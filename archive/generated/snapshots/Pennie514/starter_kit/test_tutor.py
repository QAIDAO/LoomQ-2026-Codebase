#!/usr/bin/env python3
"""教学引擎测试：课程数据完整性 + 每个电路的物理结论必须真的成立。

这些断言就是课程的「科学正确性」防线——如果某个电路的分布变了，
课上讲的结论就成了假话，测试必须失败。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adapter  # noqa: E402
import tutor  # noqa: E402

SHOTS = 4096


def counts(qasm: str, shots: int = SHOTS) -> dict:
    return adapter.run(qasm, "spinq", shots)["counts"]


def pct(c: dict, key: str, shots: int = SHOTS) -> float:
    return c.get(key, 0) / shots * 100


class TestCurriculumData(unittest.TestCase):
    def test_core_path_is_five_minutes(self):
        """对外承诺「5 分钟」，核心章节 eta 之和必须真的是 300 秒。"""
        self.assertEqual(tutor.curriculum()["core_eta"], 300)

    def test_every_lesson_has_required_fields(self):
        for ls in tutor.LESSONS:
            with self.subTest(lesson=ls["id"]):
                self.assertTrue(ls["id"] and ls["title"] and ls["chapter"])
                self.assertTrue(ls["say"], "每章都要有引导文案")
                self.assertGreater(ls["eta"], 0)

    def test_predict_answers_in_range(self):
        for ls in tutor.LESSONS:
            p = ls.get("predict")
            if p:
                with self.subTest(lesson=ls["id"]):
                    self.assertIn(p["answer"], range(len(p["options"])))
                    self.assertTrue(p["why"], "答案必须配解释")

    def test_quiz_wellformed(self):
        self.assertGreaterEqual(len(tutor.QUIZ), 5)
        for i, q in enumerate(tutor.QUIZ):
            with self.subTest(q=i):
                self.assertIn(q["answer"], range(len(q["options"])))
                self.assertTrue(q["why"])

    def test_opening_experiment_count_matches_reality(self):
        """开场承诺「6 个真实实验」，实际可跑的实验章节数必须对得上。"""
        runnable = sum(1 for ls in tutor.LESSONS
                       if ls.get("circuit") or ls["id"] in ("grover", "real"))
        opening = " ".join(tutor.LESSONS[0]["say"])
        self.assertIn(f"{runnable} 个真实实验", opening)

    def test_only_whitelisted_gates(self):
        """电路只能用适配器支持的 12 门，否则真机/模拟器会当场报错。"""
        allowed = set(adapter._GATE_ARITY)
        qasms = [ls["circuit"]["qasm"] for ls in tutor.LESSONS if ls.get("circuit")]
        for ls in tutor.LESSONS:
            for run in (ls.get("compare") or {}).get("runs", []):
                qasms.append(run["qasm"])
        qasms += [tutor.grover_qasm(t) for t in ("00", "01", "10", "11")]
        for q in qasms:
            for line in q.splitlines():
                line = line.strip()
                if (not line or line.startswith(("OPENQASM", "include", "qreg",
                                                 "creg", "measure", "//"))):
                    continue
                gate = line.split("(")[0].split()[0].rstrip(";")
                self.assertIn(gate, allowed, f"未授权的门 {gate!r}")


class TestPhysicsClaims(unittest.TestCase):
    """每一条课上讲的结论，都在这里被真实运行验证。"""

    def test_ch2_superposition_is_fair_coin(self):
        c = counts(tutor.LESSONS[2]["circuit"]["qasm"])
        self.assertAlmostEqual(pct(c, "0"), 50, delta=6)
        self.assertAlmostEqual(pct(c, "1"), 50, delta=6)

    def test_ch3_interference_returns_to_certainty(self):
        """两次 H 必须 100% 回到 0 —— 这是「叠加不是隐藏答案」的全部证据。"""
        c = counts(tutor.LESSONS[3]["circuit"]["qasm"])
        self.assertEqual(pct(c, "0"), 100.0)

    def test_ch4_bell_only_correlated_outcomes(self):
        c = counts(tutor.LESSONS[4]["circuit"]["qasm"])
        self.assertAlmostEqual(pct(c, "00") + pct(c, "11"), 100, delta=0.01)
        self.assertEqual(c.get("01", 0), 0)
        self.assertEqual(c.get("10", 0), 0)

    def test_ch5_entanglement_survives_rotation(self):
        """决定性实验（量子组）：旋转后相关性必须完好。"""
        c = counts(tutor.LESSONS[5]["circuit"]["qasm"])
        self.assertAlmostEqual(pct(c, "00") + pct(c, "11"), 100, delta=0.01)

    def test_ch5_classical_strategy_collapses(self):
        """决定性实验（经典组）：「事先约好」旋转后必须散成四种均匀 —— 当场失败。"""
        merged: dict = {}
        for run in tutor.LESSONS[5]["compare"]["runs"]:
            for k, v in counts(run["qasm"], run["shots"]).items():
                merged[k] = merged.get(k, 0) + v
        total = sum(merged.values())
        self.assertEqual(len(merged), 4, "经典策略应出现全部 4 种结果")
        for state in ("00", "01", "10", "11"):
            self.assertAlmostEqual(merged.get(state, 0) / total * 100, 25, delta=6,
                                   msg=f"{state} 应接近 25%")

    def test_ch6_grover_hits_every_target_exactly(self):
        """2 比特 Grover 是精确算法：每个目标都必须 100% 命中。"""
        for t in ("00", "01", "10", "11"):
            with self.subTest(target=t):
                c = counts(tutor.grover_qasm(t), 1024)
                self.assertEqual(c.get(t, 0), 1024,
                                 f"target={t} 应 100% 命中，实际 {c}")

    def test_grover_rejects_bad_target(self):
        with self.assertRaises(ValueError):
            tutor.grover_qasm("111")

    def test_circuits_run_on_all_three_backends(self):
        """统一中间层的核心承诺：同一份电路三家平台分布一致。"""
        qasm = tutor.LESSONS[4]["circuit"]["qasm"]
        for backend in adapter.SUPPORTED_TARGETS:
            with self.subTest(backend=backend):
                c = adapter.run(qasm, backend, 2048)["counts"]
                good = (c.get("00", 0) + c.get("11", 0)) / 2048 * 100
                self.assertAlmostEqual(good, 100, delta=0.01)


if __name__ == "__main__":
    unittest.main(verbosity=2)

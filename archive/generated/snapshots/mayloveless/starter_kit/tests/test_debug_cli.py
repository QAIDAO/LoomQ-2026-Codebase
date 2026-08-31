"""Task 13A tests for the thin trace CLI consumer."""

import importlib.util
import os
import unittest
from unittest import mock

from loomq.debug_cli import (
    PROBABILITY_BAR_WIDTH,
    _probability_bar,
    build_debug_trace,
    consume_events,
    render_event,
)
from loomq.debug_trace import TraceRecorder


BRAKET_INSTALLED = importlib.util.find_spec("braket") is not None


def events(count):
    recorder = TraceRecorder()
    for index in range(count):
        recorder.emit(
            layer="agent",
            stage="stage_%d" % index,
            executor="local",
            status="ok",
            summary="event %d" % index,
        )
    return recorder.events


class DebugCliTests(unittest.TestCase):
    def test_rendering_uses_chinese_labels_without_changing_machine_fields(self):
        recorder = TraceRecorder()
        event = recorder.emit(
            layer="agent",
            stage="intent",
            executor="llm",
            status="ok",
            summary="模型已识别任务。",
            data={"task_type": "generate_qasm"},
        )

        rendered = render_event(event)

        self.assertIn("Agent · 模型 · 识别任务 · 成功", rendered)
        self.assertEqual(event.layer, "agent")
        self.assertEqual(event.executor, "llm")
        self.assertEqual(event.stage, "intent")
        self.assertEqual(event.status, "ok")

    def test_color_rendering_distinguishes_layer_executor_and_status(self):
        recorder = TraceRecorder()
        event = recorder.emit(
            layer="circuit",
            stage="trace_stopped_after_measurement",
            executor="local",
            status="warning",
            summary="已停止追踪。",
        )

        plain = render_event(event)
        colored = render_event(event, color=True)

        self.assertNotIn("\033[", plain)
        self.assertIn("\033[36m电路\033[0m", colored)
        self.assertIn("\033[90m本地\033[0m", colored)
        self.assertIn("\033[33m警告\033[0m", colored)

    @mock.patch("loomq.debug_cli.consume_events")
    @mock.patch("loomq.debug_cli.build_debug_trace", return_value=("ok", ()))
    @mock.patch("loomq.debug_cli.sys.stdout.isatty", return_value=True)
    def test_main_disables_color_for_flag_or_no_color_environment(
        self, isatty, build_trace, consume
    ):
        from loomq.debug_cli import main

        self.assertEqual(main(["--no-color", "测试"]), 0)
        self.assertFalse(consume.call_args.kwargs["color"])

        consume.reset_mock()
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}):
            self.assertEqual(main(["测试"]), 0)
        self.assertFalse(consume.call_args.kwargs["color"])

    @mock.patch("loomq.debug_cli.consume_events")
    @mock.patch("loomq.debug_cli.build_debug_trace", return_value=("ok", ()))
    @mock.patch("loomq.debug_cli.sys.stdout.isatty", return_value=True)
    def test_main_enables_color_for_interactive_terminal(
        self, isatty, build_trace, consume
    ):
        from loomq.debug_cli import main

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(main(["测试"]), 0)

        self.assertTrue(consume.call_args.kwargs["color"])

    @mock.patch("loomq.debug_cli.consume_events")
    @mock.patch("loomq.debug_cli.build_debug_trace", return_value=("ok", ()))
    @mock.patch("loomq.debug_cli.sys.stdout.isatty", return_value=False)
    def test_main_disables_color_for_redirected_output(
        self, isatty, build_trace, consume
    ):
        from loomq.debug_cli import main

        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(main(["测试"]), 0)

        self.assertFalse(consume.call_args.kwargs["color"])

    def test_probability_bar_has_stable_fixed_width_boundaries(self):
        cases = ((0.0, 0), (0.01, 1), (0.5, 10), (1.0, 20))
        for probability, expected_filled in cases:
            with self.subTest(probability=probability):
                bar = _probability_bar(probability)
                self.assertEqual(len(bar), PROBABILITY_BAR_WIDTH)
                self.assertEqual(bar.count("█"), expected_filled)
                self.assertEqual(bar.count("░"), 20 - expected_filled)

    @mock.patch("loomq.debug_cli.trace_circuit")
    @mock.patch("loomq.debug_cli._run_agent")
    def test_backend_reply_does_not_start_circuit_trace(self, run_agent, circuit_trace):
        run_agent.return_value = "满足条件的后端：`braket_local_simulator`。"

        reply, trace_events = build_debug_trace("选择后端")

        self.assertIn("braket_local_simulator", reply)
        self.assertEqual(trace_events, ())
        circuit_trace.assert_not_called()

    @mock.patch("loomq.debug_cli._run_agent")
    def test_large_circuit_warning_does_not_replace_agent_reply(self, run_agent):
        qasm_text = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[9];
h q[0];"""
        run_agent.return_value = "ok\n\n```qasm\n%s\n```" % qasm_text

        reply, trace_events = build_debug_trace("生成九比特电路")

        self.assertIn(qasm_text, reply)
        self.assertEqual(len(trace_events), 1)
        self.assertEqual(trace_events[0].stage, "statevector_skipped")
        self.assertEqual(trace_events[0].status, "warning")

    def test_next_advances_one_event_at_a_time(self):
        commands = iter(["n", ""])
        output = []
        prompts = []

        completed = consume_events(
            events(3),
            input_fn=lambda prompt: prompts.append(prompt) or next(commands),
            output_fn=output.append,
        )

        self.assertTrue(completed)
        self.assertEqual(len(output), 3)
        self.assertEqual(len(prompts), 2)
        self.assertTrue(all("下一步" in prompt for prompt in prompts))
        self.assertTrue(all("连续执行" in prompt for prompt in prompts))
        self.assertTrue(all("退出" in prompt for prompt in prompts))

    def test_continue_prints_remaining_events_without_pausing(self):
        output = []
        prompts = []

        completed = consume_events(
            events(4),
            input_fn=lambda prompt: prompts.append(prompt) or "c",
            output_fn=output.append,
        )

        self.assertTrue(completed)
        self.assertEqual(len(output), 4)
        self.assertEqual(len(prompts), 1)

    def test_quit_only_stops_the_debug_consumer(self):
        output = []

        completed = consume_events(
            events(4),
            input_fn=lambda prompt: "q",
            output_fn=output.append,
        )

        self.assertFalse(completed)
        self.assertEqual(len(output), 1)

    @unittest.skipUnless(BRAKET_INSTALLED, "amazon-braket-sdk is not installed")
    @mock.patch("loomq.debug_cli._run_agent")
    def test_mid_measurement_warning_does_not_replace_agent_reply(self, run_agent):
        qasm_text = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
h q[0];
measure q[0] -> c[0];
x q[0];"""
        expected_reply = "已验证\n\n```qasm\n%s\n```" % qasm_text
        run_agent.return_value = expected_reply

        reply, trace_events = build_debug_trace("中途测量测试")

        self.assertEqual(reply, expected_reply)
        self.assertEqual(
            [event.stage for event in trace_events],
            ["gate_step", "measurement", "trace_stopped_after_measurement"],
        )


if __name__ == "__main__":
    unittest.main()

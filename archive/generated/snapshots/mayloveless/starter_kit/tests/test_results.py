"""统一执行结果 Schema 测试。"""

import unittest

from loomq.results import ResultValidationError, create_result


class ResultTests(unittest.TestCase):
    def test_create_valid_result(self) -> None:
        result = create_result(
            backend="braket_local_simulator",
            job_id="task-1",
            shots=4,
            counts={"00": 2, "11": 2},
            meta={"simulator": "braket_sv"},
        )

        self.assertEqual("little", result["bit_order"])
        self.assertEqual(4, sum(result["counts"].values()))
        self.assertTrue(result["timestamp"].endswith("Z"))
        self.assertNotIn("is_mock", result["meta"])

    def test_invalid_shots_are_rejected(self) -> None:
        for shots in (0, -1, True, False):
            with self.subTest(shots=shots):
                with self.assertRaisesRegex(ResultValidationError, "positive integer"):
                    create_result(
                        backend="backend",
                        job_id="job",
                        shots=shots,
                        counts={"0": 1},
                    )

    def test_counts_total_must_equal_shots(self) -> None:
        with self.assertRaisesRegex(ResultValidationError, "total must equal shots"):
            create_result(
                backend="backend", job_id="job", shots=2, counts={"0": 1}
            )

    def test_non_binary_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResultValidationError, "binary strings"):
            create_result(
                backend="backend", job_id="job", shots=1, counts={"2": 1}
            )

    def test_counts_key_lengths_must_match(self) -> None:
        with self.assertRaisesRegex(ResultValidationError, "same length"):
            create_result(
                backend="backend",
                job_id="job",
                shots=2,
                counts={"0": 1, "11": 1},
            )


if __name__ == "__main__":
    unittest.main()

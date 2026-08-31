"""Task 13A tests for deterministic per-gate Circuit Trace."""

import importlib.util
import unittest
from unittest import mock

from loomq.circuit_trace import STATE_AMPLITUDE_EPSILON, trace_circuit
from loomq.debug_cli import render_event
from loomq.debug_trace import TraceRecorder
from loomq.parser import parse_qasm


BRAKET_INSTALLED = importlib.util.find_spec("braket") is not None


def qasm(qubits, body, *, classical=False):
    creg = "creg c[%d];\n" % qubits if classical else ""
    return """OPENQASM 2.0;
include "qelib1.inc";
qreg q[%d];
%s%s
""" % (qubits, creg, body)


def by_basis(entries):
    return {entry["basis"]: entry for entry in entries}


@unittest.skipUnless(BRAKET_INSTALLED, "amazon-braket-sdk is not installed")
class CircuitTraceStatevectorTests(unittest.TestCase):
    def test_bell_h_and_cx_steps_have_expected_states(self):
        circuit = parse_qasm(
            qasm(2, "h q[0];\ncx q[0],q[1];\nmeasure q -> c;", classical=True)
        )
        recorder = TraceRecorder()

        trace_circuit(circuit, recorder)

        self.assertEqual(
            [event.stage for event in recorder.events],
            ["gate_step", "gate_step", "measurement"],
        )
        h_after = by_basis(recorder.events[0].data["state_after"])
        self.assertAlmostEqual(h_after["00"]["probability"], 0.5)
        self.assertAlmostEqual(h_after["10"]["probability"], 0.5)
        cx_after = by_basis(recorder.events[1].data["state_after"])
        self.assertAlmostEqual(cx_after["00"]["probability"], 0.5)
        self.assertAlmostEqual(cx_after["11"]["probability"], 0.5)
        self.assertNotIn("10", cx_after)

    def test_complex_relative_phase_is_preserved(self):
        circuit = parse_qasm(qasm(1, "h q[0];\ns q[0];"))
        recorder = TraceRecorder()

        trace_circuit(circuit, recorder)

        final_state = by_basis(recorder.events[-1].data["state_after"])
        self.assertAlmostEqual(final_state["0"]["real"], 2 ** -0.5)
        self.assertAlmostEqual(final_state["1"]["imag"], 2 ** -0.5)
        self.assertAlmostEqual(final_state["0"]["probability"], 0.5)
        self.assertAlmostEqual(final_state["1"]["probability"], 0.5)
        rendered = render_event(recorder.events[-1])
        self.assertIn("+0.000000+0.707107i", rendered)
        self.assertIn("██████████░░░░░░░░░░", rendered)

    def test_bit_order_matches_q0_to_qn(self):
        circuit = parse_qasm(qasm(2, "x q[0];"))
        recorder = TraceRecorder()

        trace_circuit(circuit, recorder)

        state = recorder.events[0].data["state_after"]
        self.assertEqual(state[0]["basis"], "10")
        self.assertAlmostEqual(state[0]["probability"], 1.0)

    def test_global_phase_keeps_probability_well_formed(self):
        circuit = parse_qasm(qasm(1, "x q[0];\ns q[0];\ns q[0];\nx q[0];"))
        recorder = TraceRecorder()

        trace_circuit(circuit, recorder)

        state = recorder.events[-1].data["state_after"]
        self.assertEqual(state[0]["basis"], "0")
        self.assertAlmostEqual(state[0]["real"], -1.0)
        self.assertAlmostEqual(state[0]["probability"], 1.0)

    def test_measurement_event_has_mapping_and_no_fake_outcome(self):
        circuit = parse_qasm(
            qasm(2, "h q[0];\nmeasure q -> c;", classical=True)
        )
        recorder = TraceRecorder()

        trace_circuit(circuit, recorder)

        measurement = recorder.events[-1]
        self.assertEqual(
            measurement.data["mappings"],
            [
                {"qubit": "q[0]", "classical_bit": "c[0]"},
                {"qubit": "q[1]", "classical_bit": "c[1]"},
            ],
        )
        self.assertNotIn("outcome", measurement.data)
        self.assertIn("不会伪造", measurement.data["gate_description"])
        self.assertNotIn("trace_stopped_after_measurement", [
            event.stage for event in recorder.events
        ])

    def test_primary_gate_and_measurement_descriptions_are_chinese(self):
        circuit = parse_qasm(
            qasm(
                2,
                "h q[0];\ncx q[0],q[1];\nrz(pi/2) q[1];\nmeasure q -> c;",
                classical=True,
            )
        )
        recorder = TraceRecorder()

        trace_circuit(circuit, recorder)

        descriptions = {
            event.data.get("gate", "measurement"): event.data["gate_description"]
            for event in recorder.events
            if event.stage in ("gate_step", "measurement")
        }
        self.assertIn("H 门", descriptions["h"])
        self.assertIn("CX 门", descriptions["cx"])
        self.assertIn("RZ 门", descriptions["rz"])
        self.assertIn("测量", descriptions["measurement"])

    def test_mid_circuit_measurement_emits_warning_and_stops_gate_trace(self):
        circuit = parse_qasm(
            qasm(
                1,
                "h q[0];\nmeasure q[0] -> c[0];\nx q[0];",
                classical=True,
            )
        )
        recorder = TraceRecorder()

        trace_circuit(circuit, recorder)

        self.assertEqual(
            [event.stage for event in recorder.events],
            ["gate_step", "measurement", "trace_stopped_after_measurement"],
        )
        warning = recorder.events[-1]
        self.assertEqual(warning.status, "warning")
        self.assertEqual(warning.data["measurement_operation_index"], 1)
        self.assertEqual(warning.data["remaining_gate_count"], 1)
        self.assertEqual(warning.data["reason"], "mid_circuit_measurement")
        self.assertNotIn(
            "x", [event.data.get("gate") for event in recorder.events]
        )


class CircuitTraceLimitTests(unittest.TestCase):
    @mock.patch("loomq.circuit_trace.simulate_statevector")
    def test_large_statevector_emits_warning_and_skips_simulation(self, simulator):
        circuit = parse_qasm(qasm(9, "h q[0];"))
        recorder = TraceRecorder()

        trace_circuit(circuit, recorder)

        simulator.assert_not_called()
        self.assertEqual(len(recorder.events), 1)
        self.assertEqual(recorder.events[0].stage, "statevector_skipped")
        self.assertEqual(recorder.events[0].status, "warning")
        self.assertEqual(recorder.events[0].data["max_qubits"], 8)

    @mock.patch("loomq.circuit_trace.simulate_statevector")
    def test_fixed_amplitude_threshold_omits_only_tiny_entries(self, simulator):
        simulator.side_effect = [(1 + 0j, 0j), (1 + 0j, 1e-12 + 0j)]
        circuit = parse_qasm(qasm(1, "h q[0];"))
        recorder = TraceRecorder()

        trace_circuit(circuit, recorder)

        self.assertEqual(STATE_AMPLITUDE_EPSILON, 1e-10)
        self.assertEqual(
            [item["basis"] for item in recorder.events[0].data["state_after"]],
            ["0"],
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import random
import unittest

from starter_kit.evaluator import calculate_hellinger_fidelity, validate_schema
from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.loomq.runners import run_circuit
from starter_kit.loomq.simulator import probabilities


def multi_register_fuzz(seed: int) -> str:
    rng = random.Random(seed)
    qnames = (f"alpha_{seed}", f"beta_{seed}")
    cnames = (f"flag_{seed}", f"out_{seed}")
    refs = (f"{qnames[0]}[0]", f"{qnames[0]}[1]", f"{qnames[1]}[0]")
    lines = [
        "OPENQASM 2.0;", 'include "qelib1.inc";',
        f"qreg {qnames[0]}[2];", f"qreg {qnames[1]}[1];",
        f"creg {cnames[0]}[1];", f"creg {cnames[1]}[2];",
        f"h {refs[0]};",
    ]
    one = ("h", "x", "s", "sdg", "t", "tdg")
    angles = ("pi/3", "-pi/4 + pi/8", "3*pi/7")
    for _ in range(16):
        family = rng.choice(("one", "rotation", "two", "three"))
        if family == "one":
            lines.append(f"{rng.choice(one)} {rng.choice(refs)};")
        elif family == "rotation":
            lines.append(f"{rng.choice(('rz', 'ry'))}({rng.choice(angles)}) {rng.choice(refs)};")
        elif family == "two":
            a, b = rng.sample(refs, 2)
            gate = rng.choice(("cx", "swap", "cu1"))
            parameter = f"({rng.choice(angles)})" if gate == "cu1" else ""
            lines.append(f"{gate}{parameter} {a},{b};")
        else:
            a, b, c = rng.sample(refs, 3)
            lines.append(f"ccx {a},{b},{c};")
    lines.extend(
        (
            f"measure {refs[0]} -> {cnames[1]}[1];",
            f"measure {refs[1]} -> {cnames[0]}[0];",
            f"measure {refs[2]} -> {cnames[1]}[0];",
        )
    )
    return "\n".join(lines) + "\n"


class OfficialGrammarFuzzTests(unittest.TestCase):
    def test_multiple_register_names_mappings_and_parameters_match_three_sdks(self):
        shots = 4096
        for seed in (112, 2026, 825):
            source = multi_register_fuzz(seed)
            circuit = parse_qasm(source)
            expected = probabilities(circuit)
            for target in ("spinq", "originq", "braket"):
                with self.subTest(seed=seed, target=target):
                    result = run_circuit(circuit, target, shots)
                    valid, reason = validate_schema(result)
                    self.assertTrue(valid, reason)
                    observed = {state: count / shots for state, count in result["counts"].items()}
                    self.assertGreaterEqual(calculate_hellinger_fidelity(observed, expected), 0.97)
                    self.assertNotIn("reference", result["meta"]["engine"])


if __name__ == "__main__":
    unittest.main()

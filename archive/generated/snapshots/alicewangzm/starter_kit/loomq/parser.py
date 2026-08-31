"""OpenQASM 2.0 parser for the LoomQ universal transpiler (L1.1).

Turns raw QASM text into a neutral intermediate representation (IR) that every
backend emitter (SpinQ / OriginIR / Braket) can walk. Keeping the IR
vendor-agnostic is what makes the transpiler genuinely "universal" rather than
three hardcoded string translators.

IR shape returned by parse_qasm():

    {
        "qreg": {"q": 2},         # register name -> size
        "creg": {"c": 2},
        "ops":  [                 # operations, in program order
            {"gate": "h",  "qubits": [0],    "params": []},
            {"gate": "cx", "qubits": [0, 1], "params": []},
            # measure ops also carry their classical-bit targets:
            {"gate": "measure", "qubits": [0], "clbits": [0]},
        ],
    }
"""

import re
import math

PLAIN_GATES = {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"}


def _parse_reg(statement):
    """Parse one register declaration into a (name, size) pair.

    >>> _parse_reg("qreg q[2]")
    ('q', 2)
    >>> _parse_reg("creg c[12]")
    ('c', 12)

    Size is the integer between the brackets. Name is the last whitespace-
    separated word before '[', so any leading newline left by the ';' split
    is harmlessly dropped.
    """
    statement_left_bracket_index = statement.index("[")
    statement_right_bracket_index = statement.index("]")
    statement_N_string = statement[
        statement_left_bracket_index + 1 : statement_right_bracket_index
    ]

    return (
        statement[:statement_left_bracket_index].split()[-1],
        int(statement_N_string),
    )

def _parse_params(statement):
    """Extract a gate's angle parameter(s) as floats.

    >>> _parse_params("rz(pi/2) q[0]")
    [1.5707963267948966]
    >>> _parse_params("h q[0]")
    []

    Only rz/ry/cu1 carry a parameter, always a single angle inside '(...)'. The
    angle may reference 'pi' or be plain arithmetic (e.g. '-pi/4', '1.5708'), so
    it is evaluated with 'pi' bound to math.pi. eval runs with builtins removed
    ({"__builtins__": {}}) so the expression can only do arithmetic, nothing else.
    """
    params = []
    match = re.search(r"\(([^)]*)\)", statement)
    if match:
        expr = match.group(1)  # text between the parens, e.g. 'pi/2'
        params.append(eval(expr, {"__builtins__": {}}, {"pi": math.pi}))
    return params


def _bracket_ints(s):
    """Extract every bracketed integer, left to right.

    >>> _bracket_ints("cx q[0], q[1]")
    [0, 1]

    Used to pull qubit / clbit indices out of a gate or measure statement.
    Spacing between operands is irrelevant because the regex matches each
    '[digits]' group independently (handles both 'q[0], q[1]' and 'q[0],q[1]').
    """
    return [int(n) for n in re.findall(r"\[(\d+)\]", s)]


def parse_qasm(qasm_str: str):
    """Parse an OpenQASM 2.0 program into the LoomQ IR (see module docstring).

    Assumes the fixed header shared by every evaluation circuit:

        OPENQASM 2.0;
        include "qelib1.inc";

    so the first two ';'-separated statements are dropped, leaving the qreg
    declaration, the creg declaration, then the gate / measure body.

    Each gate/measure statement becomes one or more entries in ir["ops"].
    Parameterised gates (rz/ry/cu1) carry their evaluated angle in "params".
    A gate outside the whitelist raises ValueError, so malformed input fails
    loudly instead of silently producing a wrong circuit.
    """
    ir = {
        "qreg": {},
        "creg": {},
        "ops": [],
    }
    # Strip line comments ('//' to end of line) so they don't get glued onto
    # the next statement when we split on ';'.
    qasm_str = re.sub(r'//.*', '', qasm_str)
    # Split into ';'-terminated statements; [2:] drops the OPENQASM + include
    # header lines.
    statements = qasm_str.split(";")
    statements_without_header = statements[2:]

    # First two remaining statements are the quantum and classical registers.
    qname, qsize = _parse_reg(statements_without_header[0])
    ir["qreg"][qname] = qsize

    cname, csize = _parse_reg(statements_without_header[1])
    ir["creg"][cname] = csize

    # Parse the circuit body into ir["ops"]. statements[4:] skips the four
    # statements already handled above (OPENQASM, include, qreg, creg).
    for statement in statements[4:]:
        ops_statements = statement.strip()
        if ops_statements == "":
            continue  # trailing empty piece left by the final ';'

        # Dispatch on the leading token: a whitelisted gate, a measurement, or
        # an unsupported gate (rejected loudly below).
        gate_name = ops_statements.split()[0].split("(")[0]
        if gate_name in PLAIN_GATES:
            # One op per gate line. _parse_params pulls the angle for rz/ry/cu1
            # and returns [] for gates that take no parameter.
            gate_list = {
                "gate": gate_name,
                "qubits": _bracket_ints(statement),
                "params": _parse_params(statement),
            }
            ir["ops"].append(gate_list)
        elif gate_name == "measure":
            left, right = statement.split("->")
            left, right = left.strip(), right.strip()

            if "[" in left:
                # single-bit form: measure q[0] -> c[0]
                q_index = _bracket_ints(left)[0]
                c_index = _bracket_ints(right)[0]
                ir["ops"].append(
                    {"gate": "measure", "qubits": [q_index], "clbits": [c_index]}
                )
            else:
                # whole-register form: measure q -> c
                q_name = left.split()[-1]  # 'q'  (word after 'measure')
                n = ir["qreg"][q_name]  # how many qubits -> how many ops
                for i in range(n):  # <-- the expansion loop
                    ir["ops"].append(
                        {"gate": "measure", "qubits": [i], "clbits": [i]}
                        
                    )
        else:
            raise ValueError(f"unsupported gate: {gate_name!r} in {ops_statements!r}")

    return ir

# Unified gate registry for LoomQ L1.
#
# Internal gate names follow OpenQASM 2.0 input names.
#
# Supported targets:
#   spinq
#   braket
#   originq
import ast
import math
import operator


_ALLOWED_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

_ALLOWED_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
def parse_angle(expression: str) -> float:
    node = ast.parse(
        expression,
        mode="eval"
    ).body

    def evaluate(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)

        if isinstance(node, ast.Name):
            if node.id == "pi":
                return math.pi

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)

            if op_type in _ALLOWED_BINARY_OPS:
                return _ALLOWED_BINARY_OPS[op_type](
                    evaluate(node.left),
                    evaluate(node.right)
                )

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)

            if op_type in _ALLOWED_UNARY_OPS:
                return _ALLOWED_UNARY_OPS[op_type](
                    evaluate(node.operand)
                )

        raise ValueError(
            f"Unsupported angle expression: {expression}"
        )

    return evaluate(node)
    
GATE_SPECS = {
    "h": {
        "arity": 1,
        "num_params": 0,
        "spinq": {
            "emit": "h",
            "sdk": "H",
        },
        "braket": {
            "emit": "h",
        },
        "originq": {
            "emit": "H",
            "sdk": "H",
        },
    },

    "x": {
        "arity": 1,
        "num_params": 0,
        "spinq": {
            "emit": "x",
            "sdk": "X",
        },
        "braket": {
            "emit": "x",
        },
        "originq": {
            "emit": "X",
            "sdk": "X",
        },
    },

    "s": {
        "arity": 1,
        "num_params": 0,
        "spinq": {
            "emit": "s",
            "sdk": "S",
        },
        "braket": {
            "emit": "s",
        },
        "originq": {
            "emit": "S",
            "sdk": "S",
        },
    },

    "sdg": {
        "arity": 1,
        "num_params": 0,
        "spinq": {
            "emit": "sdg",
            "sdk": "Sd",
        },
        "braket": {
            "emit": "si",
        },
        "originq": {
            "emit": "SDAG",
            "sdk": "S",
        },
    },

    "t": {
        "arity": 1,
        "num_params": 0,
        "spinq": {
            "emit": "t",
            "sdk": "T",
        },
        "braket": {
            "emit": "t",
        },
        "originq": {
            "emit": "T",
            "sdk": "T",
        },
    },

    "tdg": {
        "arity": 1,
        "num_params": 0,
        "spinq": {
            "emit": "tdg",
            "sdk": "Td",
        },
        "braket": {
            "emit": "ti",
        },
        "originq": {
            "emit": "TDAG",
            "sdk": "T",
        },
    },

    "ry": {
        "arity": 1,
        "num_params": 1,
        "spinq": {
            "emit": "ry",
            "sdk": "Ry",
        },
        "braket": {
            "emit": "ry",
        },
        "originq": {
            "emit": "RY",
            "sdk": "RY",
        },
    },

    "rz": {
        "arity": 1,
        "num_params": 1,
        "spinq": {
            "emit": "rz",
            "sdk": "Rz",
        },
        "braket": {
            "emit": "rz",
        },
        "originq": {
            "emit": "RZ",
            "sdk": "RZ",
        },
    },

    "cx": {
        "arity": 2,
        "num_params": 0,
        "spinq": {
            "emit": "cx",
            "sdk": "CX",
        },
        "braket": {
            "emit": "cnot",
        },
        "originq": {
            "emit": "CNOT",
            "sdk": "CNOT",
        },
    },

    "cu1": {
        "arity": 2,
        "num_params": 1,
        "spinq": {
            "emit": "cu1",
            "sdk": "CP",
        },
        "braket": {
            "emit": "cphaseshift",
        },
        "originq": {
            "emit": "CR",
            "sdk": "CR",
        },
    },

    "swap": {
        "arity": 2,
        "num_params": 0,
        "spinq": {
            "emit": "swap",
            "sdk": "SWAP",
        },
        "braket": {
            "emit": "swap",
        },
        "originq": {
            "emit": "SWAP",
            "sdk": "SWAP",
        },
    },

    "ccx": {
        "arity": 3,
        "num_params": 0,
        "spinq": {
            "emit": "ccx",
            "sdk": "CCX",
        },
        "braket": {
            "emit": "ccnot",
        },
        "originq": {
            "emit": "TOFFOLI",
            "sdk": "Toffoli",
        },
    },
}


SUPPORTED_GATES = set(GATE_SPECS)

SUPPORTED_TARGETS = (
    "spinq",
    "originq",
    "braket",
)


def get_gate_spec(gate_name: str) -> dict:
    gate_name = gate_name.lower()

    if gate_name not in GATE_SPECS:
        raise ValueError(
            f"Unsupported gate: {gate_name}"
        )

    return GATE_SPECS[gate_name]


def get_gate_name(
    gate_name: str,
    target: str,
    sdk: bool = False,
) -> str:

    gate_name = gate_name.lower()
    target = target.lower()

    if gate_name not in GATE_SPECS:
        raise ValueError(
            f"Unsupported gate: {gate_name}"
        )

    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"Unsupported target: {target}"
        )

    spec = GATE_SPECS[gate_name]

    if sdk:
        if "sdk" not in spec[target]:
            raise ValueError(
                f"No SDK mapping for "
                f"{gate_name} on {target}"
            )

        return spec[target]["sdk"]

    return spec[target]["emit"]

def get_gate_arity(gate_name: str) -> int:
    return get_gate_spec(gate_name)["arity"]


def get_gate_num_params(gate_name: str) -> int:
    return get_gate_spec(gate_name)["num_params"]

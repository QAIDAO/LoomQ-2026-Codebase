"""Gate specifications shared by parsers and target readers."""


GATE_SPECS = {
    "h": (1, False),
    "x": (1, False),
    "s": (1, False),
    "sdg": (1, False),
    "t": (1, False),
    "tdg": (1, False),
    "rz": (1, True),
    "ry": (1, True),
    "cx": (2, False),
    "cu1": (2, True),
    "swap": (2, False),
    "ccx": (3, False),
}

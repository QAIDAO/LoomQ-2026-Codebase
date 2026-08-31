from .ir import Circuit, Gate, Measurement
from .parser import QASMParser
from .spinq_backend import SpinQBackend
from .originq_backend import OriginQBackend
from .braket_backend import BraketBackend

BACKENDS = {
    "spinq": SpinQBackend,
    "originq": OriginQBackend,
    "braket": BraketBackend,
}

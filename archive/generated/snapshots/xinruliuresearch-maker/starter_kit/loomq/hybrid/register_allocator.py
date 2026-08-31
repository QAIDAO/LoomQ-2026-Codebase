"""Deterministic temporary-register allocation for TinyRISCV programs."""

from __future__ import annotations

from typing import Iterable, List, Set


class RegisterExhaustionError(ValueError):
    """Raised when no non-reserved RISC-V register is available."""


class TemporaryRegisterAllocator:
    """Allocate the lowest free x-register and permit deterministic reuse.

    x0 is never allocatable.  x1..x9 are always reserved for r1..r9, while the
    compiler additionally reserves x10+k for each referenced measurement bit.
    """

    def __init__(self, reserved: Iterable[int]):
        reserved_set = set(reserved)
        reserved_set.add(0)
        invalid = sorted(index for index in reserved_set if index < 0 or index > 31)
        if invalid:
            raise ValueError(f"reserved registers outside x0..x31: {invalid}")
        self._available: List[int] = [
            index for index in range(1, 32) if index not in reserved_set
        ]
        self._active: Set[int] = set()

    def allocate(self) -> int:
        if not self._available:
            active = ", ".join(f"x{index}" for index in sorted(self._active)) or "none"
            raise RegisterExhaustionError(
                "no temporary RISC-V registers remain after reserving r1..r9 "
                f"and referenced measurement registers (active temporaries: {active})"
            )
        register = self._available.pop(0)
        self._active.add(register)
        return register

    def release(self, register: int) -> None:
        if register not in self._active:
            raise ValueError(f"x{register} is not an active temporary register")
        self._active.remove(register)
        self._available.append(register)
        self._available.sort()

    @property
    def active(self) -> frozenset[int]:
        return frozenset(self._active)

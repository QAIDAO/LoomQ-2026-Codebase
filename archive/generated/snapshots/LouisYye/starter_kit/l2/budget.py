import time


class Budget:
    def __init__(self, total: float = 110.0):
        self.deadline = time.monotonic() + total

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def timeout_for_call(self) -> float:
        return max(1.0, min(45.0, self.remaining() - 8.0))

    def can_retry(self, min_seconds: float = 20.0) -> bool:
        return self.remaining() >= min_seconds


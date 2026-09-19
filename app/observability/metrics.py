from collections import Counter
from threading import Lock


class Metrics:
    def __init__(self):
        self._counters = Counter()
        self._lock = Lock()

    def increment(self, name: str, value: int = 1):
        with self._lock:
            self._counters[name] += value

    def get(self, name: str) -> int:
        with self._lock:
            return self._counters[name]

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)


metrics = Metrics()

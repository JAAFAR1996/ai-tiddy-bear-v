"""
LatencyOptimizer: Optimize streaming latency for real-time audio.
"""

import time


class LatencyOptimizer:
    def __init__(self, target_latency_ms: int = 100):
        self.target_latency_ms = target_latency_ms

    def optimize(self, start_time: float) -> float:
        elapsed = (time.time() - start_time) * 1000
        sleep_time = max(0, self.target_latency_ms - elapsed) / 1000
        if sleep_time > 0:
            time.sleep(sleep_time)
        return sleep_time

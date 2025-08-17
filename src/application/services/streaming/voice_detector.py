"""
VoiceDetector: Voice Activity Detection (VAD) for real-time streams.
"""

import numpy as np


class VoiceDetector:
    def __init__(self, threshold: float = 0.01):
        self.threshold = threshold

    def is_voice(self, audio_chunk: bytes) -> bool:
        # Very basic VAD: energy threshold
        audio_np = np.frombuffer(audio_chunk, dtype=np.int16)
        energy = np.mean(np.abs(audio_np))
        return energy > self.threshold

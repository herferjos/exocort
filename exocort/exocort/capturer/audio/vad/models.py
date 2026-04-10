from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import webrtcvad

@dataclass(slots=True)
class AudioVADConfig:
    enabled: bool = False
    aggressiveness: int = 2
    frame_ms: int = 30
    pre_roll_seconds: float = 0.3
    min_speech_seconds: float = 0.2
    min_silence_seconds: float = 0.8


class WebRTCVAD:
    def __init__(self, config: AudioVADConfig, sample_rate: int) -> None:
        if webrtcvad is None:
            raise RuntimeError(
                "Audio VAD requires the 'webrtcvad' package. Install dependencies again to enable it."
            )
        self.config = config
        self.sample_rate = sample_rate
        self.frame_ms = self._resolve_frame_ms(config.frame_ms)
        self.frame_samples = sample_rate * self.frame_ms // 1000
        self.detector = webrtcvad.Vad(self._resolve_aggressiveness(config.aggressiveness))
        self.last_ratio: float = 0.0

    def is_speech(self, samples: np.ndarray) -> bool:
        pcm = self._prepare_frame(samples)
        if pcm is None:
            self.last_ratio = 0.0
            return False

        speech = bool(self.detector.is_speech(pcm.tobytes(), self.sample_rate))
        self.last_ratio = 1.0 if speech else 0.0
        return speech

    def _prepare_frame(self, samples: np.ndarray) -> np.ndarray | None:
        mono = self._mix_down(samples)
        if mono.size != self.frame_samples:
            return None
        if mono.dtype != np.int16:
            mono = mono.astype(np.int16)
        return mono

    def _mix_down(self, samples: np.ndarray) -> np.ndarray:
        if samples.ndim <= 1:
            return samples.reshape(-1)
        return samples.mean(axis=1).astype(np.int16)

    def _resolve_aggressiveness(self, value: int) -> int:
        return min(3, max(0, int(value)))

    def _resolve_frame_ms(self, value: int) -> int:
        supported = (10, 20, 30)
        frame_ms = int(value)
        if frame_ms in supported:
            return frame_ms
        return min(supported, key=lambda candidate: abs(candidate - frame_ms))

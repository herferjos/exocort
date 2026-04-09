from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class _SegmentCollector:
    max_frames: int
    pre_roll_chunks: int
    min_speech_chunks: int
    min_silence_chunks: int
    pre_roll: deque[np.ndarray] = field(init=False)
    pending_speech: list[np.ndarray] = field(default_factory=list)
    chunks: list[np.ndarray] = field(default_factory=list)
    frames: int = 0
    recording: bool = False
    speech_chunks: int = 0
    silence_chunks: int = 0

    def __post_init__(self) -> None:
        self.pre_roll = deque(maxlen=self.pre_roll_chunks)

    def push(self, chunk: np.ndarray, speech_detected: bool) -> np.ndarray | None:
        chunk_copy = chunk.copy()

        if self.recording:
            self.chunks.append(chunk_copy)
            self.frames += int(chunk.shape[0])
            if speech_detected:
                self.speech_chunks += 1
                self.silence_chunks = 0
            else:
                self.silence_chunks += 1
            if self.frames >= self.max_frames or self.silence_chunks >= self.min_silence_chunks:
                return self._finish()
            return None

        if speech_detected:
            self.pending_speech.append(chunk_copy)
            self.speech_chunks += 1
            if self.speech_chunks >= self.min_speech_chunks:
                self.recording = True
                self.chunks = [*self.pre_roll, *self.pending_speech]
                self.frames = sum(int(part.shape[0]) for part in self.chunks)
                self.pending_speech.clear()
                self.silence_chunks = 0
                if self.frames >= self.max_frames:
                    return self._finish()
            return None

        self.pre_roll.append(chunk_copy)
        self.pending_speech.clear()
        self.speech_chunks = 0
        return None

    def _finish(self) -> np.ndarray:
        segment = np.concatenate(self.chunks, axis=0)
        self.pre_roll.clear()
        self.pending_speech.clear()
        self.chunks.clear()
        self.frames = 0
        self.recording = False
        self.speech_chunks = 0
        self.silence_chunks = 0
        return segment

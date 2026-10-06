"""Segmentação por fala (silero-vad, via ONNX) de um track mono 16 kHz."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SR = 16000
WIN = 512  # amostras por janela do silero a 16 kHz
PARTIAL_EVERY_S = 4.0


@dataclass
class SpeechEvent:
    kind: str  # "partial" | "final"
    t0: float
    t1: float
    pcm: np.ndarray
    source: str


ONNX_PATH = Path(__file__).parent / "assets" / "silero_vad.onnx"
_session = None
_session_lock = threading.Lock()


def _get_session():
    """Sessão ONNX do silero-vad (compartilhada; é segura para várias threads). Sem PyTorch: o instalador fica ~460 MB menor."""
    global _session
    with _session_lock:
        if _session is None:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            _session = ort.InferenceSession(str(ONNX_PATH), sess_options=opts, providers=["CPUExecutionProvider"])
        return _session


class SileroVad:
    """Probabilidade de voz por janela de 512 amostras (16 kHz). Cada instância tem o SEU estado (o modelo antigo dividia
    o estado entre o microfone e a reunião)."""

    CONTEXT = 64

    def __init__(self):
        self.session = _get_session()
        self.reset()

    def reset(self):
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self.CONTEXT), dtype=np.float32)

    def __call__(self, win: np.ndarray) -> float:
        x = np.concatenate([self._context, np.asarray(win, dtype=np.float32).reshape(1, -1)], axis=1)
        out, self._state = self.session.run(None, {"input": x, "state": self._state, "sr": np.array(SR, dtype="int64")})
        self._context = x[:, -self.CONTEXT:]
        return float(out.reshape(-1)[0])


class Segmenter:
    """Recebe áudio contínuo e emite segmentos de fala (parciais e finais)."""

    def __init__(self, source: str, silence_ms: int = 600, max_segment_s: float = 15.0,
                 threshold: float = 0.5, min_speech_s: float = 0.3):
        self.source = source
        self.silence_win = int(silence_ms / 1000 * SR / WIN)
        self.max_samples = int(max_segment_s * SR)
        self.threshold = threshold
        self.min_samples = int(min_speech_s * SR)
        self.model = SileroVad()
        self._tail = np.zeros(0, dtype=np.float32)
        self._reset()

    def _reset(self):
        self.buf: list[np.ndarray] = []
        self.n = 0
        self.t0 = 0.0
        self.silent_wins = 0
        self.speaking = False
        self.last_partial = 0
        self.pre: list[np.ndarray] = []  # pré-roll de 1 janela para não cortar o início

    def feed(self, pcm: np.ndarray, t_start: float) -> list[SpeechEvent]:
        """`pcm`: float32 mono 16 kHz; `t_start`: instante (s) da 1ª amostra."""
        events: list[SpeechEvent] = []
        data = np.concatenate([self._tail, pcm]) if len(self._tail) else pcm
        t = t_start - len(self._tail) / SR
        i = 0
        while i + WIN <= len(data):
            win = data[i:i + WIN]
            wt = t + i / SR
            i += WIN
            prob = self.model(win)
            voiced = prob >= self.threshold
            if not self.speaking:
                if voiced:
                    self.speaking = True
                    self.t0 = wt - (len(self.pre) * WIN / SR)
                    self.buf = list(self.pre) + [win]
                    self.n = sum(len(b) for b in self.buf)
                    self.silent_wins = 0
                    self.last_partial = 0
                else:
                    self.pre = [win]
                continue
            self.buf.append(win)
            self.n += WIN
            self.silent_wins = 0 if voiced else self.silent_wins + 1
            if self.silent_wins >= self.silence_win or self.n >= self.max_samples:
                events.extend(self._finish())
            elif self.n - self.last_partial >= PARTIAL_EVERY_S * SR:
                self.last_partial = self.n
                events.append(self._event("partial"))
        self._tail = data[i:].copy()
        return events

    def flush(self) -> list[SpeechEvent]:
        return self._finish() if self.speaking else []

    def _event(self, kind: str) -> SpeechEvent:
        pcm = np.concatenate(self.buf)
        return SpeechEvent(kind, self.t0, self.t0 + len(pcm) / SR, pcm, self.source)

    def _finish(self) -> list[SpeechEvent]:
        ev = []
        if self.n >= self.min_samples:
            ev.append(self._event("final"))
        self._reset()
        return ev

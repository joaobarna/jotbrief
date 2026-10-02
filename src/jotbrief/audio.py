"""Captura de microfone + loopback WASAPI (pyaudiowpatch), resample 16 kHz e WAV estéreo."""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable

import numpy as np
import soundfile as sf

SR = 16000
log = logging.getLogger(__name__)


def list_devices() -> dict[str, list[dict]]:
    import pyaudiowpatch as pa

    p = pa.PyAudio()
    try:
        mics, loops = [], []
        for d in p.get_device_info_generator():
            if d.get("isLoopbackDevice"):
                loops.append(d)
            elif d["maxInputChannels"] > 0 and d["hostApi"] == p.get_host_api_info_by_type(pa.paWASAPI)["index"]:
                mics.append(d)
        return {"mics": mics, "loopbacks": loops}
    finally:
        p.terminate()


def default_devices() -> tuple[dict, dict]:
    import pyaudiowpatch as pa

    p = pa.PyAudio()
    try:
        wasapi = p.get_host_api_info_by_type(pa.paWASAPI)
        mic = p.get_device_info_by_index(wasapi["defaultInputDevice"])
        spk = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
        if not spk.get("isLoopbackDevice"):
            for lb in p.get_loopback_device_info_generator():
                if spk["name"] in lb["name"]:
                    spk = lb
                    break
        return mic, spk
    finally:
        p.terminate()


class Track:
    """Um stream de captura. O callback só enfileira; `process` faz resample/downmix."""

    def __init__(self, name: str, device: dict, t0: Callable[[], float]):
        self.name = name
        self.device = device
        self._now = t0
        self.q: queue.Queue = queue.Queue()
        self.rate = int(device["defaultSampleRate"])
        self.channels = int(device["maxInputChannels"])
        self.last_cb = time.perf_counter()
        self._stream = None
        self._pa = None
        import soxr

        self._rs = soxr.ResampleStream(self.rate, SR, 1, dtype="float32")

    def open(self):
        import pyaudiowpatch as pa

        self._pa = pa.PyAudio()
        self._stream = self._pa.open(
            format=pa.paFloat32, channels=self.channels, rate=self.rate, input=True,
            input_device_index=self.device["index"], frames_per_buffer=int(self.rate * 0.1),
            stream_callback=self._cb,
        )
        self.last_cb = time.perf_counter()

    def _cb(self, data, frames, info, status):
        import pyaudiowpatch as pa

        self.last_cb = time.perf_counter()
        self.q.put((self._now() - frames / self.rate, data))
        return (None, pa.paContinue)

    def close(self):
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                log.exception("erro fechando stream %s", self.name)
            self._stream = None
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

    def read(self, timeout: float = 0.2):
        """Retorna (t_start, pcm 16 kHz mono float32) ou None."""
        try:
            t, raw = self.q.get(timeout=timeout)
        except queue.Empty:
            return None
        x = np.frombuffer(raw, dtype=np.float32).reshape(-1, self.channels).mean(axis=1)
        return t, self._rs.resample_chunk(x)


class StereoRecorder:
    """WAV estéreo 16 kHz (L=mic, R=reunião) alinhado pelo relógio de sessão."""

    def __init__(self, path, sources: tuple[str, str] = ("mic", "loop"), append: bool = False):
        from pathlib import Path

        start = 0
        if append and Path(path).exists():
            self.f = sf.SoundFile(str(path), "r+")
            start = self.f.frames
            self.f.seek(0, sf.SEEK_END)
        else:
            self.f = sf.SoundFile(str(path), "w", samplerate=SR, channels=2, subtype="PCM_16")
        self.idx = {sources[0]: 0, sources[1]: 1}
        self.bufs = {s: np.zeros(0, dtype=np.float32) for s in sources}
        self.pos = {s: start for s in sources}  # amostras já alinhadas (escritas + em buffer)
        self.written = start
        self.lock = threading.Lock()

    def add(self, source: str, t_start: float, pcm: np.ndarray):
        with self.lock:
            want = max(int(round(t_start * SR)), 0)
            if want > self.pos[source]:
                pad = np.zeros(want - self.pos[source], dtype=np.float32)
                self.bufs[source] = np.concatenate([self.bufs[source], pad])
                self.pos[source] = want
            self.bufs[source] = np.concatenate([self.bufs[source], pcm])
            self.pos[source] += len(pcm)

    def flush(self, upto_t: float):
        """Escreve até `upto_t` (s), preenchendo silêncio em tracks que pararam."""
        with self.lock:
            target = int(upto_t * SR)
            for s in self.bufs:
                if self.pos[s] < target:
                    self.bufs[s] = np.concatenate([self.bufs[s], np.zeros(target - self.pos[s], np.float32)])
                    self.pos[s] = target
            n = target - self.written
            if n <= 0:
                return
            out = np.zeros((n, 2), dtype=np.float32)
            for s, b in self.bufs.items():
                out[:, self.idx[s]] = b[:n]
                self.bufs[s] = b[n:]
            self.f.write(out)
            self.written += n

    def close(self, end_t: float):
        self.flush(end_t)
        self.f.close()

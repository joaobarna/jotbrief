"""Eco do microfone detectado pelo ÁUDIO: o mic captou o alto-falante (sem fone de ouvido).

O texto do Whisper difere entre os dois canais, mas o formato do volume ao longo do tempo é o mesmo: o envelope do
mic acompanha o da reunião (correlação alta) e o nível do mic é bem menor. Fala sua de verdade, mesmo por cima da
reunião, tem envelope diferente e nível bem maior (medido: eco 0,75–0,93 e RMS ≤ 0,0015; fala real 0,18 e RMS 0,013).
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

HOP_S = 0.02
MIN_CORR = 0.6          # correlação do envelope para considerar eco
LOOP_ACTIVE_RMS = 0.01  # a reunião precisa estar falando
QUIET_MIC_RMS = 0.003   # mic quase mudo enquanto a reunião fala: é só vazamento


def _env(x: np.ndarray, hop: int) -> np.ndarray:
    n = len(x) // hop
    return np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)


def echo_score(mic_env: np.ndarray, loop_env: np.ndarray, t0: float, t1: float, max_lag: int = 15):
    """(correlação, rms do mic, rms da reunião) no trecho [t0, t1], testando atrasos de até ±0,3 s."""
    a, b = int(t0 / HOP_S), int(t1 / HOP_S)
    m = mic_env[a:b]
    if len(m) < 10:
        return 0.0, float(m.mean()) if len(m) else 0.0, 0.0
    lm = np.log(m)
    best = -1.0
    for lag in range(-max_lag, max_lag + 1):
        seg = loop_env[max(a + lag, 0): b + lag]
        k = min(len(seg), len(lm))
        if k < 10:
            continue
        x, y = lm[:k], np.log(seg[:k])
        if x.std() == 0 or y.std() == 0:
            continue
        best = max(best, float(np.corrcoef(x, y)[0, 1]))
    return best, float(m.mean()), float(loop_env[a:b].mean()) if b > a else 0.0


class EnvelopeLog:
    """Envelope de volume dos dois canais ao vivo, para tirar o eco do microfone já durante a gravação."""

    SR = 16000

    def __init__(self):
        self._hop = int(self.SR * HOP_S)
        self._env = {"mic": np.zeros(0), "loop": np.zeros(0)}
        self._lock = threading.Lock()

    def add(self, name: str, t: float, pcm: np.ndarray) -> None:
        if name not in self._env:
            return
        vals = _env(np.asarray(pcm, dtype="float32").reshape(-1), self._hop)
        if not len(vals):
            return
        i = max(int(round(t / HOP_S)), 0)
        with self._lock:
            arr = self._env[name]
            if len(arr) < i + len(vals):
                arr = np.concatenate([arr, np.full(i + len(vals) - len(arr), 1e-6)])
            arr[i:i + len(vals)] = vals
            self._env[name] = arr

    def is_leak(self, t0: float, t1: float) -> bool:
        with self._lock:
            mic, loop = self._env["mic"].copy(), self._env["loop"].copy()
        n = min(len(mic), len(loop))
        if n < 10 or int(t1 / HOP_S) > n + 25:  # ainda sem áudio suficiente: não decide
            return False
        corr, mic_rms, loop_rms = echo_score(mic[:n], loop[:n], t0, min(t1, n * HOP_S))
        return is_leak_score(corr, mic_rms, loop_rms)


LEAK_MAX_MIC_RMS = 0.006  # acima disso é a SUA voz (medido: vazamento ≤ 0,002; fala sua ≥ 0,017), mesmo que o formato lembre o da reunião


def is_leak_score(corr: float, mic_rms: float, loop_rms: float) -> bool:
    return (loop_rms >= LOOP_ACTIVE_RMS and mic_rms < LEAK_MAX_MIC_RMS
            and (corr >= MIN_CORR or mic_rms < QUIET_MIC_RMS))


MISSING_MAX_COVERAGE = 0.5  # menos que isso do texto do mic existe no canal da reunião: é fala que só o mic pegou
MIN_CONCURRENT = 0.4        # e o Meet mostrou 2+ pessoas falando juntas em pelo menos esta fração da fala


def _missing_from_loop(rec: dict, records: list[dict]) -> bool:
    from .session import _words
    mw = _words(rec["text"])
    if len(mw) < 3:
        return False
    lw = {w for l in records if l.get("source") == "loop"
          and min(rec["t1"], l["t1"] + 1.5) - max(rec["t0"], l["t0"] - 1.5) > 0 for w in _words(l["text"])}
    return sum(1 for w in mw if w in lw) / len(mw) < MISSING_MAX_COVERAGE


def recover_overlapped(folder: Path, records: list[dict], leaks: list[dict]) -> int:
    """Quando duas pessoas falam juntas, o canal da reunião só transcreve a voz mais forte; a outra pode ter ficado só no
    vazamento do mic. Esses trechos voltam como fala da reunião — mas só se o Meet confirma 2+ pessoas falando juntas
    (senão é lixo de áudio fraco) e o texto não está no canal da reunião."""
    from . import meet_names
    events = meet_names.read_events(folder)
    if not events:
        return 0
    n = 0
    for r in leaks:
        if (_missing_from_loop(r, records)
                and meet_names.concurrent_share(events, r["t0"], r["t1"]) >= MIN_CONCURRENT):
            r["echo"] = False
            r["source"] = "loop"
            r["recovered"] = True
            r.pop("leak", None)
            who = meet_names.newcomer(events, r["t0"], r["t1"])
            if who:
                r["speaker"] = who
            n += 1
    if n:
        records.sort(key=lambda x: x["t0"])
    return n


def mark_echo_by_audio(folder: Path, records: list[dict]) -> int:
    """Marca echo=True nas falas do mic que são só o som da reunião vazando; retorna quantas marcou.

    Trechos que o Meet mostra como fala simultânea e que o canal da reunião não tem voltam como fala recuperada."""
    import soundfile as sf

    wav = Path(folder) / "audio.wav"
    mics = [r for r in records if r.get("source") == "mic"]  # inclui os já marcados: podem ser a 2ª pessoa falando junto
    if not mics or not wav.exists():
        return 0
    data, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    if data.shape[1] < 2:
        return 0
    hop = int(sr * HOP_S)
    mic_env, loop_env = _env(data[:, 0], hop), _env(data[:, 1], hop)
    n = 0
    leaks = []
    for r in mics:
        corr, mic_rms, loop_rms = echo_score(mic_env, loop_env, r["t0"], r["t1"])
        if is_leak_score(corr, mic_rms, loop_rms):
            r["echo"] = True
            r["leak"] = True
            leaks.append(r)
            n += 1
        elif r.get("leak"):
            r.pop("leak", None)
            r["echo"] = False  # a medição de agora diz que não era vazamento
        elif r.get("echo") and _missing_from_loop(r, records):
            r["echo"] = False  # escondida por engano: o volume é de voz sua e o texto não está na reunião
    try:
        n -= recover_overlapped(folder, records, leaks)
    except Exception:  # noqa: BLE001 - recuperar é um extra; o resto já está certo
        pass
    return n

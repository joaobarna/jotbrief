"""Reconhecer pessoas pela voz: 'impressões de voz' locais (vetores) das pessoas que você já nomeou.

Tudo fica no seu PC (%APPDATA%\\jotbrief\\voices.json). Apague o arquivo para esquecer todas as vozes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

VOICES_PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / "jotbrief" / "voices.json"
MIN_WINDOW_S = 1.0        # trechos mais curtos dão vetores pouco confiáveis
MAX_TOTAL_S = 40.0        # áudio usado por pessoa em cada reunião (as falas mais longas)
MAX_WINDOW_S = 20.0
MAX_WEIGHT_S = 600.0      # teto do "peso" de uma voz já aprendida (para ainda poder se ajustar)


def _unit(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ---------- cadastro (arquivo) ----------

def load_voices(path: Path | None = None) -> dict[str, dict]:
    """{'Ana': {'emb': [...], 'seconds': 55.0}}"""
    try:
        data = json.loads((path or VOICES_PATH).read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, dict) and v.get("emb")}
    except (OSError, ValueError, AttributeError):
        return {}


def _save(voices: dict[str, dict], path: Path | None) -> None:
    path = path or VOICES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(voices, ensure_ascii=False), encoding="utf-8")


def add_sample(name: str, emb: np.ndarray, seconds: float, path: Path | None = None) -> None:
    """Soma uma amostra (vetor de voz + segundos de fala) à impressão da pessoa (média ponderada)."""
    name = " ".join(name.split())
    if not name or seconds <= 0:
        return
    voices = load_voices(path)
    cur = voices.get(name)
    e = _unit(emb)
    if cur:
        old = _unit(np.array(cur["emb"]))
        w_old = min(float(cur.get("seconds", 0.0)), MAX_WEIGHT_S)
        merged = _unit(old * w_old + e * seconds)
        voices[name] = {"emb": merged.round(5).tolist(), "seconds": round(min(w_old + seconds, MAX_WEIGHT_S), 1)}
    else:
        voices[name] = {"emb": e.round(5).tolist(), "seconds": round(seconds, 1)}
    _save(voices, path)


def forget_voice(name: str, path: Path | None = None) -> bool:
    voices = load_voices(path)
    keys = [k for k in voices if k.casefold() == " ".join(name.split()).casefold()]
    for k in keys:
        del voices[k]
    if keys:
        _save(voices, path)
    return bool(keys)


# ---------- comparação (pura, testável) ----------

def similarities(emb: np.ndarray, voices: dict[str, dict]) -> dict[str, float]:
    e = _unit(emb)
    return {n: float(np.dot(e, _unit(np.array(v["emb"])))) for n, v in voices.items()}


def match(emb: np.ndarray, voices: dict[str, dict], threshold: float = 0.75, margin: float = 0.05) -> tuple[str, float] | None:
    """Pessoa cadastrada mais parecida, se passar do limiar e ganhar da segunda por `margin`."""
    sims = sorted(similarities(emb, voices).items(), key=lambda kv: kv[1], reverse=True)
    if not sims or sims[0][1] < threshold:
        return None
    if len(sims) > 1 and sims[0][1] - sims[1][1] < margin:
        return None
    return sims[0]


def assign_names(cluster_embs: dict[int, np.ndarray], voices: dict[str, dict], threshold: float = 0.75,
                 margin: float = 0.05) -> dict[int, tuple[str, float]]:
    """Nome para cada voz separada da reunião.

    O mesmo nome pode valer para mais de uma voz: o app às vezes divide uma pessoa em duas, e cada uma só
    precisa parecer com a voz cadastrada.
    """
    out: dict[int, tuple[str, float]] = {}
    for sid, emb in cluster_embs.items():
        m = match(emb, voices, threshold, margin)
        if m:
            out[sid] = m
    return out


# ---------- vetores a partir do áudio ----------

def embed_windows(right: np.ndarray, sr: int, windows: list[tuple[float, float]],
                  max_total: float = MAX_TOTAL_S) -> tuple[np.ndarray, float] | None:
    """Vetor médio (ponderado pela duração) da voz nos trechos `windows` do canal `right`; e os segundos usados.

    Usa as falas mais longas até `max_total` segundos. None se não há áudio suficiente.
    """
    from .speakers import _extractor

    ws = sorted((w for w in windows if w[1] - w[0] >= MIN_WINDOW_S), key=lambda w: w[1] - w[0], reverse=True)
    if not ws:
        return None
    ex = _extractor()
    acc, secs = None, 0.0
    for a, b in ws:
        if secs >= max_total:
            break
        b = min(b, a + MAX_WINDOW_S)
        wav = np.ascontiguousarray(right[int(a * sr):int(b * sr)], dtype=np.float32)
        if len(wav) < int(MIN_WINDOW_S * sr) or float(np.abs(wav).max()) < 1e-4:
            continue
        s = ex.create_stream()
        s.accept_waveform(sample_rate=sr, waveform=wav)
        s.input_finished()
        v = _unit(np.array(ex.compute(s), dtype=np.float64))
        d = b - a
        acc = v * d if acc is None else acc + v * d
        secs += d
    if acc is None:
        return None
    return _unit(acc), secs


def learnable_label(label: str) -> bool:
    """Rótulos do canal da reunião de onde dá para aprender uma voz: 'Pessoa N' ou 'Reunião' (sem identificar)."""
    return label.lower().startswith("pessoa") or label.strip().lower() in {"reunião", "reuniao"}


def learn_from_meeting(folder: Path, label: str, name: str, path: Path | None = None) -> float:
    """Aprende a voz de `name` a partir das falas de `label` ('Pessoa 2') nesta reunião. Retorna os segundos usados."""
    import soundfile as sf

    from . import speakers
    from .session import clean_records, read_jsonl

    folder = Path(folder)
    if not learnable_label(label) or not speakers.has_model() or not (folder / "audio.wav").exists():
        return 0.0
    unlabeled = not label.lower().startswith("pessoa")  # 'Reunião': as falas do outro lado sem rótulo de pessoa
    recs = [r for r in clean_records(read_jsonl(folder / "transcricao.jsonl"))
            if r["source"] == "loop" and (not r.get("speaker") if unlabeled else r.get("speaker") == label)]
    if not recs:
        return 0.0
    data, sr = sf.read(str(folder / "audio.wav"), dtype="float32", always_2d=True)
    if data.shape[1] < 2:
        return 0.0
    got = embed_windows(data[:, 1], sr, [(r["t0"], r["t1"]) for r in recs])
    if not got:
        return 0.0
    emb, secs = got
    add_sample(name, emb, secs, path)
    return secs

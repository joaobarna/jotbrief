"""Helpers da UI sem dependência de Qt (testáveis)."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

STAMP = "%Y-%m-%d_%H%M"
STAMP_SECONDS = "%Y-%m-%d_%H%M%S"  # usado quando já existe uma reunião começada no mesmo minuto


def parse_stamp(name: str) -> datetime | None:
    for fmt in (STAMP, STAMP_SECONDS):
        try:
            return datetime.strptime(name, fmt)
        except ValueError:
            continue
    return None


WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def group_label(d: date, today: date) -> str:
    """Rótulo do dia: 'Hoje · 2026-09-29', 'Ontem · 2026-09-28' ou 'Segunda · 2026-09-22'."""
    delta = (today - d).days
    if delta <= 0:
        return f"Hoje · {d:%Y-%m-%d}"
    if delta == 1:
        return f"Ontem · {d:%Y-%m-%d}"
    return f"{WEEKDAYS[d.weekday()]} · {d:%Y-%m-%d}"


def group_by_day(folders: list[Path], today: date | None = None) -> list[tuple[str, list[Path]]]:
    """Agrupa pastas AAAA-MM-DD_HHMM por dia (um grupo por dia), do mais recente ao mais antigo."""
    today = today or date.today()
    groups: dict[date | None, list[Path]] = {}
    for f in sorted(folders, key=lambda p: p.name, reverse=True):
        dt = parse_stamp(f.name)
        groups.setdefault(dt.date() if dt else None, []).append(f)
    days = sorted((d for d in groups if d is not None), reverse=True)
    out = [(group_label(d, today), groups[d]) for d in days]
    if None in groups:
        out.append(("Outras", groups[None]))
    return out


def clean_subject(s: str, limit: int = 80) -> str:
    s = " ".join(s.replace("|", "-").split()).strip(" .\"'")
    return s[:limit].rstrip() or "Sem assunto"


def call_title(folder_name: str, subject: str) -> str:
    """'YYYY-MM-DD | hh:mm | Assunto' — data e hora do início da call (nome da pasta)."""
    dt = parse_stamp(folder_name)
    when = dt.strftime("%Y-%m-%d | %H:%M") if dt else folder_name
    return f"{when} | {clean_subject(subject)}"


def read_meta(folder: Path) -> dict:
    import json
    try:
        return json.loads((Path(folder) / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_meta(folder: Path, **updates) -> None:
    import json
    meta = read_meta(folder)
    meta.update(updates)
    (Path(folder) / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def read_subject(folder: Path) -> str | None:
    return read_meta(folder).get("subject") or None


def write_subject(folder: Path, subject: str) -> None:
    write_meta(folder, subject=clean_subject(subject))


def read_parts(folder: Path) -> list[dict]:
    """Partes (cada vez que a gravação foi iniciada/retomada): [{'start': segundos, 'at': 'HH:MM'}]."""
    parts: list[dict] = []
    for p in read_meta(folder).get("parts") or []:
        if parts and abs(parts[-1]["start"] - p["start"]) < 0.5:
            parts[-1] = p  # gravação parada e reiniciada logo em seguida: fica só a última
        else:
            parts.append(p)
    return parts


def add_part(folder: Path, start: float, at: str) -> list[dict]:
    """Registra o início de uma nova parte. Reuniões antigas (sem partes) ganham a parte 1 retroativa."""
    parts = read_parts(folder)
    if not parts and start > 0:
        dt = parse_stamp(Path(folder).name)
        parts.append({"start": 0.0, "at": dt.strftime("%H:%M") if dt else "--:--"})
    new = {"start": round(float(start), 2), "at": at}
    if parts and abs(parts[-1]["start"] - new["start"]) < 0.5:
        parts[-1] = new
    else:
        parts.append(new)
    write_meta(folder, parts=parts)
    return parts


def build_items(records: list[dict], parts: list[dict], duration: float) -> list[tuple]:
    """Intercala separadores entre as partes: ('sep', idx, label, start, end) e ('utt', registro).

    Sem separadores se houver 0 ou 1 parte.
    """
    records = sorted(records, key=lambda r: r["t0"])
    if len(parts) < 2:
        return [("utt", r) for r in records]
    items: list[tuple] = []
    for i, p in enumerate(parts):
        end = parts[i + 1]["start"] if i + 1 < len(parts) else max(duration, p["start"])
        items.append(("sep", i, f"Parte {i + 1} · {p['at']}", p["start"], end))
        items += [("utt", r) for r in records if p["start"] - 0.05 <= r["t0"] < end - 0.05
                  or (i == 0 and r["t0"] < p["start"])
                  or (i + 1 == len(parts) and r["t0"] >= end - 0.05)]
    return items


def pretty_name(name: str) -> str:
    dt = parse_stamp(name)
    return dt.strftime("%d/%m às %H:%M") if dt else name


def playable_wav(folder: Path, cache_dir: Path | None = None) -> Path | None:
    """WAV mono (mic + reunião somados e normalizados) para escutar; o original é estéreo (L=mic, R=reunião).

    Guardado no diretório temporário e refeito só se o áudio original mudou.
    """
    import tempfile

    import numpy as np
    import soundfile as sf

    src = Path(folder) / "audio.wav"
    if not src.exists():
        return None
    cache_dir = cache_dir or Path(tempfile.gettempdir()) / "jotbrief-play"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{Path(folder).name}.norm.wav"
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    # 1ª passada: pico do mix mono; 2ª: normaliza p/ ~0,9 (gravações do mic saem baixas; ganho máx. 10x)
    peak = 0.0
    with sf.SoundFile(str(src)) as f:
        for block in f.blocks(blocksize=1 << 20, dtype="float32"):
            mono = block.mean(axis=1) if block.ndim > 1 else block
            if len(mono):
                peak = max(peak, float(np.abs(mono).max()))
    gain = min(0.9 / peak, 10.0) if peak > 1e-4 else 1.0
    with sf.SoundFile(str(src)) as f, sf.SoundFile(str(out), "w", samplerate=f.samplerate,
                                                   channels=1, subtype="PCM_16") as o:
        for block in f.blocks(blocksize=1 << 20, dtype="float32"):
            mono = block.mean(axis=1) if block.ndim > 1 else block
            o.write(np.clip(mono * gain, -1.0, 1.0))
    return out


def word_timings(rec: dict) -> list[tuple[float, float, str]]:
    """(início, fim, palavra) de cada palavra da fala: tempos reais se gravados; senão, estimados
    pelo tamanho das palavras dentro de [t0, t1]."""
    if rec.get("words"):
        return [(float(a), float(b), w) for a, b, w in rec["words"]]
    words = rec["text"].split()
    if not words:
        return []
    total = sum(len(w) + 1 for w in words)
    t, span, out = float(rec["t0"]), max(float(rec["t1"]) - float(rec["t0"]), 0.1), []
    for w in words:
        d = span * (len(w) + 1) / total
        out.append((t, t + d, w))
        t += d
    return out


def active_word(timings: list[tuple[float, float, str]], sec: float) -> int:
    """Índice da palavra em curso em `sec` (a última que já começou); -1 se ainda não começou."""
    idx = -1
    for i, (a, _b, _w) in enumerate(timings):
        if a <= sec:
            idx = i
        else:
            break
    return idx


def read_names(folder: Path) -> dict[str, str]:
    """Nomes dados às pessoas da reunião: {'Pessoa 1': 'Carlos', 'Eu': 'Marcos'}."""
    names = read_meta(folder).get("names") or {}
    return {k: v for k, v in names.items() if isinstance(k, str) and isinstance(v, str) and v.strip()}


def write_names(folder: Path, names: dict[str, str]) -> None:
    """Salva os nomes (vazio = volta ao rótulo original)."""
    clean = {k: " ".join(v.split()) for k, v in names.items() if v and v.strip() and v.strip() != k}
    write_meta(folder, names=clean)


def read_auto_names(folder: Path) -> list[str]:
    """Rótulos ('Pessoa 2') cujo nome foi dado pelo reconhecimento de voz, não por você."""
    return [x for x in (read_meta(folder).get("auto_names") or []) if isinstance(x, str)]


def apply_auto_names(folder: Path, found: dict[str, str]) -> None:
    """Aplica nomes reconhecidos pela voz sem passar por cima dos que você definiu.

    Nomes automáticos antigos são refeitos; os manuais (que você digitou) ficam.
    """
    names = dict(read_meta(folder).get("names") or {})
    for label in read_auto_names(folder):
        names.pop(label, None)
    auto = []
    for label, name in found.items():
        if label not in names:
            names[label] = name
            auto.append(label)
    write_meta(folder, names=names, auto_names=auto)


def mark_manual(folder: Path, labels: list[str]) -> None:
    """O nome foi definido/corrigido por você: deixa de ser 'reconhecido automaticamente'."""
    auto = [a for a in read_auto_names(folder) if a not in labels]
    write_meta(folder, auto_names=auto)

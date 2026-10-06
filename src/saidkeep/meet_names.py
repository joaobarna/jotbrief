"""Nomes das pessoas a partir de quem o Google Meet mostrou como 'falando' (extensão do Chrome).

A extensão avisa o app quando alguém começa/para de falar; o app carimba com o tempo da gravação em
`falantes_meet.jsonl` ({"t": seg, "name": "Ana", "on": true}). Depois cruzamos com as vozes separadas (Pessoa N).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

FILE = "falantes_meet.jsonl"
SELF_NAMES = {"você", "voce", "you", "eu", "me"}  # o Meet chama a própria pessoa assim; o mic já é o 'Eu'


def clean_name(name: str) -> str:
    n = " ".join(str(name).split())
    for suf in ("(Você)", "(voce)", "(You)", "(você)"):
        n = n.replace(suf, "").strip()
    return n


def is_self(name: str) -> bool:
    return clean_name(name).lower() in SELF_NAMES or not clean_name(name)


_WRITE_LOCK = threading.Lock()  # o servidor local atende vários avisos ao mesmo tempo


def append_event(folder: Path, t: float, name: str, on: bool) -> None:
    line = json.dumps({"t": round(t, 2), "name": clean_name(name), "on": bool(on)}, ensure_ascii=False) + "\n"
    with _WRITE_LOCK, open(Path(folder) / FILE, "a", encoding="utf-8") as f:
        f.write(line)


def read_events(folder: Path) -> list[dict]:
    out = []
    try:
        for ln in (Path(folder) / FILE).read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(ln)
                if isinstance(e.get("t"), (int, float)) and e.get("name"):
                    out.append(e)
            except ValueError:
                continue
    except OSError:
        return []
    return sorted(out, key=lambda e: e["t"])


def solo_intervals(events: list[dict], end: float) -> dict[str, list[tuple[float, float]]]:
    """Trechos em que UMA só pessoa (que não é você) estava marcada como falando: só esses servem para cruzar."""
    active: set[str] = set()
    out: dict[str, list[tuple[float, float]]] = {}
    last = 0.0

    def close(upto: float):
        if len(active) == 1 and upto > last:
            (who,) = tuple(active)
            out.setdefault(who, []).append((last, upto))

    for e in events:
        close(e["t"])
        last = e["t"]
        if is_self(e["name"]):
            continue
        (active.add if e.get("on") else active.discard)(e["name"])
    close(end)
    return out


def live_speaker(events: list[dict], t0: float, t1: float, min_seconds: float = 1.0) -> str | None:
    """Quem o Meet mostrou falando SOZINHO durante a fala [t0, t1] (para rotular ao vivo); None se não deu para saber."""
    best, secs = None, 0.0
    for name, ivs in solo_intervals(events, t1).items():
        ov = sum(max(0.0, min(t1, b) - max(t0, a)) for a, b in ivs)
        if ov > secs:
            best, secs = name, ov
    return best if best and secs >= min(min_seconds, 0.5 * (t1 - t0)) else None


def concurrent_share(events: list[dict], t0: float, t1: float) -> float:
    """Fração da fala [t0, t1] em que DUAS ou mais pessoas (fora você) estavam marcadas falando no Meet."""
    if t1 <= t0:
        return 0.0
    active: set[str] = set()
    last, both = 0.0, 0.0
    for e in sorted(events, key=lambda e: e["t"]) + [{"t": t1 + 1, "name": "", "on": False}]:
        a, b = max(last, t0), min(e["t"], t1)
        if len(active) >= 2 and b > a:
            both += b - a
        last = e["t"]
        if e["name"] and not is_self(e["name"]):
            (active.add if e.get("on") else active.discard)(e["name"])
    return both / (t1 - t0)


def newcomer(events: list[dict], t0: float, t1: float) -> str | None:
    """Entre quem estava falando em [t0, t1], quem COMEÇOU por último (quem entrou por cima da outra pessoa)."""
    start: dict[str, float] = {}
    on_now: set[str] = set()
    for e in sorted(events, key=lambda e: e["t"]):
        if e["t"] > t1 or not e["name"] or is_self(e["name"]):
            continue
        if e.get("on"):
            if e["name"] not in on_now:
                start[e["name"]] = e["t"]
            on_now.add(e["name"])
        else:
            on_now.discard(e["name"])
    active = [n for n in on_now if n in start]
    if len(active) < 2:
        return None
    return max(active, key=lambda n: start[n])


def match_labels(records: list[dict], events: list[dict], min_seconds: float = 3.0,
                 min_share: float = 0.6) -> dict[str, str]:
    """{'Pessoa 2': 'Ana'}: o nome do Meet que mais coincide no tempo com cada voz separada."""
    if not events:
        return {}
    end = max([r["t1"] for r in records] + [e["t"] for e in events], default=0.0)
    solos = solo_intervals(events, end)
    per: dict[str, dict[str, float]] = {}
    for r in records:
        label = r.get("speaker")
        if r.get("source") != "loop" or not label:
            continue
        for name, ivs in solos.items():
            ov = sum(max(0.0, min(r["t1"], b) - max(r["t0"], a)) for a, b in ivs)
            if ov > 0:
                per.setdefault(label, {})[name] = per.setdefault(label, {}).get(name, 0.0) + ov
    found: dict[str, str] = {}
    for label, by_name in per.items():
        total = sum(by_name.values())
        name, secs = max(by_name.items(), key=lambda kv: kv[1])
        if secs >= min_seconds and secs / total >= min_share:
            found[label] = name
    # dois rótulos com o mesmo nome: vale o de mais tempo (o outro fica sem nome automático)
    best: dict[str, tuple[float, str]] = {}
    for label, name in found.items():
        secs = per[label][name]
        if name not in best or secs > best[name][0]:
            best[name] = (secs, label)
    return {label: name for name, (_s, label) in best.items()}


def apply_meet_names(folder: Path, learn: bool = True) -> dict[str, str]:
    """Dá às 'Pessoa N' o nome visto no Meet, sem passar por cima dos nomes que você digitou. Retorna o que aplicou."""
    from .session import clean_records, read_jsonl
    from .ui_helpers import read_auto_names, read_meta, write_meta

    folder = Path(folder)
    events = read_events(folder)
    if not events:
        return {}
    records = clean_records(read_jsonl(folder / "transcricao.jsonl"))
    found = match_labels(records, events)
    if not found:
        return {}
    meta = read_meta(folder)
    names = dict(meta.get("names") or {})
    auto = read_auto_names(folder)
    applied: dict[str, str] = {}
    for label, name in found.items():
        if label in names and label not in auto:
            continue  # definido por você
        names[label] = name
        if label not in auto:
            auto.append(label)
        applied[label] = name
    write_meta(folder, names=names, auto_names=auto)
    if learn:  # a voz já fica aprendida: nas próximas reuniões o reconhecimento funciona sem a extensão
        from .voices import learn_from_meeting
        for label, name in applied.items():
            try:
                learn_from_meeting(folder, label, name)
            except Exception:  # noqa: BLE001 - aprender nunca pode atrapalhar
                pass
    return applied

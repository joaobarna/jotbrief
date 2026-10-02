"""Cadastro de pessoas: os nomes que você já deu em qualquer reunião, para escolher de novo em vez de digitar."""
from __future__ import annotations

import json
import os
from pathlib import Path

PEOPLE_PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / "jotbrief" / "people.json"
MAX_PEOPLE = 200


def is_auto_label(name: str) -> bool:
    """Rótulos automáticos do app (não são nomes de pessoas)."""
    n = name.strip().lower()
    return not n or n in {"eu", "reunião", "reuniao"} or n.startswith("pessoa ")


def _clean(name: str) -> str:
    return " ".join(str(name).split())


def _read(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [_clean(x) for x in data if isinstance(x, str) and not is_auto_label(_clean(x))]
    except (OSError, ValueError, TypeError):
        return []


def _dedupe(names: list[str]) -> list[str]:
    seen, out = set(), []
    for n in names:
        k = n.casefold()
        if n and k not in seen:
            seen.add(k)
            out.append(n)
    return out


def names_in_meetings(root: Path | None) -> list[str]:
    """Nomes já usados nas reuniões salvas (mais recentes primeiro)."""
    from .ui_helpers import read_names

    if not root or not Path(root).exists():
        return []
    out: list[str] = []
    for d in sorted((p for p in Path(root).iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True):
        out += [v for v in read_names(d).values() if not is_auto_label(v)]
    return out


def load_people(root: Path | None = None, path: Path = PEOPLE_PATH) -> list[str]:
    """Lista para escolher: o que você usou por último primeiro, depois nomes só encontrados nas reuniões."""
    return _dedupe(_read(path) + [_clean(n) for n in names_in_meetings(root)])


def remember(name: str, path: Path = PEOPLE_PATH) -> None:
    """Guarda o nome no cadastro (vai para o topo). Ignora vazio e rótulos automáticos."""
    name = _clean(name)
    if is_auto_label(name):
        return
    names = _dedupe([name] + _read(path))[:MAX_PEOPLE]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # cadastro é conveniência: não pode atrapalhar salvar o nome na reunião


def forget(name: str, path: Path = PEOPLE_PATH) -> None:
    """Tira um nome do cadastro (não mexe nas reuniões que já o usam)."""
    keep = [n for n in _read(path) if n.casefold() != _clean(name).casefold()]
    try:
        path.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass

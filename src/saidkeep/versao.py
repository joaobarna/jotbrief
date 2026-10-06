"""Versão do app no formato do JB Ladder: data/hora do commit em Brasília (YYYY.MM.DD.HH.mm), com o histórico embutido."""
from __future__ import annotations

import json
from pathlib import Path

CHANGELOG = Path(__file__).parent / "data" / "changelog.json"


def entradas() -> list[dict]:
    """[{'versao': '2026.10.02.12.30', 'titulo': '…', 'hash': 'abc1234'}], da mais nova para a mais antiga."""
    try:
        data = json.loads(CHANGELOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in data if isinstance(e, dict) and e.get("versao") and e.get("titulo")]


def atual() -> str:
    e = entradas()
    return e[0]["versao"] if e else "dev"

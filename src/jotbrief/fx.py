"""Cotação do dólar em reais (para mostrar o custo do Claude em BRL). Fontes públicas, sem chave; com cache."""
from __future__ import annotations

import json
import os
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

CACHE = Path(os.environ.get("APPDATA", Path.home())) / "jotbrief" / "cotacao.json"
TTL = 3600  # 1 h: o app busca de novo depois disso


def _get(url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "jotbrief"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - API pública de cotação
        return json.loads(r.read().decode("utf-8"))


def _awesome() -> float:  # cotação comercial em tempo real
    return float(_get("https://economia.awesomeapi.com.br/json/last/USD-BRL")["USDBRL"]["bid"])


def _frankfurter() -> float:  # taxa de referência diária do Banco Central Europeu
    return float(_get("https://api.frankfurter.app/latest?from=USD&to=BRL")["rates"]["BRL"])


SOURCES: list[tuple[str, Callable[[], float]]] = [("AwesomeAPI", _awesome), ("Frankfurter/BCE", _frankfurter)]


def cached(path: Path = CACHE) -> dict | None:
    """Última cotação guardada: {'rate': 5.23, 'at': epoch, 'source': '...'} (None se nunca buscou)."""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if float(d["rate"]) > 0 else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def refresh(path: Path = CACHE, force: bool = False, sources=None, now: Callable[[], float] = time.time) -> dict | None:
    """Busca a cotação atual (se a guardada tem mais de 1 h) e guarda. Em falha de rede, devolve a última guardada."""
    old = cached(path)
    if old and not force and now() - float(old.get("at", 0)) < TTL:
        return old
    for name, fn in sources or SOURCES:
        try:
            rate = fn()
        except Exception:  # noqa: BLE001 - tenta a próxima fonte
            continue
        if 1.0 < rate < 50.0:  # sanidade: dólar em reais
            d = {"rate": rate, "at": now(), "source": name}
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(d), encoding="utf-8")
            except OSError:
                pass
            return d
    return old


def fmt_brl(usd: float, rate: float) -> str:
    return f"R$ {usd * rate:.2f}".replace(".", ",")

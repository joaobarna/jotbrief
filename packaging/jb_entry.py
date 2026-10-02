"""Ponto de entrada do executável (PyInstaller). Sem argumentos abre a janela; com argumentos roda o subcomando
(`identify`, `mcp`, …) — é assim que o app chama a si mesmo em outro processo."""
import os
import sys
from pathlib import Path


def _fix_streams() -> None:
    """Executável sem console: stdout/stderr vêm vazios; manda para um arquivo de log para nada quebrar."""
    if sys.stdout is None or sys.stderr is None:
        log = Path(os.environ.get("APPDATA", ".")) / "jotbrief" / "app-stderr.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        f = open(log, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or f
        sys.stderr = sys.stderr or f


if __name__ == "__main__":
    _fix_streams()
    from jotbrief.__main__ import main

    if len(sys.argv) == 1:
        sys.argv.append("gui")
    sys.exit(main())

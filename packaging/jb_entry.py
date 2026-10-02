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

    gui = len(sys.argv) == 1
    if gui:
        sys.argv.append("gui")
    code = 1
    try:
        code = main() or 0
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        if not gui:  # comandos de terminal (identify, setup, selftest…) terminam mesmo com threads de fundo vivas
            for stream in (sys.stdout, sys.stderr):
                try:
                    stream.flush()
                except Exception:  # noqa: BLE001
                    pass
            os._exit(code)
    sys.exit(code)

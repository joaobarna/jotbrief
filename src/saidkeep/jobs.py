"""Tarefas pesadas fora do app: rodam num processo separado para a janela nunca travar."""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path


def run_identify(folder: Path, people: int = 0, on_status: Callable[[str], None] | None = None) -> int:
    """Identifica os falantes de `folder` (saidkeep identify) e retorna o nº de pessoas; levanta RuntimeError se falhar.

    A separação de vozes é código nativo que segura o interpretador por ~1 min em 9 min de áudio; dentro do app isso
    congelava a janela. Num processo à parte, a interface continua respondendo.
    """
    from .runtime import app_command
    cmd = app_command("identify", str(Path(folder).resolve()), "--people", str(int(people)))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", creationflags=flags)
    n, error = 0, ""
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("STATUS ") and on_status:
            on_status(line[7:])
        elif line.startswith("RESULT "):
            n = int(line[7:] or 0)
        elif line.startswith("ERROR "):
            error = line[6:]
    code = proc.wait()
    if error or code != 0:
        raise RuntimeError(error or f"o processo terminou com código {code}")
    return n

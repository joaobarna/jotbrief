"""Registra o servidor MCP do JB no claude_desktop_config.json (com backup), sem depender de UI."""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SERVER_NAME = "jotbrief"


def config_paths() -> list[Path]:
    """Onde o Claude Desktop lê a configuração.

    A versão da Microsoft Store guarda uma cópia PRIVADA em Packages\\Claude_*\\LocalCache\\Roaming\\Claude, e é
    ela que o app lê; a versão comum usa %APPDATA%\\Claude.
    """
    local = os.environ.get("LOCALAPPDATA", "")
    pkg = sorted(glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude",
                                        "claude_desktop_config.json")))
    if pkg:
        return [Path(p) for p in pkg]
    return [Path(os.environ.get("APPDATA", str(Path.home()))) / "Claude" / "claude_desktop_config.json"]


def claude_running() -> bool:
    """O Claude Desktop reescreve a configuração ao fechar/salvar; editar com ele aberto perde a alteração."""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Claude.exe", "/NH"], capture_output=True, text=True,
                             timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "claude.exe" in out.lower()


def server_entry(python_exe: str | None = None) -> dict:
    if python_exe:
        return {"command": python_exe, "args": ["-m", "jotbrief", "mcp"]}
    from .runtime import app_command
    cmd = app_command("mcp")  # no app instalado o próprio executável faz o papel do servidor
    return {"command": cmd[0], "args": cmd[1:]}


def install(path: Path, python_exe: str | None = None) -> Path | None:
    """Adiciona mcpServers.jotbrief, preservando o resto. Retorna o caminho do backup (None se o arquivo era novo)."""
    path = Path(path)
    data: dict = {}
    backup = None
    indent = 2
    if path.exists():
        raw = path.read_text(encoding="utf-8-sig")
        data = json.loads(raw) if raw.strip() else {}
        indent = 4 if raw.lstrip().startswith("{\n    ") else 2
        backup = path.with_name(f"{path.stem}.backup-{datetime.now():%Y%m%d-%H%M%S}.json")
        shutil.copy2(path, backup)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    data.setdefault("mcpServers", {})[SERVER_NAME] = server_entry(python_exe)
    path.write_text(json.dumps(data, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8")
    return backup


def is_installed(path: Path) -> bool:
    try:
        return SERVER_NAME in (json.loads(Path(path).read_text(encoding="utf-8-sig")).get("mcpServers") or {})
    except (OSError, ValueError):
        return False

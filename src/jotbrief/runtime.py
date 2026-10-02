"""Onde o app está rodando: do código-fonte (uv run) ou instalado (PyInstaller). Um lugar só para essas diferenças."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True no app instalado (executável gerado pelo PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def app_command(*args: str) -> list[str]:
    """Comando para rodar um subcomando do próprio app em outro processo (`identify`, `mcp`, …)."""
    if is_frozen():
        return [sys.executable, *args]           # o executável já é o app
    return [sys.executable, "-m", "jotbrief", *args]


def data_dir() -> Path:
    """Dados do app (configuração, vozes, modelos, cotação): %APPDATA%\\jotbrief."""
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "jotbrief"


def user_files_dir() -> Path:
    """Arquivos que são do usuário (reuniões, skills): Documentos\\JB - Jot Brief no app instalado."""
    return Path.home() / "Documents" / "JB - Jot Brief"


def cuda_dir() -> Path:
    """Onde ficam as bibliotecas CUDA baixadas na 1ª vez que há uma placa NVIDIA (o instalador não as inclui: ~2 GB)."""
    return data_dir() / "cuda"


def default_output_dir() -> Path:
    """Pasta das reuniões: `reunioes` ao lado do projeto no código-fonte; em Documentos no app instalado."""
    return user_files_dir() / "reunioes" if is_frozen() else Path("reunioes")


def project_root() -> Path:
    """Raiz do projeto (só faz sentido no código-fonte)."""
    return Path(__file__).resolve().parents[2]


def dll_search_dirs() -> list[Path]:
    """Pastas onde procurar as DLLs CUDA (cublas/cudnn): pacotes pip, ao lado do executável e a pasta baixada."""
    roots = [Path(p) for p in sys.path] + [cuda_dir()]
    if is_frozen():
        roots += [Path(sys.executable).parent, Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()]
    out = []
    for base in roots:
        for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin"):
            d = base / sub
            if d.is_dir() and d not in out:
                out.append(d)
    return out

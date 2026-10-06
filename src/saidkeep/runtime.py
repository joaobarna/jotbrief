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
    return [sys.executable, "-m", "saidkeep", *args]


# Nomes antigos do app (antes era "JB - Jot Brief"): só aparecem aqui, para migrar os dados de quem já usava.
LEGACY_DATA_DIRNAME = "jotbrief"
LEGACY_DOCS_DIRNAME = "JB - Jot Brief"


def data_dir() -> Path:
    """Dados do app (configuração, vozes, modelos, cotação): %APPDATA%\\saidkeep."""
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "saidkeep"


def user_files_dir() -> Path:
    """Arquivos que são do usuário (reuniões, skills): Documentos\\SaidKeep no app instalado."""
    return Path.home() / "Documents" / "SaidKeep"


def legacy_data_dir() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home()))) / LEGACY_DATA_DIRNAME


def legacy_user_files_dir() -> Path:
    return Path.home() / "Documents" / LEGACY_DOCS_DIRNAME


def _merge_move(old: Path, new: Path) -> str | None:
    """Move `old` para `new`. Se `new` já existe (o app novo chegou a criar a pasta), move só o que ainda não está lá."""
    import shutil

    if not old.exists():
        return None
    if not new.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)                                   # mesma unidade: instantâneo, mesmo com 2 GB de bibliotecas CUDA
        return f"{old} -> {new}"
    moved = []
    for child in sorted(old.iterdir()):
        target = new / child.name
        if not target.exists():
            shutil.move(str(child), str(target))
            moved.append(child.name)
    for child in list(old.iterdir()):
        if child.is_file() and child.suffix == ".log":    # log repetido do app antigo: não vale guardar
            try:
                child.unlink()
            except OSError:
                pass
    try:
        old.rmdir()                                       # só some se ficou vazia
    except OSError:
        pass
    return f"{old} -> {new} (mesclado: {', '.join(moved) or 'nada novo'})"


def migrate_legacy() -> list[str]:
    """1ª abertura depois da troca de nome: leva %APPDATA%\\jotbrief e Documentos\\JB - Jot Brief para os nomes novos.

    Seguro repetir (nada a fazer na 2ª vez) e nunca levanta erro: se algo estiver em uso, o app segue e tenta de novo
    na próxima abertura."""
    done = []
    if os.environ.get("SAIDKEEP_NO_MIGRATE"):             # desenvolvimento/testes: não mexe nos dados reais
        return done
    for old, new in ((legacy_data_dir(), data_dir()), (legacy_user_files_dir(), user_files_dir())):
        try:
            msg = _merge_move(old, new)
        except OSError:
            continue
        if msg:
            done.append(msg)
    if done:
        _fix_config_paths(data_dir() / "config.toml")
    return done


def _fix_config_paths(config: Path) -> None:
    """O config.toml pode guardar o caminho da pasta antiga de reuniões: reescreve para a nova."""
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return
    old, new = legacy_user_files_dir(), user_files_dir()
    fixed = text
    for a, b in ((old.as_posix(), new.as_posix()), (str(old).replace("\\", "\\\\"), str(new).replace("\\", "\\\\"))):
        fixed = fixed.replace(a, b)
    if fixed != text:
        config.write_text(fixed, encoding="utf-8", newline="\n")


def rewrite_legacy_path(p: Path) -> Path:
    """Caminho que ainda aponta para a pasta antiga de Documentos (guardado no config.toml) → pasta nova."""
    old = legacy_user_files_dir()
    try:
        rel = p.relative_to(old)
    except ValueError:
        return p
    return user_files_dir() / rel


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

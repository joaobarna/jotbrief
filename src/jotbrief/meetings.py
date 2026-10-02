"""Acesso somente-leitura às reuniões salvas (sem Qt): usado pelo servidor MCP e testável sozinho."""
from __future__ import annotations

from pathlib import Path

from .config import Config
from .prompts import build_message
from .session import read_jsonl, render_transcript, transcript_meta
from .ui_helpers import call_title, parse_stamp, read_names, read_parts, read_subject

LATEST = {"", "latest", "ultima", "última", "last"}


def default_root(cfg: Config | None = None) -> Path:
    """Pasta das reuniões. Relativa → a partir da raiz do projeto (o servidor MCP roda de outro diretório)."""
    cfg = cfg or Config.load()
    root = Path(cfg.output_dir)
    if not root.is_absolute():
        from .runtime import project_root
        root = project_root() / root
    return root


def meeting_dirs(root: Path) -> list[Path]:
    """Reuniões (pastas com transcrição), da mais recente para a mais antiga."""
    if not root.exists():
        return []
    return sorted((d for d in root.iterdir() if d.is_dir() and (d / "transcricao.jsonl").exists()),
                  key=lambda d: d.name, reverse=True)


def summary(folder: Path) -> dict:
    recs = read_jsonl(folder / "transcricao.jsonl")
    names = read_names(folder)
    meta = transcript_meta(recs, names)
    return {"id": folder.name, "title": call_title(folder.name, read_subject(folder) or ""),
            "falas": len(recs), "meta": meta}


def resolve(root: Path, meeting: str = "latest") -> Path:
    """'latest' (a mais recente), o id exato (nome da pasta), um prefixo (ex.: '2026-09-29') ou um trecho do assunto.

    Só aceita reuniões dentro da pasta de reuniões (nada de caminhos livres).
    """
    dirs = meeting_dirs(root)
    if not dirs:
        raise ValueError("Nenhuma reunião salva ainda.")
    q = (meeting or "").strip().lower()
    if q in LATEST:
        return dirs[0]
    exact = [d for d in dirs if d.name.lower() == q]
    if exact:
        return exact[0]
    prefix = [d for d in dirs if d.name.lower().startswith(q)]
    if prefix:
        return prefix[0]  # a mais recente que casa
    by_subject = [d for d in dirs if q in (read_subject(d) or "").lower()]
    if by_subject:
        return by_subject[0]
    ids = ", ".join(d.name for d in dirs[:8])
    raise ValueError(f"Reunião '{meeting}' não encontrada. Ids disponíveis (mais recentes): {ids}")


def listing(root: Path, limit: int = 20, query: str = "") -> str:
    """Uma reunião por linha: 'id | título | falas | duração | participantes'."""
    q = query.strip().lower()
    lines = []
    for d in meeting_dirs(root):
        if q and q not in d.name.lower() and q not in (read_subject(d) or "").lower():
            try:
                text = (d / "transcricao.jsonl").read_text(encoding="utf-8").lower()
            except OSError:
                continue
            if q not in text:
                continue
        s = summary(d)
        lines.append(f"{s['id']} | {s['title']} | {s['falas']} falas | {s['meta']}")
        if len(lines) >= max(limit, 1):
            break
    return "\n".join(lines) if lines else "Nenhuma reunião encontrada."


def transcript_text(folder: Path) -> str:
    """Cabeçalho da reunião + uma fala por linha ('AAAA-MM-DD hh:mm:ss | Quem | fala'), com os nomes definidos."""
    recs = read_jsonl(folder / "transcricao.jsonl")
    names = read_names(folder)
    text = render_transcript(recs, folder.name, read_parts(folder), names)
    return build_message("", call_title(folder.name, read_subject(folder) or ""), text,
                         transcript_meta(recs, names))


def started_at(folder: Path) -> str:
    dt = parse_stamp(folder.name)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else folder.name

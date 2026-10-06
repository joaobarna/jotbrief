"""Assunto (título curto) da call, gerado pelo Claude a partir da transcrição."""
from __future__ import annotations

from pathlib import Path

import anthropic
from pydantic import BaseModel

from .config import Config, supports_effort
from .session import read_jsonl, render_markdown

class Assunto(BaseModel):
    assunto: str


SUBJECT_SYSTEM = (
    "Dê um título curto para uma reunião a partir da transcrição automática (português, pode ter erros). "
    "Até 8 palavras, descrevendo o tema principal (ex.: 'Revisão do orçamento do 3º trimestre'). "
    "Sem aspas, sem data, sem o caractere '|'. Não invente o que não estiver na conversa."
)


def generate_subject(folder: Path, cfg: Config | None = None) -> str:
    """Assunto da call gerado pelo Claude; salvo em meta.json na pasta da reunião."""
    from .ui_helpers import clean_subject, read_subject, write_subject

    folder = Path(folder)
    if (existing := read_subject(folder)):
        return existing
    cfg = cfg or Config.load()
    records = read_jsonl(folder / "transcricao.jsonl")
    if not records:
        raise ValueError("transcrição vazia")
    transcript = render_markdown(records, "Transcrição")[:60000]
    try:
        resp = anthropic.Anthropic().messages.parse(
            model=cfg.claude_model, max_tokens=2000,
            **({"output_config": {"effort": "low"}} if supports_effort(cfg.claude_model) else {}),
            system=SUBJECT_SYSTEM,
            messages=[{"role": "user", "content": transcript}],
            output_format=Assunto,
        )
    except (anthropic.AuthenticationError, TypeError) as e:  # TypeError: o SDK reclama quando não há credencial
        if isinstance(e, TypeError) and "authentication" not in str(e).lower():
            raise
        raise RuntimeError("ANTHROPIC_API_KEY ausente ou inválida (veja o README: .env)") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError(f"Sem conexão com a API: {e}") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Erro da API ({e.status_code}): {e.message}") from e
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise RuntimeError("Não foi possível gerar o assunto")
    subject = clean_subject(resp.parsed_output.assunto)
    write_subject(folder, subject)
    return subject

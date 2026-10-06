"""Servidor MCP do SaidKeep: deixa o Claude (Desktop) ler as reuniões salvas sozinho.

Ferramentas (somente leitura):
  list_meetings(limit, query)   -> reuniões salvas
  get_transcript(meeting)       -> transcrição de uma reunião ('latest' = a mais recente)
Prompts (aparecem como atalhos no chat): os mesmos pedidos do botão do Claude (Ata, Resumo, Tarefas…).

Roda por stdio: NADA pode escrever no stdout além do protocolo.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from . import meetings
from .prompts import load_prompts

INSTRUCTIONS = (
    "Acesso às reuniões gravadas pelo app SaidKeep (transcrições locais em português). "
    "Use list_meetings para ver as reuniões e get_transcript para ler uma. Cada linha da transcrição é "
    "'data hora | falante | fala'. A transcrição é automática e pode ter erros."
)


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "pedido"


def build_server(root: Path | None = None) -> MCPServer:
    root = root or meetings.default_root()
    srv = MCPServer("saidkeep", instructions=INSTRUCTIONS)

    @srv.tool(description="Lista as reuniões salvas (mais recentes primeiro): id | título | falas | duração | "
                          "participantes. 'query' filtra por assunto, data ou trecho da conversa.")
    def list_meetings(limit: int = 20, query: str = "") -> str:
        return meetings.listing(root, limit, query)

    @srv.tool(description="Devolve a transcrição de uma reunião, uma fala por linha com data, hora e falante. "
                          "'meeting' aceita 'latest' (padrão), o id (ex.: 2026-09-29_1552), uma data "
                          "(2026-09-29) ou parte do assunto.")
    def get_transcript(meeting: str = "latest") -> str:
        return meetings.transcript_text(meetings.resolve(root, meeting))

    for pr in load_prompts():
        def make(pedido: str):
            def prompt_fn(meeting: str = "latest") -> str:
                return (f"{pedido}\n\nLeia a reunião com a ferramenta get_transcript "
                        f"(meeting=\"{meeting}\") e responda em português.")
            return prompt_fn

        srv.prompt(name=slugify(pr["nome"]), title=f"{pr['icone']} {pr['nome']}",
                   description=pr["pedido"][:180])(make(pr["pedido"]))
    return srv


def main(root: Path | None = None) -> None:
    build_server(root).run("stdio")


if __name__ == "__main__":
    main()

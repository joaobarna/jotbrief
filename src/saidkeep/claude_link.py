"""Abrir uma conversa NOVA dentro do projeto do Claude, já com o pedido (e a transcrição, quando cabe) preenchidos.

Testado no claude.ai: `https://claude.ai/new?project=<id>&q=<texto>` abre a conversa no projeto com o texto na
caixa (a página do projeto em si ignora `?q=`). O Claude não envia sozinho: mostra um aviso de segurança e você clica
em enviar. Textos de ~7,5 mil caracteres foram aceitos inteiros; acima disso o app envia só o pedido + cabeçalho
pelo link e deixa a transcrição na área de transferência (Ctrl+V).
"""
from __future__ import annotations

import html
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .prompts import build_message

BASE = "https://claude.ai/new"
BASE_APP = "claude://claude.ai/new"  # app Claude para Windows (protocolo claude://)
# O tratador de links do app (lido no código dele) aceita em /new SÓ o parâmetro `q`; `project` invalida o link. Ele só
# abre um projeto por id (claude://claude.ai/project/<id>), sem texto. Por isso, para o app: abre o projeto e deixa o
# texto completo na área de transferência. O app também corta `q` em 14.336 caracteres.
DESKTOP_MAX_URL = 12000
MAX_URL = 7500  # tamanho do link que sabemos que o claude.ai aceita (testado com ~7,5 mil caracteres)
_PROJECT_RE = re.compile(r"/project/([0-9a-fA-F-]{36})")


def project_id(project_url: str | None) -> str | None:
    m = _PROJECT_RE.search(project_url or "")
    return m.group(1) if m else None


def build_url(text: str, project_url: str | None = None, desktop: bool = False) -> str:
    """Link de 'conversa nova' com `text` preenchido, dentro do projeto (se a URL do projeto for conhecida).

    `desktop=True` gera o link do app Claude para Windows (claude://claude.ai/new?q=…), em vez do do navegador.
    No app o parâmetro `project` não é aceito (invalida o link), então nunca vai no link do app.
    """
    pid = None if desktop else project_id(project_url)
    base = BASE_APP if desktop else BASE
    head = f"{base}?project={pid}&q=" if pid else f"{base}?q="
    return head + quote(text, safe="")


@dataclass
class LaunchPlan:
    url: str
    clipboard: str | None   # texto a colar (Ctrl+V) quando a transcrição não cabe no link
    full: bool              # True: tudo vai no link; False: pedido no link + transcrição na área de transferência
    mode: str = "link"      # "link" (conversa nova com texto) ou "project" (app: só abre o projeto; texto copiado)


def plan_launch(pedido: str, title: str, transcript: str, meta: str = "", project_url: str | None = None,
                limit: int = MAX_URL, desktop: bool = False, compact: bool = False) -> LaunchPlan:
    """Decide o que vai no link e o que vai para a área de transferência."""
    message = build_message(pedido, title, transcript, meta, compact)
    if desktop:
        pid = project_id(project_url)
        if pid:  # app: abre a página do projeto e deixa TUDO na área de transferência (colar na caixa "Nova sessão")
            return LaunchPlan(f"claude://claude.ai/project/{pid}", message, False, "project")
        limit = min(limit, DESKTOP_MAX_URL) if limit == MAX_URL else limit
    url = build_url(message, project_url, desktop)
    if len(url) <= limit:
        return LaunchPlan(url, None, True)
    head = build_message(pedido, title, "", meta, compact)  # pedido + cabeçalho; a transcrição é colada em seguida
    return LaunchPlan(build_url(head, project_url, desktop), transcript.strip() + "\n", False)


def write_redirect_page(url: str, directory: Path | None = None) -> Path:
    """Página local que só redireciona para `url`.

    Usada no botão do NAVEGADOR: abrir um arquivo curto e deixar o navegador redirecionar evita problemas com links
    https muito longos na linha de comando. (O app do Windows recebe o link claude:// inteiro direto do sistema.)
    O arquivo é apagado pelo app logo depois.
    """
    path = (directory or Path(tempfile.gettempdir())) / "saidkeep_abrir_claude.html"
    path.write_text(
        "<!doctype html><meta charset=\"utf-8\"><title>Abrindo o Claude…</title>"
        "<body style=\"font-family:sans-serif;padding:2em\">Abrindo o Claude…"
        f"<script>location.replace({json.dumps(url)});</script>"
        f"<noscript><a href=\"{html.escape(url)}\">Clique para abrir o Claude</a></noscript></body>",
        encoding="utf-8")
    return path

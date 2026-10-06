"""Pedidos prontos para levar a transcrição ao Claude. A lista é editável em %APPDATA%\\saidkeep\\prompts.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

PROMPTS_PATH = Path(os.environ.get("APPDATA", Path.home())) / "saidkeep" / "prompts.json"

DEFAULTS: list[dict] = [
    {"icone": "✨", "nome": "Ata da reunião",
     "pedido": "Gere a ata desta reunião com: participantes (se dá para identificar), pauta, principais "
               "discussões, decisões tomadas, action items (tarefa, responsável e prazo, quando citados) "
               "e pendências em aberto. Seja fiel ao que foi dito e não invente responsáveis nem prazos."},
    {"icone": "✨", "nome": "Resumo curto",
     "pedido": "Faça um resumo curto desta reunião, em até 5 linhas."},
    {"icone": "✓", "nome": "Resumo detalhado",
     "pedido": "Faça um resumo detalhado desta reunião, organizado por tópico, com contexto, argumentos e conclusões."},
    {"icone": "✨", "nome": "Resumo detalhado com citação",
     "pedido": "Faça um resumo detalhado desta reunião, por tópico, citando trechos literais entre aspas "
               "com a data e a hora da fala entre colchetes, como [2026-09-29 15:52:08]."},
    {"icone": "✓", "nome": "Resumo e itens de ação",
     "pedido": "Faça um resumo desta reunião e, ao final, liste os itens de ação (o que, quem e quando)."},
    {"icone": "☑", "nome": "Gerar tarefas",
     "pedido": "Extraia desta reunião uma lista de tarefas, cada uma com responsável, prazo e prioridade "
               "(marque como 'não informado' o que não foi dito)."},
    {"icone": "✉", "nome": "Rascunho de e-mail",
     "pedido": "Escreva um rascunho de e-mail de follow-up para os participantes desta reunião: agradecimento, "
               "resumo objetivo, decisões e próximos passos com responsáveis."},
    {"icone": "▦", "nome": "Preparar slides",
     "pedido": "Monte a estrutura de uma apresentação (slides) sobre esta reunião: título, e para cada slide "
               "um título e 3 a 5 tópicos curtos."},
    {"icone": "🧠", "nome": "Conselhos inteligentes",
     "pedido": "Faça uma análise crítica desta reunião: riscos, lacunas, pontos que ficaram sem definição, "
               "perguntas que deveriam ter sido feitas e recomendações de próximos passos."},
    {"icone": "🔄", "nome": "Sincronização da equipe",
     "pedido": "Extraia as atualizações de status desta reunião por assunto ou pessoa: o que foi feito, "
               "o que está em andamento e o que está bloqueado."},
]

TRANSCRIPT_ONLY = {"icone": "📄", "nome": "Só a transcrição", "pedido": ""}


def load_prompts(path: Path = PROMPTS_PATH) -> list[dict]:
    """Lê a lista de pedidos do arquivo (criando-o com os padrões na 1ª vez); volta aos padrões se inválido."""
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2), encoding="utf-8")
            return [dict(p) for p in DEFAULTS]
        data = json.loads(path.read_text(encoding="utf-8"))
        ok = [p for p in data if isinstance(p, dict) and p.get("nome") and p.get("pedido")]
        return [{"icone": p.get("icone", "✨"), "nome": p["nome"], "pedido": p["pedido"]} for p in ok] \
            or [dict(p) for p in DEFAULTS]
    except (OSError, ValueError, TypeError):
        return [dict(p) for p in DEFAULTS]


def build_message(pedido: str, title: str, transcript: str, meta: str = "", compact: bool = False) -> str:
    """Texto colado no chat: o pedido vem PRIMEIRO; depois o cabeçalho da reunião e uma fala por linha.

    `compact=True` (modo skill): "Use a skill X." + "Transcrição:" + cabeçalho + falas, sem avisos repetidos.

        <pedido>

        Reunião: 2026-09-29 | 15:52 | Assunto
        Duração: 00:05:12 | Participantes: Eu, Pessoa 1

        Transcrição automática, pode ter erros. Formato: data hora | falante | fala. “Eu” = quem gravou.

        2026-09-29 15:52:02 | Pessoa 1 | ...
    """
    head = f"{pedido.strip()}\n\n" if pedido.strip() else ""
    info = f"Reunião: {title}\n" + (f"{meta}\n" if meta else "")
    if compact:  # só chama a skill e indica a transcrição (as regras de leitura já estão na skill)
        return f"{head}Transcrição:\n{info}\n{transcript.strip()}\n"
    notes = ["Transcrição automática, pode ter erros.", "Formato: data hora | falante | fala."]
    if "| Eu |" in transcript:
        notes.append("“Eu” = quem gravou.")
    if "| Pessoa " in transcript:
        notes.append("“Pessoa N” = voz separada automaticamente (pode errar).")
    if "| Reunião |" in transcript:
        notes.append("“Reunião” = os demais participantes.")
    return f"{head}{info}\n{' '.join(notes)}\n\n{transcript.strip()}\n"

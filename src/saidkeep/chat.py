"""Chat com o Claude sobre a reunião (durante ou depois): a transcrição vai como contexto, as respostas chegam aos poucos."""
from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path

import anthropic

from .config import Config, supports_effort

CHAT_FILE = "chat.json"
MAX_TRANSCRIPT = 150_000  # caracteres (≈ 2–3 h de reunião); acima disso mantém o começo e o fim

# Botões prontos: (rótulo, pedido). O rótulo aparece na conversa; o pedido é o que vai ao Claude.
QUICK = [
    ("📝 Resumo detalhado",
     "Faça um resumo detalhado da reunião até agora: contexto, cada assunto discutido com os argumentos de cada "
     "pessoa (cite quem disse), decisões tomadas, números e datas mencionados, pontos de desacordo e próximos passos. "
     "Organize por tópicos com títulos curtos."),
    ("⚡ Resumo rápido", "Resuma a reunião até agora em no máximo 5 linhas."),
    ("🎯 Pontos-chave", "Liste os pontos-chave da reunião até agora em tópicos curtos, do mais importante ao menos."),
    ("✅ Decisões e tarefas",
     "Liste as decisões tomadas e as tarefas combinadas: o quê, quem é o responsável e o prazo (quando foi dito). "
     "Marque como 'a confirmar' o que ficou vago."),
    ("❓ Em aberto", "Quais perguntas ficaram sem resposta e que pontos ainda precisam ser esclarecidos ou decididos?"),
    ("💡 Perguntas para fazer",
     "Sugira de 5 a 8 perguntas que eu deveria fazer agora nesta reunião, com base no que foi dito até agora: "
     "aprofundar pontos vagos, checar premissas, números ou datas sem fonte, riscos, decisões e responsáveis ainda sem "
     "definição, e contradições entre falas. Para cada uma, escreva a pergunta pronta para falar em voz alta (uma frase) "
     "e, em uma linha, por que ela importa. Ordene da mais importante para a menos."),
    ("🔎 Última fala", "Explique em poucas linhas o que acabou de ser dito nos últimos minutos e por que importa."),
]

SYSTEM = (
    "Você ajuda o usuário a analisar uma reunião gravada (que pode ainda estar acontecendo). "
    "Abaixo está a transcrição automática, em português, e pode ter erros de reconhecimento (nomes e números "
    "especialmente). Cada linha é 'data hora | falante | fala'; “Eu” é quem gravou. "
    "Responda sempre em português, de forma direta, usando Markdown simples (títulos curtos e tópicos). "
    "Baseie-se só no que foi dito: se algo não está na transcrição, diga que não foi mencionado. "
    "Não invente nomes, números nem decisões."
)


# US$ por milhão de tokens (tabela oficial): entrada, saída, leitura de cache, escrita de cache (5 min = 1,25x a entrada)
PRICES = {
    "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "read": 0.20, "write": 2.50},
    "claude-opus-5-5": {"in": 4.00, "out": 20.00, "read": 0.20, "write": 5.00},
    "claude-haiku-4-5": {"in": 1.00, "out": 5.00, "read": 0.10, "write": 1.25},
}
EFFORTS = [("baixo", "low"), ("médio", "medium"), ("alto", "high"), ("muito alto", "xhigh"), ("máximo", "max")]


def usage_dict(u) -> dict:
    """Tokens de uma resposta: entrada nova, saída (inclui o raciocínio), cache lido e cache gravado."""
    g = lambda k: int(getattr(u, k, 0) or 0)  # noqa: E731
    return {"in": g("input_tokens"), "out": g("output_tokens"),
            "read": g("cache_read_input_tokens"), "write": g("cache_creation_input_tokens")}


def usage_cost(model: str, usage: dict) -> float | None:
    """Custo estimado em US$ (None se o modelo não está na tabela de preços)."""
    p = PRICES.get(model)
    if not p:
        return None
    return sum(usage.get(k, 0) * p[k] for k in ("in", "out", "read", "write")) / 1_000_000


def total_cost(messages: list[dict]) -> float | None:
    """Soma o custo de cada resposta com o preço do modelo que a gerou (None se algum modelo não tem preço)."""
    total = 0.0
    for m in messages:
        u = m.get("usage")
        if u:
            c = usage_cost(u.get("model", ""), u)
            if c is None:
                return None
            total += c
    return total


def sum_usage(messages: list[dict]) -> dict:
    tot = {"in": 0, "out": 0, "read": 0, "write": 0}
    for m in messages:
        for k, v in (m.get("usage") or {}).items():
            if k in tot:
                tot[k] += int(v)
    return tot


def _k(n: int) -> str:
    return f"{n / 1000:.1f} mil".replace(".", ",") if n >= 1000 else str(n)


def fmt_usage(model: str, usage: dict, label: str = "", cost: float | None = None, brl: float | None = None) -> str:
    """'12,3 mil entrada (9,0 mil do cache) · 640 saída · ≈ US$ 0,03'."""
    cached = usage.get("read", 0)
    total_in = usage.get("in", 0) + usage.get("write", 0) + cached
    txt = f"{_k(total_in)} entrada" + (f" ({_k(cached)} do cache)" if cached else "") + f" · {_k(usage.get('out', 0))} saída"
    if cost is None:
        cost = usage_cost(model, usage)
    if cost is not None:
        txt += f" · ≈ US$ {cost:.3f}".replace(".", ",")
        if brl:
            txt += f" (R$ {cost * brl:.2f})".replace(".", ",")
    return (label + ": " if label else "") + txt


def build_system(title: str, meta: str, transcript: str, live: bool) -> str:
    t = transcript.strip()
    if len(t) > MAX_TRANSCRIPT:
        half = MAX_TRANSCRIPT // 2
        t = t[:half] + "\n[… trecho do meio omitido por tamanho …]\n" + t[-half:]
    state = "A reunião ainda está em andamento; a transcrição vai até agora." if live else "A reunião já terminou."
    return f"{SYSTEM}\n\n{state}\nReunião: {title}\n{meta}\n\nTranscrição:\n{t}\n"


def friendly_error(e: Exception) -> str:
    if isinstance(e, anthropic.AuthenticationError) or (
            isinstance(e, TypeError) and "authentication" in str(e).lower()):
        return "ANTHROPIC_API_KEY ausente ou inválida (veja o README: .env)."
    if isinstance(e, anthropic.APIConnectionError):
        return f"Sem conexão com a API: {e}"
    if isinstance(e, anthropic.APIStatusError):
        return f"Erro da API ({e.status_code}): {e.message}"
    return str(e)


def stream_reply(cfg: Config, system: str, messages: list[dict], on_delta: Callable[[str], None],
                 stop: threading.Event | None = None) -> tuple[str, dict]:
    """Pergunta ao Claude e entrega o texto aos poucos; retorna (resposta, tokens usados — {} se você parou antes)."""
    out: list[str] = []
    usage: dict = {}
    client = anthropic.Anthropic()
    with client.messages.stream(
            model=cfg.claude_model, max_tokens=8000,
            **({"output_config": {"effort": cfg.chat_effort}} if supports_effort(cfg.claude_model) else {}),
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": m["role"], "content": m["content"]} for m in messages]) as stream:
        for piece in stream.text_stream:
            if stop is not None and stop.is_set():
                break
            out.append(piece)
            on_delta(piece)
        else:
            usage = usage_dict(stream.get_final_message().usage)
    return "".join(out), usage


def test_key(key: str, model: str) -> str:
    """Confere a chave com uma consulta gratuita (só pergunta pelo modelo). Retorna "" se válida, ou o motivo."""
    try:
        anthropic.Anthropic(api_key=key.strip()).models.retrieve(model)
        return ""
    except Exception as e:  # noqa: BLE001
        if isinstance(e, anthropic.AuthenticationError):
            return "A Anthropic recusou esta chave (inválida ou revogada)."
        return friendly_error(e)


def load_chat(folder: Path) -> list[dict]:
    try:
        data = json.loads((Path(folder) / CHAT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [m for m in data if isinstance(m, dict) and m.get("role") in ("user", "assistant")
            and isinstance(m.get("content"), str)]


def save_chat(folder: Path, messages: list[dict]) -> None:
    (Path(folder) / CHAT_FILE).write_text(json.dumps(messages, ensure_ascii=False), encoding="utf-8")

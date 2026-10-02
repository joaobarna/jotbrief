"""Gera a skill do Claude "jb-transcricao" e o painel HTML (botões de copiar), a partir da lista de pedidos.

- SKILL.md: ensina o Claude a receber a transcrição do JB, perguntar o que gerar e entregar o painel.
- painel.html: nome da conversa + um botão de copiar para cada pedido (funciona dentro do Claude e sozinho no navegador).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .prompts import load_prompts

SKILL_NAME = "jb-jot-brief-transcricao"

def skill_request(name: str = SKILL_NAME) -> str:
    """Texto no início da mensagem enviada ao Claude (funciona com ou sem a skill instalada)."""
    return f"Use a skill {name}."


SKILL_REQUEST = skill_request()

PAINEL_TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JB · Painel da reunião</title>
<style>
  :root { --bg:#ffffff; --panel:#f6f7f9; --text:#1f2328; --muted:#6b7280; --border:#e5e7eb; --accent:#12805c; --accent-text:#ffffff; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f1115; --panel:#161a20; --text:#e6e8eb; --muted:#8b93a1; --border:#232832; --accent:#3ddc97; --accent-text:#06281a; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:15px/1.5 "Segoe UI", system-ui, -apple-system, Arial, sans-serif; }
  main { max-width: 880px; margin: 0 auto; padding: 24px 16px 48px; }
  h1 { font-size: 18px; margin: 0 0 4px; }
  .sub { color: var(--muted); margin: 0 0 18px; font-size: 13px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 14px 16px; }
  .label { font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 8px; }
  .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  input[type=text] { flex: 1; min-width: 240px; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--border);
                     background: var(--bg); color: var(--text); font: inherit; }
  button { cursor: pointer; border: 1px solid var(--border); background: var(--bg); color: var(--text); border-radius: 10px;
           padding: 9px 14px; font: inherit; font-weight: 600; }
  button:hover { border-color: var(--accent); }
  button.primary { background: var(--accent); color: var(--accent-text); border-color: var(--accent); }
  button.ok { background: var(--accent); color: var(--accent-text); border-color: var(--accent); }
  h2 { font-size: 14px; margin: 22px 0 10px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
  .op { display: flex; flex-direction: column; gap: 8px; }
  .op h3 { margin: 0; font-size: 15px; }
  .op p { margin: 0; color: var(--muted); font-size: 13px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  .op button { align-self: flex-start; }
  .hint { color: var(--muted); font-size: 13px; margin-top: 14px; }
  @media (max-width: 520px) { button { width: 100%; } }
</style>
</head>
<body>
<main>
  <h1>JB · Painel da reunião</h1>
  <p class="sub" id="sub"></p>

  <div class="card">
    <div class="label">Nome da conversa</div>
    <div class="row">
      <input type="text" id="titulo" aria-label="Nome da conversa">
      <button class="primary" id="copiar-titulo" type="button">Copiar nome</button>
    </div>
    <p class="hint">Renomeie a conversa no Claude colando este nome (o Claude não consegue renomear sozinho).</p>
  </div>

  <h2>O que gerar com esta reunião</h2>
  <div class="grid" id="opcoes"></div>
  <p class="hint">Clique em <b>Copiar pedido</b> e cole como próxima mensagem nesta conversa.</p>
</main>

<script>
const DADOS = __DADOS__;

function copiar(texto, botao, rotulo) {
  const feito = () => {
    botao.textContent = "Copiado ✓";
    botao.classList.add("ok");
    setTimeout(() => { botao.textContent = rotulo; botao.classList.remove("ok"); }, 1600);
  };
  const alternativa = () => {           // plano B: alguns ambientes bloqueiam navigator.clipboard
    const area = document.createElement("textarea");
    area.value = texto; area.style.position = "fixed"; area.style.opacity = "0";
    document.body.appendChild(area); area.select();
    try { document.execCommand("copy"); feito(); } catch (e) { botao.textContent = "Selecione e copie (Ctrl+C)"; }
    document.body.removeChild(area);
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(texto).then(feito, alternativa);
  } else { alternativa(); }
}

document.getElementById("sub").textContent = DADOS.subtitulo || "";
const campo = document.getElementById("titulo");
campo.value = DADOS.titulo;
document.getElementById("copiar-titulo").addEventListener("click", (e) => copiar(campo.value, e.target, "Copiar nome"));

const grade = document.getElementById("opcoes");
for (const op of DADOS.opcoes) {
  const card = document.createElement("div");
  card.className = "card op";
  const h = document.createElement("h3"); h.textContent = `${op.icone}  ${op.nome}`;
  const p = document.createElement("p"); p.textContent = op.pedido || "Só a transcrição, sem pedido.";
  const b = document.createElement("button"); b.type = "button"; b.textContent = "Copiar pedido";
  b.addEventListener("click", () => copiar(op.pedido || "Só a transcrição: não gere nada, apenas confirme que recebeu.", b, "Copiar pedido"));
  card.append(h, p, b); grade.appendChild(card);
}
</script>
</body>
</html>
"""


def _options(prompts: list[dict] | None = None) -> list[dict]:
    prompts = prompts if prompts is not None else load_prompts()
    return [{"icone": p["icone"], "nome": p["nome"], "pedido": p["pedido"]} for p in prompts]


def render_painel(title: str = "AAAA-MM-DD | hh:mm | Assunto", subtitle: str = "",
                  prompts: list[dict] | None = None) -> str:
    """HTML do painel. `title` já no formato 'AAAA-MM-DD | hh:mm | Assunto'."""
    dados = {"titulo": title, "subtitulo": subtitle, "opcoes": _options(prompts)}
    blob = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")  # nunca fecha o <script> por engano
    return PAINEL_TEMPLATE.replace("__DADOS__", blob)


def render_skill_md(prompts: list[dict] | None = None) -> str:
    opts = _options(prompts)
    catalog = "\n".join(f"{i}. **{o['icone']} {o['nome']}**: {o['pedido']}" for i, o in enumerate(opts, 1))
    menu = "\n".join(f"{i}. {o['icone']} {o['nome']}" for i, o in enumerate(opts, 1))
    return f"""---
name: {SKILL_NAME}
description: Use quando o usuário colar ou anexar a transcrição de uma reunião gravada pelo app JB - Jot Brief (cabeçalho "Reunião: AAAA-MM-DD | hh:mm | Assunto" e linhas "data hora | falante | fala"), ou pedir para trabalhar uma call/reunião gravada. Pergunta o que gerar (ata, resumos, tarefas, e-mail, slides, análise) e entrega um painel HTML com botões para copiar o nome da conversa e os pedidos.
---

# JB · Transcrição de reunião

O usuário grava reuniões com o app JB - Jot Brief e cola a transcrição aqui. Seu trabalho: entender a reunião, perguntar o que ele quer gerar e entregar o resultado junto com um painel de botões de copiar.

## Passo 1 · Entender o material
- Leia o cabeçalho: `Reunião: AAAA-MM-DD | hh:mm | Assunto`, `Duração`, `Participantes` e a nota sobre falantes.
- Cada linha da transcrição é `AAAA-MM-DD hh:mm:ss | Falante | fala`. "Eu" é o usuário; nomes como "Pessoa 2" ou "Reunião" são vozes separadas automaticamente e podem estar erradas.
- A transcrição é automática e pode ter erros de reconhecimento (nomes próprios, termos técnicos, trechos em outro idioma). Não trate como literal quando algo parecer absurdo: sinalize.
- Sem cabeçalho, deduza data, hora e assunto do conteúdo e diga o que deduziu.

## Passo 2 · Nome da conversa
O Claude não consegue renomear conversas. Monte o nome no padrão do projeto e entregue pronto para copiar:

`AAAA-MM-DD | hh:mm | Assunto`

Use a data e a hora do cabeçalho. O assunto tem no máximo 8 palavras, em português, descreve o tema principal e não contém o caractere `|`.

## Passo 3 · Perguntar o que gerar
- Se a mensagem do usuário já pede algo específico (por exemplo "gere a ata"), não pergunte: gere.
- Caso contrário, pergunte de forma curta qual(is) entregável(is) ele quer, mostrando esta lista numerada (pode escolher mais de um):

{menu}

- Aceite também pedidos livres. Se ele escolher "Só a transcrição", apenas confirme o recebimento e mostre o painel.

## Passo 4 · Gerar
Siga o pedido da opção escolhida. Catálogo (o texto de cada pedido):

{catalog}

Regras de fidelidade, valem para todas as opções:
- Não invente responsáveis, prazos, valores ou decisões que não estejam na conversa. Marque "não informado".
- Ao citar, use aspas e o horário da fala no formato `[AAAA-MM-DD hh:mm:ss]`.
- Preserve os nomes dos falantes como estão na transcrição; se a atribuição parecer incerta ("Pessoa N"), avise.
- Responda em português do Brasil, com estrutura curta e escaneável.

## Passo 5 · Painel de botões (HTML)
Ao final de cada resposta (ou logo após o Passo 2, se o usuário só quiser o painel), entregue **um artefato HTML** com:
1. O nome da conversa (Passo 2) em um campo editável com o botão **Copiar nome**.
2. Um cartão para cada opção do catálogo acima, com o botão **Copiar pedido** (copia o texto do pedido para colar como próxima mensagem).

Use o arquivo `painel.html` desta skill como base: copie-o inteiro e troque apenas `titulo` (e, se quiser, `subtitulo`) dentro de `const DADOS = {{...}}`. Se não conseguir ler o arquivo, crie um HTML único, sem bibliotecas externas, que faça o mesmo: botões com `navigator.clipboard.writeText` e, como plano B, `document.execCommand("copy")` com um `textarea` temporário.

Depois do painel, diga em uma linha: "Renomeie a conversa colando o nome e, se quiser outra saída, copie o pedido."
"""


def build_skill(dest: Path, prompts: list[dict] | None = None) -> Path:
    """Escreve dest/jb-transcricao/{SKILL.md, painel.html} e dest/jb-transcricao.zip (para enviar ao Claude)."""
    dest = Path(dest)
    folder = dest / SKILL_NAME
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(render_skill_md(prompts), encoding="utf-8", newline="\n")
    (folder / "painel.html").write_text(render_painel(prompts=prompts), encoding="utf-8", newline="\n")
    zpath = dest / f"{SKILL_NAME}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in (folder / "SKILL.md", folder / "painel.html"):
            z.write(f, f"{SKILL_NAME}/{f.name}")
    return zpath

# JB - Jot Brief — documentação

App para Windows que **transcreve reuniões (Google Meet, Teams, Zoom) sem bot**, separa e nomeia quem fala, e leva a
conversa para o Claude (chat dentro do app, projeto do claude.ai ou app Claude do Windows).
Tudo que é áudio roda **no seu computador**; só o texto vai ao Claude, quando você pede.

> Esta documentação descreve o app como ele está hoje. Para instalar e usar no dia a dia, veja também o `README.md`.

---

## 1. Visão geral

| O que faz | Como |
|---|---|
| Grava a reunião **sem bot** | Captura o áudio que sai nas caixas/fone (loopback WASAPI) + o seu microfone |
| Transcreve **localmente** | Whisper (faster-whisper) na sua placa NVIDIA; sem placa, usa a CPU com um modelo menor |
| Mostra a conversa **ao vivo** | Bolhas estilo chat, que acompanham o áudio; você à direita, a reunião à esquerda |
| Separa e nomeia as pessoas | Separação de vozes + reconhecimento por voz + nomes vistos no Meet + convidados da agenda |
| Conversa com o Claude **durante a reunião** | Coluna de chat com botões prontos (resumo, tarefas, perguntas para fazer…) |
| Leva para o Claude | Navegador, app do Windows ou servidor MCP (o Claude Desktop lê as reuniões sozinho) |

**Custos:** transcrição, separação de vozes e reconhecimento são grátis (rodam locais). O que usa a API da Anthropic
(com a sua `ANTHROPIC_API_KEY`) é o **chat do painel** e o **assunto automático** da reunião. O app mostra o consumo em tokens
e o custo estimado em US$ e em R$.

---

## 2. Instalação e primeiro uso

Requisitos: Windows 11, Python 3.12 (gerenciado pelo `uv`), e, para velocidade, uma placa NVIDIA.

```
uv sync --extra cuda          # com GPU NVIDIA; sem GPU: uv sync
copy .env.example .env        # preencha ANTHROPIC_API_KEY
uv run jotbrief setup         # baixa os modelos de transcrição (~1,6 GB)
uv run jotbrief gui           # abre a janela
```

- A chave da API fica **só** no arquivo `.env` (nunca vai para o Git nem para a tela).
- Os modelos de separação de voz (≈ 32 MB) são baixados na primeira vez que você usa 👥.
- Dispositivos de áudio: `uv run jotbrief devices` lista; por padrão o app usa os padrões do Windows.

**Primeira gravação:** abra o app → escolha o idioma (Português, Inglês ou Automático) → clique no botão redondo de gravar →
fale/ouça a reunião → clique de novo para parar. A reunião aparece na lista à esquerda.

---

## 3. A janela

```
┌──────────────┬───────────────────────────────┬──────────────────┐
│  Lista de    │  ● 00:00:00   + Nova reunião   │  Claude          │
│  reuniões    │  [barra de botões]             │  modelo · esforço│
│  (por dia)   │  Gravando em: título           │  consumo (US$/R$)│
│              │  player de áudio               │  [botões prontos]│
│              │  bolhas da transcrição         │  conversa        │
│              │                                │  [pergunta ↑]    │
├──────────────┴───────────────────────────────┴──────────────────┤
│  Aviso LGPD                                                      │
└──────────────────────────────────────────────────────────────────┘
```

### 3.1 Lista de reuniões (esquerda)
- Cada reunião é um cartão: **`AAAA-MM-DD | hh:mm | Assunto`** (data e hora em negrito), número de falas e, se houver tarefa em
  andamento, a linha `⏳ identificando falantes…`.
- Agrupada por dia; o botão do dia (**`▾ HOJE · 2026-10-02 (7)`**) recolhe/expande. Ao abrir o app só o último dia com transcrição
  fica aberto. A reunião selecionada ou em gravação nunca fica escondida.
- **Buscar reuniões:** procura no título e no texto das transcrições.
- 🗑 move a reunião para a **Lixeira do Windows** (dá para recuperar). Não deixa excluir a que está sendo gravada.
- **+ Nova reunião** deixa nenhuma selecionada: a próxima gravação cria uma nova (uma linha "Nova reunião" aparece no topo).
  Gravar com uma reunião selecionada **continua nela** (vira "Parte 2", com um separador).

### 3.2 Barra de botões (centro)
| Grupo | Botões |
|---|---|
| Gravar | Gravar/parar + tempo · **Nova reunião** · idioma |
| Claude | ✳🌐 navegador · ⚙ projeto · ✳🪟 app do Windows (manual) |
| Pessoas | 👥 identificar falantes · ✏ dar nomes |
| Reprocessar | 🔄 transcreve o áudio de novo |
| Pasta | 📁 abre a pasta da reunião |
| Copiar | 📋 copia a transcrição no formato ideal para IA |
| Chat | 💬 mostra/oculta a coluna do Claude |
| Visual | 🎈 modo balão · tema claro/escuro |

### 3.3 Bolhas e player
- Você ("Eu") à direita, em verde; a reunião à esquerda, uma cor por pessoa. O texto parcial aparece pontilhado e vira
  definitivo quando a fala fecha.
- Clique no **nome** da bolha para renomear a pessoa (também ensina a voz dela).
- **Player:** play/pausa, ±10 s, barra de posição, volume. O texto **acompanha o áudio** como letra de música; "▶ Ouvir parte"
  toca só uma parte. O botão ↓ leva ao fim; durante a gravação a tela rola sozinha.
- **Modo balão (🎈):** ao gravar, a janela vira uma barra flutuante com a última fala.

### 3.4 Chat com o Claude (direita)
- **Botões prontos:** 📝 Resumo detalhado · ⚡ Resumo rápido · 🎯 Pontos-chave · ✅ Decisões e tarefas · ❓ Em aberto ·
  💡 Perguntas para fazer · 🔎 Última fala. O texto do pedido aparece ao passar o mouse.
- **Conversa livre:** escreva e aperte Enter (Shift+Enter quebra a linha). A resposta chega aos poucos; ■ interrompe.
- **Durante a gravação** o Claude lê a transcrição **até aquele momento** (atualizada a cada pergunta).
- **Modelo** (Sonnet 5.5, Opus 5.5 ou Haiku 4.5) e **esforço** (baixo → máximo) escolhidos no topo; valem para o app todo
  (chat e assunto). O Haiku não tem ajuste de esforço.
- **Consumo:** última resposta e total da reunião (tokens de entrada, parte vinda do cache, saída), custo estimado em
  **US$ e R$** (cotação atual, atualizada a cada hora; fonte e horário aparecem no painel).
- Cada reunião tem a sua conversa, salva em `chat.json` na pasta dela. 🗑 limpa.

---

## 4. Como cada recurso funciona

### 4.1 Captura e transcrição
- **Dois canais** gravados em um `audio.wav` estéreo de 16 kHz: **esquerda = seu microfone, direita = o áudio da reunião**.
- Um detector de fala (silero-vad, rodando via ONNX, sem PyTorch) corta o áudio em trechos; cada trecho vai ao Whisper. Há filtros contra "alucinações"
  (legendas-fantasma como "Legenda Adriana Zanotto", textos em outro alfabeto, frases repetidas).
- Idioma: Português, Inglês ou **Automático** (escolhe entre pt e en por trecho).

### 4.2 Eco do microfone (sem fone de ouvido)
Se o microfone "escuta" o alto-falante, o som da reunião voltaria como se fosse você. O app resolve em camadas:
1. **Texto:** descarta falas do mic que repetem o que a reunião disse no mesmo momento.
2. **Áudio ao vivo e depois de parar:** compara o volume dos dois canais ao longo do tempo. É vazamento quando o **microfone está
   baixíssimo** (≤ 0,002 medido) enquanto a reunião fala; a **sua voz**, mesmo por cima da reunião, tem volume 10–40× maior e
   nunca é escondida.
3. **Recuperação:** quando duas pessoas falam juntas, o canal da reunião só transcreve a voz mais forte; a outra pode ter ficado só no
   vazamento do mic. Se o Meet confirma 2+ pessoas falando juntas e o texto não existe no canal da reunião, o trecho volta como fala
   (com o nome de quem entrou por cima).

> **Limite:** com **fone de ouvido** o mic não capta a reunião; então não há eco, mas uma segunda voz falando por cima da primeira não
> fica registrada. Só capturar o áudio de cada participante separadamente resolveria isso (não implementado).

### 4.3 Identificar falantes (👥)
- Separa as vozes do canal da reunião em **Pessoa 1, 2…** (modelos locais: pyannote segmentation + embeddings de voz via
  sherpa-onnx), inclusive dividindo uma fala em que duas pessoas se alternam.
- Roda **automaticamente ao parar** a gravação, num **processo separado** (a janela não trava) — ~1 min para 9 min de áudio.
- Ao clicar manualmente você pode informar quantas pessoas falam (sem contar você); isso separa melhor vozes parecidas.
- Ajustes em `config.toml`: `diarization_threshold` (menor = separa mais; 0,3 padrão) e `num_speakers`.

### 4.4 Dar nomes às pessoas
Quatro fontes, da mais fraca para a mais forte (o que você digita **nunca** é sobrescrito):
1. **Reconhecimento por voz:** ao nomear alguém, o app guarda a **impressão de voz** e, nas próximas reuniões, dá o nome sozinho
   (`voice_match_threshold` 0,75 e `voice_match_margin` 0,05). É dado biométrico: fica só em `%APPDATA%\jotbrief\voices.json`
   (apague o arquivo para esquecer todas).
2. **Convidados da agenda:** com `calendar_ics_url` (endereço secreto iCal do Google Agenda), o app acha o evento do horário
   (inclui reuniões semanais/diárias) e põe os convidados no topo da lista de nomes.
3. **Nomes vistos no Meet** (extensão do Chrome, abaixo): cruza quem o Meet mostrou falando sozinho com cada voz.
4. **Você:** clicando no nome da bolha ou em ✏ (lista de pessoas já cadastradas + digitar novo).

### 4.5 Extensão do Chrome (Google Meet)
Pasta `extension/` — instalar em `chrome://extensions` → Modo do desenvolvedor → **Carregar sem compactação** → pasta `extension`.
- Observa a página do Meet e avisa o app quem está falando. Mostra um selo no canto inferior esquerdo:
  `[JB - Jot Brief] Nome · app gravando ✓` (também diz se o app está fechado ou não está gravando).
- **Ícone da extensão:** o JB verde; ganha um **círculo vermelho** quando o app está gravando.
- **Ao vivo:** quando uma só pessoa fala, a bolha já sai com o nome dela. Depois de parar, o cruzamento por voz refaz os nomes e
  aprende a voz.
- **Segurança:** só conversa com `127.0.0.1:47821`; o app recusa pedidos vindos de páginas da web (exige um header que só a extensão
  envia).
- Os avisos ficam em `falantes_meet.jsonl` na pasta da reunião.
- É **experimental**: o Meet não expõe "quem fala" de forma estável, então a detecção é por atividade da interface e pode precisar de
  ajuste se o Meet mudar (`DEBUG` em `content.js` mantém o selo visível).

### 4.6 Reprocessar (🔄)
Transcreve o `audio.wav` de novo com o idioma e os filtros atuais (faz backup da transcrição anterior em `transcricao.jsonl.bak`),
opcionalmente já identificando os falantes. Útil depois de melhorias no app ou para corrigir o idioma.

### 4.7 Levar para o Claude
- **✳🌐 Navegador:** abre uma conversa nova **dentro do seu projeto** no claude.ai com o pedido da skill + a transcrição. Com
  `auto_send = true` o app espera a página carregar e aperta Enter (só se a janela da frente for uma página nova do Claude).
  Calls longas (> ~7,5 mil caracteres no link) levam o pedido no link e a transcrição fica na área de transferência para colar.
- **✳🪟 App do Windows (manual):** o app Claude só aceita texto em conversas novas fora de projetos. Por isso o botão abre o projeto
  e copia o texto: clique em "Nova sessão" e cole (Ctrl+V).
- **⚙ Projeto:** define a URL do projeto (`https://claude.ai/project/…`).
- **Skill `jb-jot-brief-transcricao`:** `uv run jotbrief skill` gera o `.zip` (e o `painel.html`) para enviar ao Claude. A skill pergunta
  o que gerar e entrega o nome sugerido da conversa e botões de copiar.
- **Servidor MCP:** `uv run jotbrief mcp-install` (com o Claude Desktop **fechado**) registra um servidor **somente leitura** com
  `list_meetings` e `get_transcript`; o Claude Desktop passa a ler as reuniões sozinho.
- **Copiar (📋):** uma fala por linha, com data e hora reais:
  ```
  Reunião: 2026-09-29 | 15:52 | Assunto
  Duração: 00:00:22 | Participantes: Pessoa 1, Eu

  2026-09-29 15:52:02 | Pessoa 1 | Conta, Carlos. Por que você está tão animado?
  ```

### 4.8 Assunto automático
Ao parar, o Claude gera um título curto (até 8 palavras) e a lista passa a mostrar `AAAA-MM-DD | hh:mm | Assunto`. Sem chave/rede, fica
"Sem assunto" (sem prejuízo).

---

## 5. Arquivos

### 5.1 Por reunião — `reunioes\AAAA-MM-DD_HHMM\`
| Arquivo | Conteúdo |
|---|---|
| `audio.wav` | estéreo 16 kHz (L = mic, R = reunião) |
| `transcricao.jsonl` | uma fala por linha: `t0`, `t1`, `source` (mic/loop), `text`, `speaker`, `words`, `echo`, `recovered` |
| `transcricao.md` | transcrição legível |
| `meta.json` | assunto, partes, nomes (`names`), quais foram automáticos (`auto_names`), convidados da agenda |
| `falantes_meet.jsonl` | avisos da extensão (segundo, nome, começou/parou) |
| `chat.json` | conversa com o Claude e o consumo de cada resposta |
| `transcricao.jsonl.bak` | backup antes de reprocessar/identificar |
| `app.log` | log da gravação |

### 5.2 Do app — `%APPDATA%\jotbrief\`
`config.toml` · `people.json` (nomes cadastrados) · `voices.json` (impressões de voz) · `prompts.json` (pedidos do botão do Claude) ·
`cotacao.json` (dólar em R$) · `models\` (modelos de separação de voz).

### 5.3 Configuração (`config.toml`)
| Chave | Padrão | Para quê |
|---|---|---|
| `language` | `pt` | idioma da transcrição (`pt`, `en`, `auto`) |
| `device` | `auto` | `auto`, `cuda` ou `cpu` |
| `model_gpu` / `model_cpu` | `large-v3-turbo` / `small` | modelos do Whisper |
| `output_dir` | `reunioes` | onde ficam as reuniões |
| `claude_model` | `claude-sonnet-5-5` | modelo do chat e do assunto |
| `chat_effort` | `medium` | esforço do Claude no chat (`low`…`max`) |
| `chat_open` | `true` | coluna do chat visível |
| `claude_project_url` | — | projeto do claude.ai |
| `skill_name` | `jb-jot-brief-transcricao` | nome da skill (vai no início da mensagem) |
| `auto_send` | `true` | aperta Enter sozinho no navegador |
| `ask_in_app` | `false` | `true`: o botão pergunta o que gerar no app (senão a skill pergunta no Claude) |
| `calendar_ics_url` | vazio | endereço secreto iCal do Google Agenda |
| `diarization_threshold` | `0.3` | separação de vozes (menor = separa mais) |
| `num_speakers` | `0` | nº de pessoas, se souber (0 = automático) |
| `voice_match_threshold` / `voice_match_margin` | `0.75` / `0.05` | rigor do reconhecimento por voz |
| `speaker_threshold` | `0.55` | separação sem o modelo de troca de voz |
| `silence_ms` / `max_segment_s` | `600` / `15` | corte das falas |
| `mic_device` / `loopback_device` | — | índices dos dispositivos (`jotbrief devices`) |
| `theme` / `volume` / `floating` | `claro` / `100` / `false` | aparência e modo balão |

---

## 6. Linha de comando

`uv run jotbrief <comando>`

| Comando | Faz |
|---|---|
| `gui` | abre a janela |
| `run` | grava e transcreve no terminal (Ctrl+C para parar) |
| `devices` | lista dispositivos de áudio |
| `setup` | baixa/carrega os modelos |
| `identify <pasta> [--people N]` | separa as vozes de uma reunião (usado pelo app, em processo separado) |
| `learn-voices` | aprende as vozes das pessoas já nomeadas nas reuniões salvas |
| `subjects` | gera o assunto das reuniões "Sem assunto" |
| `check-key` | testa a `ANTHROPIC_API_KEY` |
| `skill` | gera a skill do Claude (`skills\`) |
| `mcp` / `mcp-config` / `mcp-install` | servidor MCP; mostra a configuração; instala no Claude Desktop (feche-o antes) |

---

## 7. Arquitetura (para quem for mexer)

```
audio.py ─ Track/StereoRecorder ─► session.py ─► transcriber.py (Whisper) ─► transcricao.jsonl
vad.py (silero)                       │   ├─ echo.py (eco por áudio, recuperação)
                                      │   └─ meet_names.py / meet_bridge.py (extensão)
speakers.py (separação)  voices.py (reconhecimento)  people.py  agenda.py (convidados)
reprocess.py   jobs.py (identify em processo separado)
chat.py (Claude: streaming, preços, uso)   fx.py (dólar→R$)   summarize.py (assunto)
claude_link.py  prompts.py  skill.py  auto_send.py  claude_config.py  mcp_server.py  meetings.py
ui.py (PySide6)  ui_helpers.py (partes sem Qt)       extension/ (Chrome)
```

- **Regra de ouro da UI:** workers → UI só por `Signal`.
- **Trabalho pesado fora da janela:** a separação de vozes roda em outro processo (`jobs.run_identify`), porque era código nativo que
  congelava a interface.
- **Eco:** `echo.EnvelopeLog` guarda o volume dos dois canais ao vivo; `echo.mark_echo_by_audio` repete a medição no áudio completo
  (ao identificar falantes e ao reprocessar).
- **Tempo:** a linha do tempo da sessão (`session.now()`) é o relógio de tudo: falas, avisos do Meet e posição no áudio; ao retomar uma
  reunião, soma o que já foi gravado.
- **Testes:** `uv run pytest -q` (≈ 95 testes: lógica pura, UI sem tela (offscreen), extensão, formatos). Os que baixam modelos são
  marcados `slow`.

---

## 8. Privacidade e segurança
- **LGPD:** gravar e transcrever reuniões exige o consentimento dos participantes (o aviso fica no rodapé). Avise antes de iniciar.
- **Áudio e voz ficam no seu PC.** Impressões de voz são dado biométrico: só em `voices.json`, nunca enviadas.
- **O que vai para a Anthropic:** o texto da transcrição (e o pedido), só quando você usa o chat, gera o assunto ou manda para o Claude.
- **Chave da API:** só no `.env`; nunca no código, no Git ou em mensagens.
- **Extensão do Chrome:** fala só com `127.0.0.1`; o app recusa pedidos de sites.
- **Agenda:** o endereço iCal secreto equivale a uma senha de leitura da agenda; guarde-o só no `config.toml` (se vazar, use
  "Redefinir" no Google Agenda).
- **Exclusão:** vai para a Lixeira do Windows.

---

## 9. Problemas conhecidos e limites
| Situação | O que acontece / o que fazer |
|---|---|
| Duas pessoas falam ao mesmo tempo | O canal da reunião transcreve a voz mais forte. A outra só aparece se vazou pelo mic (sem fone) e o Meet confirmou a fala simultânea |
| Sem fone de ouvido | Pode sobrar algum eco; o app filtra pelo volume. Fone é o ideal |
| Muitas pessoas "fantasma" na separação | Informe o número de pessoas em 👥 ou aumente `diarization_threshold` |
| Nome de voz errado | Corrija no ✏; a correção manual vale mais e nunca é sobrescrita |
| App Claude do Windows | Não aceita texto + projeto: botão é manual (abre o projeto, você cola) |
| Extensão não mostra o nome certo | Recarregue a extensão e a aba do Meet; veja o selo `[JB - Jot Brief]` e o Console (F12) com `[JotBrief]` |
| Não consigo excluir uma reunião | Não dá enquanto ela está sendo gravada; pare a gravação primeiro |
| Chat sem resposta | Veja a mensagem no painel: normalmente chave ausente/inválida ou sem internet (`uv run jotbrief check-key`) |
| Custo do chat | Cada pergunta reenvia a transcrição como contexto (com cache). Reuniões longas custam mais por pergunta |
| Teams/Zoom desktop | A captura de áudio funciona para qualquer app; os **nomes automáticos pelo Meet** só valem para o Meet no navegador |

---

## 10. Glossário
- **Loopback:** áudio que sai do computador (a voz dos outros na reunião).
- **Pessoa N:** rótulo automático de uma voz separada.
- **Eco/vazamento:** o microfone captando o alto-falante.
- **Esforço:** quanto o Claude "pensa" antes de responder (mais esforço = mais lento e mais caro).
- **MCP:** protocolo pelo qual o Claude Desktop lê as reuniões como ferramenta.
- **Skill:** pacote de instruções que você instala no Claude para tratar transcrições do JB.

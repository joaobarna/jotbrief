# SaidKeep

> Antes chamado **JB - Jot Brief**. Quem já usava continua com os dados: ao abrir a versão nova, as reuniões e a configuração são movidas sozinhas.

Transcreve reuniões (Meet/Teams/Zoom) no Windows, sem bot: captura o áudio do sistema (loopback WASAPI) e o microfone, transcreve localmente com Whisper (faster-whisper) e leva a transcrição para o Claude, onde você pede ata, resumo, tarefas etc.

> Documentação completa de tudo o que o app faz: [DOCUMENTACAO.md](DOCUMENTACAO.md)

## Uso
```
uv sync --extra cuda          # GPU NVIDIA; sem GPU: uv sync
copy .env.example .env        # ANTHROPIC_API_KEY (só p/ gerar o assunto da call)
uv run saidkeep setup         # baixa modelos (~1,6 GB)
uv run saidkeep gui           # janela
uv run saidkeep run           # CLI (Ctrl+C para parar)
uv run saidkeep devices
```
Saída em `reunioes/AAAA-MM-DD_HHMM/`: `audio.wav` (L=mic, R=reunião), `transcricao.jsonl`, `transcricao.md`, `meta.json` (assunto e partes).

## Formato da transcrição copiada
Uma fala por linha, com data e hora reais (início da call + posição no áudio), no formato ideal para colar numa IA:
```
Reunião: 2026-09-29 | 15:52 | Assunto
Duração: 00:00:22 | Participantes: Pessoa 1, Pessoa 2, Eu

2026-09-29 15:52:02 | Pessoa 1 | Conta, Carlos. Por que você está tão animado?
2026-09-29 15:52:19 | Eu | Legal, deu para ver bem a diferenciação.
```

## Identificar falantes (👥)
Separa as vozes do canal da reunião (Pessoa 1, 2…), inclusive quando duas pessoas falam na mesma fala. Ao clicar, informe quantas pessoas falam (sem contar você): isso separa melhor vozes parecidas. Roda local; baixa dois modelos pequenos (~32 MB) na primeira vez.
Ajustes em `config.toml`: `diarization_threshold` (menor = separa mais) e `num_speakers`.

## Reconhecer pessoas pela voz
Quando você dá um nome a uma pessoa (clicando no nome na bolha), o app guarda a **impressão da voz** dela e, nas próximas reuniões, ao identificar os falantes (👥, ou automaticamente ao parar a gravação), já coloca o nome de quem reconhecer. Nomes reconhecidos sozinhos têm a borda tracejada e a dica "Reconhecido pela voz"; se estiver errado, é só clicar e corrigir (a correção também ensina o app). Nomes que você digitou nunca são trocados pelo reconhecimento.
- `uv run saidkeep learn-voices` aprende de uma vez as pessoas que você já nomeou nas reuniões salvas.
- Ajustes em `config.toml`: `voice_match_threshold` (padrão 0,75; maior = mais rígido) e `voice_match_margin`.
- **Privacidade:** impressão de voz é dado biométrico. Fica só no seu PC, em `%APPDATA%\saidkeep\voices.json`, e nada é enviado a lugar nenhum. Para esquecer todas as vozes, apague o arquivo; para esquecer uma pessoa, use "Esquecer este nome" no diálogo de nome.

## Reprocessar (🔄)
Transcreve o `audio.wav` da reunião selecionada de novo, com o idioma que você escolher e os filtros atuais (descarta legendas-fantasma tipo "Legenda Adriana Zanotto", textos em outro alfabeto e o eco do microfone). Opcionalmente já identifica os falantes. A transcrição anterior fica salva como `transcricao.jsonl.bak-...` na pasta da reunião; nomes, assunto e partes são mantidos. Leva cerca de 1/10 da duração do áudio numa GPU NVIDIA (7 min de call em ~40 s).

## Automático: servidor MCP (Claude Desktop lê as reuniões sozinho)
`uv run saidkeep mcp` sobe um servidor MCP **somente leitura** com as ferramentas `list_meetings` e `get_transcript` e os mesmos pedidos do botão do Claude como atalhos (Ata da reunião, Resumos, Tarefas…). Assim, em vez de colar, você pede no chat do Claude Desktop: "ata da última reunião do SaidKeep".
**Instalação:** feche o Claude Desktop por completo (bandeja → Sair), rode `uv run saidkeep mcp-install` num terminal comum (fora do Claude) e abra o Claude de novo. O comando recusa rodar com o Claude aberto (ele reescreve a configuração ao salvar e perderia a alteração), faz backup e preserva o resto do arquivo; detecta a cópia privada da versão da Microsoft Store. `uv run saidkeep mcp-config` só mostra o trecho, sem alterar nada.

## Levar para o Claude (três botões juntos, no box cinza)
- **Estrela com globo** → abre uma conversa nova **dentro do projeto**, no **navegador**, já com o pedido da skill (`skill_name` no `config.toml`), o cabeçalho e a transcrição com data e hora. Você só clica em enviar.
- **Estrela numa janela** → **app Claude do Windows**. O tratador de links do app só aceita `q` em `claude://claude.ai/new` (o parâmetro `project` invalida o link) e abre projetos apenas por id, sem texto. Por isso este botão **abre o projeto** no app e deixa o **texto completo na área de transferência**: clique em "Nova sessão", cole (Ctrl+V) e envie.
- **⚙** → define a URL do projeto (`https://claude.ai/project/…`).
Calls longas no navegador (link acima de ~7,5 mil caracteres) levam o pedido no link e a transcrição fica na área de transferência para colar.
- **Convidados da agenda como sugestão de nome:** cole em `calendar_ics_url` (em `%APPDATA%\saidkeep\config.toml`) o "endereço secreto em formato iCal" do seu Google Agenda (Configurações → sua agenda → Integrar agenda). Ao abrir uma reunião, o app acha o evento daquele horário (inclui semanais) e coloca os convidados no topo da lista de nomes. Ao nomear uma pessoa, a voz dela já é aprendida sozinha.
- **Nomes automáticos pelo Meet (extensão do Chrome, experimental):** a pasta `extension/` é uma extensão que observa quem está falando no Google Meet e avisa o app (só em `127.0.0.1`, porta 47821; o app recusa pedidos de páginas da web). Enquanto você grava, o app guarda `falantes_meet.jsonl`; ao identificar os falantes, cruza os trechos em que UMA pessoa falava sozinha com cada "Pessoa N" e dá o nome (nunca por cima de um nome que você digitou) e ainda aprende a voz. Instalar: `chrome://extensions` → Modo do desenvolvedor → "Carregar sem compactação" → pasta `extension`. Um selo no canto inferior esquerdo do Meet mostra quem a extensão vê falando (para ajustar se o Meet mudar; `DEBUG` em `content.js`).
- **Envio automático (navegador):** com `auto_send = true` (padrão) o app espera a página do Claude carregar e aperta Enter; em calls longas cola a transcrição (Ctrl+V) antes. Só age se a janela em primeiro plano for uma página NOVA do Claude (o título da janela precisa mudar depois de abrir o link e ficar estável por ~3,5 s); se você trocar de janela, não envia. Desligue com `auto_send = false`. O botão do app do Windows não envia sozinho. O nome da conversa e os botões de copiar (nome + pedidos) vêm da skill, dentro do Claude.

## Notas
- Use headset para evitar eco (há dedupe, mas headset é melhor).
- Avise os participantes: gravar exige consentimento (LGPD).

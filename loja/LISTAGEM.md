# Chrome Web Store: pacote e textos da publicação

Extensão **SaidKeep: nomes no Google Meet** (versão 1.0.0). Este documento reúne tudo o que o painel da loja pede.

- **Pacote para enviar:** `dist/saidkeep-extensao-1.0.0.zip` (gere com `uv run python scripts/pack_extension.py`)
- **Política de privacidade (endereço público):**
  - Português: https://joao-barnabe.com/saidkeep/privacidade/
  - Inglês: https://joao-barnabe.com/en/saidkeep/privacy/
- **Site/suporte:** https://joao-barnabe.com/saidkeep/
- **Imagens (nesta pasta):**
  - `screenshot-1-app.png` (1280x800): o app SaidKeep com os nomes das pessoas (dados fictícios)
  - `screenshot-2-extensao.png` (1280x800): o popup da extensão nos estados "gravando" e "app fechado"
  - `cartao-promocional-440x280.png`: cartão promocional pequeno
  - O ícone de 128 px já vai dentro do pacote.

---

## 1. Cadastro na loja (uma vez)

1. Entre em https://chrome.google.com/webstore/devconsole com a sua conta Google.
2. Aceite o contrato de desenvolvedor e pague a **taxa única de US$ 5**.
3. Confirme o e-mail de contato. Se perguntar se você é "trader" (comerciante, regra da União Europeia): extensão gratuita e pessoal, escolha **não comerciante**.
4. Ative a verificação em duas etapas na conta, se ainda não estiver (a loja exige).

## 2. Enviar o pacote

1. **Add new item** → envie o `.zip`.
2. Aba **Store listing**: preencha com os textos abaixo, envie as imagens e escolha:
   - **Category:** Productivity
   - **Language:** Portuguese (Brazil), com a listagem em inglês adicionada em "Add language"
3. Aba **Privacy**: preencha como na seção 3.
4. Aba **Distribution**: **Visibility = Unlisted** na primeira vez (só quem tem o link instala; dá para testar a instalação pela loja). Depois de testar, mude para **Public**. Regiões: todas.
5. **Submit for review.** A análise costuma levar de 1 a 3 dias, às vezes mais na primeira publicação.

---

## 3. Aba Privacy (campos e respostas)

**Single purpose (finalidade única):**
> Show which participant is speaking in Google Meet to the user's SaidKeep desktop app, so the voices in the transcript can be named.

**Permission justification:**

| Permissão | Justificativa (em inglês, como a loja pede) |
|---|---|
| `host permission: http://127.0.0.1:47821/*` | Send "participant started/stopped speaking" notices to the companion desktop app that runs on the user's own computer (localhost). No external server is contacted. |
| `content script on https://meet.google.com/*` | Read the participants' display names and the "speaking" indicator on the call page, only while a Meet page is open. |
| `alarms` | Check every 30 seconds whether the local app is recording, to show a red dot on the toolbar icon even when no Meet tab is open. |
| `storage` | Remember one local preference: show or hide the on-page badge. |

**Remote code:** *No, I am not using remote code.*

**Data usage (o que a extensão trata):** marque
- *Personally identifiable information* (nomes de exibição dos participantes) e
- *Website content* (o indicador de "falando" da página do Meet).

Marque as três certificações: não vende dados a terceiros; não usa nem transfere dados para finalidades alheias ao propósito único; não usa nem transfere dados para avaliar crédito ou para empréstimos.
> Os dados não saem do computador do usuário (só vão ao app local), mas declarar é o mais seguro e coerente com a política publicada.

**Privacy policy URL:** https://joao-barnabe.com/saidkeep/privacidade/

**Instruções para o revisor (campo "Test instructions"):**
> This extension is a companion to a free Windows desktop app (SaidKeep) that transcribes meetings locally. No account or login is needed.
> To verify WITHOUT the app: open any Google Meet call (e.g. https://meet.google.com/new). A small dark badge appears at the bottom-left reading "[SaidKeep] nobody speaking · app closed ✗". Click the toolbar icon: the popup says "The SaidKeep app is not open on this computer" and shows a download link; the checkbox hides/shows the badge.
> To verify WITH the app (Windows): download the installer from https://joao-barnabe.com/saidkeep/ and start a recording. The badge then reads "app recording ✓", the toolbar icon gets a red dot, and the names of participants who speak are sent only to the app at 127.0.0.1:47821 (see the privacy policy). The extension contacts no other server.

---

## 4. Textos da listagem

### Português (Brasil)

**Nome:** SaidKeep: nomes no Google Meet

**Resumo (132 caracteres):** Mostra ao app SaidKeep (Windows) quem está falando no Google Meet, para dar nome às vozes da transcrição.

**Descrição detalhada:**

```
Veja quem está falando no Google Meet e dê nome às vozes da sua transcrição.

Esta extensão é a companheira do app SaidKeep (Windows), que transcreve reuniões no seu computador, sem bot na chamada. Durante uma reunião no Google Meet, a extensão observa quem está falando e avisa o app. Assim, a transcrição mostra "Ana: ..." em vez de "Pessoa 2".

COMO FUNCIONA
1. Instale o app SaidKeep no Windows (gratuito): https://joao-barnabe.com/saidkeep/
2. Instale esta extensão.
3. Entre numa reunião no Google Meet e grave pelo app. Os nomes aparecem nas falas, ao vivo.

O QUE A EXTENSÃO FAZ
• Descobre qual participante está falando e avisa o app que roda no seu computador.
• Mostra, se você quiser, um selo discreto no Meet com o estado da conexão (dá para esconder pelo ícone da extensão).
• Mostra no ícone um círculo vermelho quando o app está gravando.

PRIVACIDADE
• Nada é enviado para servidores: os avisos vão somente para o app SaidKeep, no seu próprio computador (127.0.0.1).
• Lê apenas os nomes de exibição e o indicador de "falando" que já aparecem na página. Não lê áudio, vídeo, chat nem e-mails.
• Sem anúncios, sem análise de uso, sem código remoto.
• Política de privacidade: https://joao-barnabe.com/saidkeep/privacidade/

REQUISITOS
• App SaidKeep para Windows: https://joao-barnabe.com/saidkeep/
• Google Meet no navegador.

AVISOS
• Gravar e transcrever reuniões exige o consentimento dos participantes (LGPD). Avise antes de iniciar.
• Esta extensão não é afiliada, endossada nem patrocinada pelo Google. "Google Meet" é marca do Google LLC.
```

### English

**Name:** SaidKeep: names in Google Meet

**Summary (132 chars max):** Tells the SaidKeep Windows app who is speaking in Google Meet, so transcript voices get real names.

**Detailed description:**

```
See who is speaking in Google Meet and give names to the voices in your transcript.

This extension is the companion to the SaidKeep app (Windows), which transcribes meetings on your own computer, with no bot in the call. During a Google Meet meeting, the extension watches who is speaking and tells the app. The transcript then shows "Ana: ..." instead of "Person 2".

HOW IT WORKS
1. Install the SaidKeep app on Windows (free): https://joao-barnabe.com/en/saidkeep/
2. Install this extension.
3. Join a Google Meet meeting and record from the app. Names appear on the lines as they are spoken.

WHAT THE EXTENSION DOES
• Finds out which participant is speaking and tells the app running on your computer.
• Optionally shows a small badge in Meet with the connection status (you can hide it from the extension icon).
• Shows a red dot on the icon while the app is recording.

PRIVACY
• Nothing is sent to servers: notices go only to the SaidKeep app on your own computer (127.0.0.1).
• It reads only the display names and the "speaking" indicator already shown on the page. It does not read audio, video, chat or e-mails.
• No ads, no analytics, no remote code.
• Privacy policy: https://joao-barnabe.com/en/saidkeep/privacy/

REQUIREMENTS
• SaidKeep app for Windows: https://joao-barnabe.com/en/saidkeep/
• Google Meet in the browser.

NOTICES
• Recording and transcribing meetings requires the participants' consent. Let them know before you start.
• This extension is not affiliated with, endorsed by or sponsored by Google. "Google Meet" is a trademark of Google LLC.
```

---

## 5. Depois da aprovação

- Troque para **Public** (se começou como Unlisted).
- Copie o endereço da extensão na loja e me passe: eu coloco o botão **"Instalar a extensão"** na página do SaidKeep no site e atualizo a documentação, que hoje ensina a instalação "sem compactação".
- A cada nova versão: aumente o `version` em `extension/manifest.json`, rode `uv run python scripts/pack_extension.py` e envie o novo `.zip` em **Package → Upload new package**. A loja revisa de novo.

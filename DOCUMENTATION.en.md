# JB - Jot Brief — documentation

A Windows app that **transcribes meetings (Google Meet, Teams, Zoom) without a bot**, separates and names who is speaking, and takes the
conversation to Claude (chat inside the app, a claude.ai project, or the Claude app for Windows).
Everything audio-related runs **on your computer**; only the text goes to Claude, when you ask for it.

> This documentation describes the app as it is today. To install it and use it day to day, also see the `README.md`.

---

## 1. Overview

| What it does | How |
|---|---|
| Records the meeting **without a bot** | Captures the audio that comes out of your speakers/headset (WASAPI loopback) + your microphone |
| Transcribes **locally** | Whisper (faster-whisper) on your NVIDIA GPU; without one, it uses the CPU with a smaller model |
| Shows the conversation **live** | Chat-style bubbles that follow the audio; you on the right, the meeting on the left |
| Separates and names people | Voice separation + voice recognition + names seen in Meet + calendar invitees |
| Chats with Claude **during the meeting** | Chat column with ready-made buttons (summary, tasks, questions to ask…) |
| Takes it to Claude | Browser, Windows app, or MCP server (Claude Desktop reads the meetings on its own) |

**Costs:** transcription, voice separation, and recognition are free (they run locally). What uses the Anthropic API
(with your `ANTHROPIC_API_KEY`) is the **panel chat** and the meeting's **automatic subject**. The app shows token usage
and the estimated cost in USD and in BRL (R$).

---

## 2. Installation and first use

Requirements: Windows 11, Python 3.12 (managed by `uv`), and, for speed, an NVIDIA GPU.

```
uv sync --extra cuda          # with an NVIDIA GPU; without a GPU: uv sync
copy .env.example .env        # fill in ANTHROPIC_API_KEY
uv run jotbrief setup         # downloads the transcription models (~1.6 GB)
uv run jotbrief gui           # opens the window
```

- The API key lives **only** in the `.env` file (it never goes to Git or onto the screen).
- The voice separation models (≈ 32 MB) are downloaded the first time you use 👥.
- Audio devices: `uv run jotbrief devices` lists them; by default the app uses the Windows defaults.

**First recording:** open the app → choose the language (Português, Inglês, or Automático — Portuguese, English, or Automatic) → click the round record button →
speak/listen to the meeting → click again to stop. The meeting shows up in the list on the left.

---

## 3. The window

```
┌──────────────┬───────────────────────────────┬──────────────────┐
│  Meeting     │  ● 00:00:00   + Nova reunião   │  Claude          │
│  list        │  [button bar]                  │  model · effort  │
│  (by day)    │  Gravando em: title            │  usage (US$/R$)  │
│              │  audio player                  │  [ready buttons] │
│              │  transcript bubbles            │  conversation    │
│              │                                │  [question ↑]    │
├──────────────┴───────────────────────────────┴──────────────────┤
│  LGPD notice                                                     │
└──────────────────────────────────────────────────────────────────┘
```

### 3.1 Meeting list (left)
- Each meeting is a card: **`YYYY-MM-DD | hh:mm | Subject`** (date and time in bold), number of utterances and, if a task is in
  progress, the line `⏳ identificando falantes…` (identifying speakers…).
- Grouped by day; the day button (**`▾ HOJE · 2026-10-02 (7)`**, where HOJE = TODAY) collapses/expands it. When you open the app, only the latest day with a transcript
  is open. The selected meeting, or the one being recorded, is never hidden.
- **Buscar reuniões** (Search meetings): searches the title and the text of the transcripts.
- 🗑 moves the meeting to the **Windows Recycle Bin** (you can recover it). It won't let you delete the one being recorded.
- **+ Nova reunião** (New meeting) leaves none selected: the next recording creates a new one (a "Nova reunião" row appears at the top).
  Recording with a meeting selected **continues it** (it becomes "Parte 2" (Part 2), with a separator).

### 3.2 Button bar (center)
| Group | Buttons |
|---|---|
| Record (Gravar) | Record/stop + time · **Nova reunião** (New meeting) · language |
| Claude | ✳🌐 browser · ⚙ project · ✳🪟 Windows app (manual) |
| People | 👥 identify speakers · ✏ assign names |
| Reprocess | 🔄 transcribes the audio again |
| Folder | 📁 opens the meeting folder |
| Copy | 📋 copies the transcript in the ideal format for AI |
| Chat | 💬 shows/hides the Claude column |
| Visual | 🎈 balloon mode · light/dark theme |

### 3.3 Bubbles and player
- You ("Eu" = Me) on the right, in green; the meeting on the left, one color per person. Partial text appears dotted and becomes
  final when the utterance closes.
- Click the **name** on a bubble to rename the person (this also teaches the app their voice).
- **Player:** play/pause, ±10 s, position bar, volume. The text **follows the audio** like song lyrics; **"▶ Ouvir parte"** (Play section)
  plays just one section. The ↓ button jumps to the end; during recording the screen scrolls on its own.
- **Balloon mode (🎈):** when recording, the window turns into a floating bar with the latest utterance.

### 3.4 Chat with Claude (right)
- **Ready-made buttons:** 📝 Resumo detalhado (Detailed summary) · ⚡ Resumo rápido (Quick summary) · 🎯 Pontos-chave (Key points) · ✅ Decisões e tarefas (Decisions and tasks) · ❓ Em aberto (Open items) ·
  💡 Perguntas para fazer (Questions to ask) · 🔎 Última fala (Last utterance). The text of the request appears when you hover over the button.
- **Free conversation:** type and press Enter (Shift+Enter breaks the line). The answer arrives gradually; ■ interrupts it.
- **During recording** Claude reads the transcript **up to that moment** (refreshed with every question).
- **Model** (Sonnet 5.5, Opus 5.5, or Haiku 4.5) and **effort** (low → max) are chosen at the top; they apply to the whole app
  (chat and subject). Haiku has no effort setting.
- **Usage:** last answer and meeting total (input tokens, the part that came from cache, output), estimated cost in
  **USD and BRL (R$)** (current exchange rate, refreshed every hour; the source and time are shown in the panel).
- Each meeting has its own conversation, saved in `chat.json` in its folder. 🗑 clears it.

---

## 4. How each feature works

### 4.1 Capture and transcription
- **Two channels** recorded into a stereo 16 kHz `audio.wav`: **left = your microphone, right = the meeting audio**.
- A speech detector (silero-vad, running via ONNX, without PyTorch) cuts the audio into chunks; each chunk goes to Whisper. There are filters against "hallucinations"
  (ghost subtitles such as "Legenda Adriana Zanotto" (a Portuguese subtitle credit), text in another alphabet, repeated phrases).
- Language: Português, Inglês, or **Automático** (chooses between pt and en per chunk).

### 4.2 Microphone echo (without a headset)
If the microphone "hears" the speaker, the meeting sound would come back as if it were you. The app handles this in layers:
1. **Text:** discards mic utterances that repeat what the meeting said at the same moment.
2. **Audio, live and after stopping:** compares the volume of the two channels over time. It is leakage when the **microphone is
   extremely quiet** (≤ 0.002 measured) while the meeting is speaking; **your voice**, even on top of the meeting, is 10–40× louder and
   is never hidden.
3. **Recovery:** when two people talk at once, the meeting channel only transcribes the stronger voice; the other may have been left only in the
   mic leakage. If Meet confirms 2+ people speaking together and the text does not exist in the meeting channel, the chunk comes back as an utterance
   (with the name of whoever talked over the other).

> **Limit:** with a **headset** the mic doesn't pick up the meeting; so there is no echo, but a second voice talking over the first is not
> recorded. Only capturing each participant's audio separately would solve this (not implemented).

### 4.3 Identify speakers (👥)
- Separates the voices in the meeting channel into **Pessoa 1, 2…** (Person 1, 2…) (local models: pyannote segmentation + voice embeddings via
  sherpa-onnx), including splitting an utterance in which two people alternate.
- Runs **automatically when you stop** the recording, in a **separate process** (the window doesn't freeze) — ~1 min for 9 min of audio.
- When you click it manually you can enter how many people are speaking (not counting you); this separates similar voices better.
- Settings in `config.toml`: `diarization_threshold` (lower = separates more; 0.3 default) and `num_speakers`.

### 4.4 Assigning names to people
Four sources, from weakest to strongest (what you type is **never** overwritten):
1. **Voice recognition:** when you name someone, the app stores their **voice print** and, in future meetings, assigns the name on its own
   (`voice_match_threshold` 0.75 and `voice_match_margin` 0.05). It is biometric data: it stays only in `%APPDATA%\jotbrief\voices.json`
   (delete the file to forget everyone).
2. **Calendar invitees:** with `calendar_ics_url` (the secret iCal address of Google Calendar), the app finds the event at that time
   (including weekly/daily meetings) and puts the invitees at the top of the name list.
3. **Names seen in Meet** (Chrome extension, below): matches who Meet showed speaking alone with each voice.
4. **You:** by clicking the name on the bubble or ✏ (a list of people already registered + typing a new one).

### 4.5 Chrome extension (Google Meet)
`extension/` folder — install at `chrome://extensions` → Developer mode → **Load unpacked** → `extension` folder.
- It watches the Meet page and tells the app who is speaking. It shows a badge in the bottom-left corner:
  `[JB - Jot Brief] Name · app gravando ✓` (app recording ✓; it also says whether the app is closed or not recording).
- **Extension icon:** the green JB; it gets a **red circle** when the app is recording.
- **Live:** when only one person is speaking, the bubble already comes out with their name. After you stop, the voice matching redoes the names and
  learns the voice.
- **Security:** it only talks to `127.0.0.1:47821`; the app refuses requests coming from web pages (it requires a header that only the extension
  sends).
- The notices are kept in `falantes_meet.jsonl` in the meeting folder.
- It is **experimental**: Meet doesn't expose "who is speaking" in a stable way, so detection is based on interface activity and may need
  adjusting if Meet changes (`DEBUG` in `content.js` keeps the badge visible).

### 4.6 Reprocess (🔄)
Transcribes `audio.wav` again with the current language and filters (backing up the previous transcript to `transcricao.jsonl.bak`),
optionally identifying the speakers right away. Useful after improvements to the app or to fix the language.

### 4.7 Taking it to Claude
- **✳🌐 Browser:** opens a new conversation **inside your project** on claude.ai with the skill's request + the transcript. With
  `auto_send = true` the app waits for the page to load and presses Enter (only if the front window is a new Claude page).
  Long calls (> ~7,500 characters in the link) carry the request in the link and the transcript stays on the clipboard for you to paste.
- **✳🪟 Windows app (manual):** the Claude app only accepts text in new conversations outside projects. So the button opens the project
  and copies the text: click "Nova sessão" (New session) and paste (Ctrl+V).
- **⚙ Project:** sets the project URL (`https://claude.ai/project/…`).
- **`jb-jot-brief-transcricao` skill:** `uv run jotbrief skill` generates the `.zip` (and the `painel.html`) to upload to Claude. The skill asks
  what to generate and delivers the suggested conversation name and copy buttons.
- **MCP server:** `uv run jotbrief mcp-install` (with Claude Desktop **closed**) registers a **read-only** server with
  `list_meetings` and `get_transcript`; Claude Desktop then reads the meetings on its own.
- **Copy (📋):** one utterance per line, with real date and time:
  ```
  Reunião: 2026-09-29 | 15:52 | Assunto
  Duração: 00:00:22 | Participantes: Pessoa 1, Eu

  2026-09-29 15:52:02 | Pessoa 1 | Conta, Carlos. Por que você está tão animado?
  ```

### 4.8 Automatic subject
When you stop, Claude generates a short title (up to 8 words) and the list starts showing `YYYY-MM-DD | hh:mm | Subject`. Without a key/network, it stays as
"Sem assunto" (No subject) (no harm done).

---

## 5. Files

### 5.1 Per meeting — `reunioes\YYYY-MM-DD_HHMM\`
| File | Contents |
|---|---|
| `audio.wav` | stereo 16 kHz (L = mic, R = meeting) |
| `transcricao.jsonl` | one utterance per line: `t0`, `t1`, `source` (mic/loop), `text`, `speaker`, `words`, `echo`, `recovered` |
| `transcricao.md` | readable transcript |
| `meta.json` | subject, parts, names (`names`), which ones were automatic (`auto_names`), calendar invitees |
| `falantes_meet.jsonl` | extension notices (second, name, started/stopped) |
| `chat.json` | conversation with Claude and the usage of each answer |
| `transcricao.jsonl.bak` | backup before reprocessing/identifying |
| `app.log` | recording log |

### 5.2 App-level — `%APPDATA%\jotbrief\`
`config.toml` · `people.json` (registered names) · `voices.json` (voice prints) · `prompts.json` (the Claude button's requests) ·
`cotacao.json` (dollar rate in BRL) · `models\` (voice separation models).

### 5.3 Configuration (`config.toml`)
| Key | Default | What for |
|---|---|---|
| `language` | `pt` | transcription language (`pt`, `en`, `auto`) |
| `device` | `auto` | `auto`, `cuda`, or `cpu` |
| `model_gpu` / `model_cpu` | `large-v3-turbo` / `small` | Whisper models |
| `output_dir` | `reunioes` | where the meetings are stored |
| `claude_model` | `claude-sonnet-5-5` | model for the chat and the subject |
| `chat_effort` | `medium` | Claude's effort in the chat (`low`…`max`) |
| `chat_open` | `true` | chat column visible |
| `claude_project_url` | — | claude.ai project |
| `skill_name` | `jb-jot-brief-transcricao` | skill name (goes at the start of the message) |
| `auto_send` | `true` | presses Enter on its own in the browser |
| `ask_in_app` | `false` | `true`: the button asks what to generate in the app (otherwise the skill asks in Claude) |
| `calendar_ics_url` | empty | secret iCal address of Google Calendar |
| `diarization_threshold` | `0.3` | voice separation (lower = separates more) |
| `num_speakers` | `0` | number of people, if you know it (0 = automatic) |
| `voice_match_threshold` / `voice_match_margin` | `0.75` / `0.05` | strictness of voice recognition |
| `speaker_threshold` | `0.55` | separation without the voice-change model |
| `silence_ms` / `max_segment_s` | `600` / `15` | utterance cutting |
| `mic_device` / `loopback_device` | — | device indexes (`jotbrief devices`) |
| `theme` / `volume` / `floating` | `claro` / `100` / `false` | appearance and balloon mode (`claro` = light) |

---

## 6. Command line

`uv run jotbrief <command>`

| Command | What it does |
|---|---|
| `gui` | opens the window |
| `run` | records and transcribes in the terminal (Ctrl+C to stop) |
| `devices` | lists audio devices |
| `setup` | downloads/loads the models |
| `identify <folder> [--people N]` | separates the voices of a meeting (used by the app, in a separate process) |
| `learn-voices` | learns the voices of people already named in the saved meetings |
| `subjects` | generates the subject for meetings with "Sem assunto" |
| `check-key` | tests the `ANTHROPIC_API_KEY` |
| `skill` | generates the Claude skill (`skills\`) |
| `mcp` / `mcp-config` / `mcp-install` | MCP server; shows the configuration; installs it in Claude Desktop (close it first) |

---

## 7. Architecture (for anyone who will tinker with it)

```
audio.py ─ Track/StereoRecorder ─► session.py ─► transcriber.py (Whisper) ─► transcricao.jsonl
vad.py (silero)                       │   ├─ echo.py (audio echo, recovery)
                                      │   └─ meet_names.py / meet_bridge.py (extension)
speakers.py (separation)  voices.py (recognition)  people.py  agenda.py (invitees)
reprocess.py   jobs.py (identify in a separate process)
chat.py (Claude: streaming, prices, usage)   fx.py (dollar→BRL)   summarize.py (subject)
claude_link.py  prompts.py  skill.py  auto_send.py  claude_config.py  mcp_server.py  meetings.py
ui.py (PySide6)  ui_helpers.py (Qt-free parts)       extension/ (Chrome)
```

- **UI golden rule:** workers → UI only via `Signal`.
- **Heavy work outside the window:** voice separation runs in another process (`jobs.run_identify`), because it was native code that
  froze the interface.
- **Echo:** `echo.EnvelopeLog` stores the volume of both channels live; `echo.mark_echo_by_audio` repeats the measurement on the full audio
  (when identifying speakers and when reprocessing).
- **Time:** the session timeline (`session.now()`) is the clock for everything: utterances, Meet notices, and position in the audio; when resuming a
  meeting, it adds what has already been recorded.
- **Tests:** `uv run pytest -q` (≈ 95 tests: pure logic, UI without a screen (offscreen), extension, formats). The ones that download models are
  marked `slow`.

---

## 8. Privacy and security
- **LGPD (Brazil's data protection law):** recording and transcribing meetings requires the participants' consent (the notice is in the footer). Tell people before you start.
- **Audio and voice stay on your PC.** Voice prints are biometric data: only in `voices.json`, never sent anywhere.
- **What goes to Anthropic:** the transcript text (and the request), only when you use the chat, generate the subject, or send it to Claude.
- **API key:** only in `.env`; never in the code, in Git, or in messages.
- **Chrome extension:** talks only to `127.0.0.1`; the app refuses requests from websites.
- **Calendar:** the secret iCal address is equivalent to a read-only password for your calendar; keep it only in `config.toml` (if it leaks, use
  "Reset" in Google Calendar).
- **Deletion:** goes to the Windows Recycle Bin.

---

## 9. Known issues and limits
| Situation | What happens / what to do |
|---|---|
| Two people speak at the same time | The meeting channel transcribes the stronger voice. The other only shows up if it leaked through the mic (no headset) and Meet confirmed the simultaneous speech |
| No headset | Some echo may remain; the app filters it by volume. A headset is ideal |
| Many "ghost" people in the separation | Enter the number of people in 👥 or raise `diarization_threshold` |
| Wrong voice name | Fix it with ✏; the manual correction carries more weight and is never overwritten |
| Claude app for Windows | Doesn't accept text + project: the button is manual (it opens the project, you paste) |
| Extension doesn't show the right name | Reload the extension and the Meet tab; check the `[JB - Jot Brief]` badge and the Console (F12) with `[JotBrief]` |
| I can't delete a meeting | You can't while it is being recorded; stop the recording first |
| Chat doesn't answer | Check the message in the panel: usually a missing/invalid key or no internet (`uv run jotbrief check-key`) |
| Chat cost | Each question resends the transcript as context (with cache). Long meetings cost more per question |
| Teams/Zoom desktop | Audio capture works for any app; the **automatic names from Meet** only apply to Meet in the browser |

---

## 10. Glossary
- **Loopback:** audio that comes out of the computer (the voice of the others in the meeting).
- **Pessoa N** (Person N)**:** automatic label for a separated voice.
- **Echo/leakage:** the microphone picking up the speaker.
- **Effort:** how much Claude "thinks" before answering (more effort = slower and more expensive).
- **MCP:** the protocol through which Claude Desktop reads the meetings as a tool.
- **Skill:** a package of instructions you install in Claude to handle JB transcripts.

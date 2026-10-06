"""Orquestra uma sessão de gravação/transcrição. Sem dependência de UI."""
from __future__ import annotations

import difflib
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Callable

from . import audio
from .config import Config
from .transcriber import Transcriber, Utterance
from .vad import Segmenter

log = logging.getLogger(__name__)

LABELS = {"mic": "Eu", "loop": "Reunião"}


# ---------- funções puras (testáveis) ----------

def _overlap(a: Utterance | dict, b: Utterance | dict) -> float:
    a0, a1 = (a.t0, a.t1) if isinstance(a, Utterance) else (a["t0"], a["t1"])
    b0, b1 = (b.t0, b.t1) if isinstance(b, Utterance) else (b["t0"], b["t1"])
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    return inter / max(min(a1 - a0, b1 - b0), 1e-6)


def _text(x) -> str:
    return (x.text if isinstance(x, Utterance) else x["text"]).lower()


def _words(text: str) -> list[str]:
    import re
    import unicodedata
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", t)


def is_echo(mic, loops: list, ratio: float = 0.7, sim: float = 0.6) -> bool:
    """Segmento do mic que repete (no tempo e no texto) o que a reunião falou: o microfone captou o alto-falante.

    Além de comparar com um trecho só, junta TODOS os trechos da reunião que cobrem o tempo do mic: o Whisper corta
    as frases em lugares diferentes nos dois canais, então o texto do mic costuma ser a soma de vários trechos.
    """
    m0, m1 = (mic.t0, mic.t1) if isinstance(mic, Utterance) else (mic["t0"], mic["t1"])
    mic_text = _text(mic)
    near = []
    for l in loops:
        if _overlap(mic, l) > ratio and difflib.SequenceMatcher(None, mic_text, _text(l)).ratio() > sim:
            return True
        l0, l1 = (l.t0, l.t1) if isinstance(l, Utterance) else (l["t0"], l["t1"])
        if min(m1, l1) - max(m0, l0) > 0:
            near.append((l0, _text(l)))
    mw = _words(mic_text)
    if len(mw) < 4 or not near:
        return False
    lw = {w for _t, txt in near for w in _words(txt)}
    covered = sum(1 for w in mw if w in lw) / len(mw)  # quanto do que o mic "disse" a reunião já tinha dito
    return covered >= 0.75


def release_logs(folder: Path) -> int:
    """Fecha os arquivos de log abertos dentro de `folder` (o Windows não move/apaga uma pasta com arquivo em uso)."""
    n = 0
    root = Path(folder).resolve()
    for h in list(logging.getLogger().handlers):
        if isinstance(h, logging.FileHandler) and Path(h.baseFilename).resolve().parent == root:
            logging.getLogger().removeHandler(h)
            h.close()
            n += 1
    return n


def clean_records(records: list[dict]) -> list[dict]:
    loops = [r for r in records if r["source"] == "loop"]
    from .transcriber import is_hallucination

    out = [r for r in records if not r.get("echo") and not is_hallucination(r["text"])
           and (r["source"] != "mic" or not is_echo(r, loops))]
    return sorted(out, key=lambda r: r["t0"])


def fmt_time(t: float) -> str:
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def wall_clock(folder_name: str | None, parts: list[dict] | None, t0: float) -> datetime | None:
    """Data e hora reais de uma fala: início da call (nome da pasta) + posição no áudio.

    Com várias partes (a gravação foi retomada), conta a partir da hora em que cada parte começou.
    """
    from .ui_helpers import parse_stamp

    base = parse_stamp(folder_name) if folder_name else None
    if base is None:
        return None
    if not parts:
        return base + timedelta(seconds=t0)
    day, prev, starts = base.date(), None, []
    for p in parts:
        try:
            h, m = (int(x) for x in p["at"].split(":"))
        except (ValueError, KeyError, AttributeError):
            h, m = base.hour, base.minute
        d = datetime.combine(day, dtime(h, m))
        if prev is not None and d < prev:  # passou da meia-noite
            day += timedelta(days=1)
            d += timedelta(days=1)
        prev = d
        starts.append(d)
    idx = max((i for i, p in enumerate(parts) if p["start"] - 0.05 <= t0), default=0)
    return starts[idx] + timedelta(seconds=t0 - parts[idx]["start"])


def speaker_label(r: dict) -> str:
    """Rótulo automático da fala: 'Pessoa 2', 'Eu' ou 'Reunião'."""
    return r.get("speaker") or LABELS.get(r["source"], r["source"])


def speaker_labels(records: list[dict]) -> list[str]:
    """Rótulos que aparecem na reunião, na ordem em que surgem (para nomear as pessoas)."""
    out: list[str] = []
    for r in clean_records(records):
        lb = speaker_label(r)
        if lb not in out:
            out.append(lb)
    return out


def render_transcript(records: list[dict], folder_name: str | None = None, parts: list[dict] | None = None,
                      names: dict[str, str] | None = None) -> str:
    """Uma fala por linha, compacta e fácil para uma IA ler: 'AAAA-MM-DD hh:mm:ss | Quem | fala'."""
    names = names or {}
    lines = []
    for r in clean_records(records):
        who = names.get(speaker_label(r), speaker_label(r))
        dt = wall_clock(folder_name, parts, r["t0"])
        stamp = f"{dt:%Y-%m-%d %H:%M:%S}" if dt else fmt_time(r["t0"])
        lines.append(f"{stamp} | {who} | {' '.join(r['text'].split())}")
    return "\n".join(lines)


def transcript_meta(records: list[dict], names: dict[str, str] | None = None) -> str:
    """'Duração: 00:05:12 | Participantes: Eu, Pessoa 1, Pessoa 2' (na ordem em que aparecem)."""
    recs = clean_records(records)
    if not recs:
        return ""
    names = names or {}
    who: list[str] = []
    for r in recs:
        w = names.get(speaker_label(r), speaker_label(r))
        if w not in who:
            who.append(w)
    return f"Duração: {fmt_time(max(r['t1'] for r in recs))} | Participantes: {', '.join(who)}"


def render_markdown(records: list[dict], title: str = "Transcrição", folder_name: str | None = None,
                    parts: list[dict] | None = None, names: dict[str, str] | None = None) -> str:
    return f"# {title}\n\n{render_transcript(records, folder_name, parts, names)}\n"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------- sessão ----------

class Session:
    def __init__(self, cfg: Config,
                 on_utterance: Callable[[Utterance], None] | None = None,
                 on_status: Callable[[str], None] | None = None):
        self.cfg = cfg
        self.on_utterance = on_utterance or (lambda u: None)
        self.on_status = on_status or (lambda m: None)
        self.dir: Path | None = None
        self._t0 = 0.0
        self.offset = 0.0  # segundos já gravados ao retomar uma reunião
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self.transcriber: Transcriber | None = None
        self.tracks: dict[str, audio.Track] = {}
        self._finals: list[Utterance] = []
        from .echo import EnvelopeLog
        self.env = EnvelopeLog()  # volume dos canais ao vivo: tira o eco do microfone na hora
        self.speaker_hint: Callable[[float, float], str | None] | None = None  # nome ao vivo (extensão do Meet)
        self._jsonl = None
        self._lock = threading.Lock()

    def now(self) -> float:
        return time.perf_counter() - self._t0 + self.offset

    def prepare(self):
        """Carrega o modelo (pode demorar); chame antes de start()."""
        self.transcriber = Transcriber(self.cfg, self._on_utt, self.on_status)
        self.transcriber.load()
        self.on_status(f"Modelo carregado: {self.transcriber.model_name}")

    def start(self, resume: Path | None = None):
        """Inicia uma reunião nova, ou retoma `resume` (continua áudio, texto e tempo da mesma pasta)."""
        if self.transcriber is None:
            self.prepare()
        if resume is not None:
            self.dir = Path(resume)
            wav = self.dir / "audio.wav"
            if wav.exists():
                import soundfile as sf
                with sf.SoundFile(str(wav)) as f:
                    self.offset = f.frames / f.samplerate
        else:
            now = datetime.now()
            self.dir = Path(self.cfg.output_dir) / now.strftime("%Y-%m-%d_%H%M")
            if self.dir.exists():  # já há uma reunião neste minuto: não reaproveita (regravaria o áudio dela)
                self.dir = Path(self.cfg.output_dir) / now.strftime("%Y-%m-%d_%H%M%S")
        self.dir.mkdir(parents=True, exist_ok=True)
        self._log_handler = logging.FileHandler(self.dir / "app.log", encoding="utf-8")
        logging.getLogger().addHandler(self._log_handler)
        self._jsonl = open(self.dir / "transcricao.jsonl", "a", encoding="utf-8")
        from .ui_helpers import add_part
        add_part(self.dir, self.offset, datetime.now().strftime("%H:%M"))

        mic_dev, loop_dev = audio.default_devices()
        if self.cfg.mic_device is not None:
            mic_dev = _dev(self.cfg.mic_device, "mics")
        if self.cfg.loopback_device is not None:
            loop_dev = _dev(self.cfg.loopback_device, "loopbacks")

        self._t0 = time.perf_counter()
        self._stop.clear()
        self.rec = audio.StereoRecorder(self.dir / "audio.wav", append=resume is not None)
        self.transcriber.start()
        for name, dev in (("mic", mic_dev), ("loop", loop_dev)):
            tr = audio.Track(name, dev, self.now)
            tr.open()
            self.tracks[name] = tr
            th = threading.Thread(target=self._pump, args=(tr,), name=f"pump-{name}", daemon=True)
            th.start()
            self._threads.append(th)
        th = threading.Thread(target=self._housekeeping, name="housekeeping", daemon=True)
        th.start()
        self._threads.append(th)
        self.on_status(f"Gravando: mic='{mic_dev['name']}' | reunião='{loop_dev['name']}'")

    def _pump(self, tr: audio.Track):
        seg = Segmenter(tr.name, self.cfg.silence_ms, self.cfg.max_segment_s)
        while not self._stop.is_set():
            item = tr.read()
            if item is None:
                continue
            t, pcm = item
            if not len(pcm):
                continue
            self.rec.add(tr.name, t, pcm)
            self.env.add(tr.name, t, pcm)
            for ev in seg.feed(pcm, t):
                self.transcriber.submit(ev)
        for ev in seg.flush():
            self.transcriber.submit(ev)

    def _housekeeping(self):
        """Flush do WAV e watchdog de dispositivo."""
        while not self._stop.wait(1.0):
            self.rec.flush(self.now() - 1.0)
            now = time.perf_counter()
            last = {n: t.last_cb for n, t in self.tracks.items()}
            for name, tr in self.tracks.items():
                others = [v for n, v in last.items() if n != name]
                if now - tr.last_cb > 5 and others and now - max(others) < 2 and name == "mic":
                    # loopback pode calar em silêncio (normal); só o mic é reaberto
                    self._reopen(tr)

    def _reopen(self, tr: audio.Track):
        log.warning("stream '%s' sem dados; reabrindo", tr.name)
        self.on_status(f"Reabrindo dispositivo '{tr.name}'...")
        try:
            tr.close()
            tr.device = audio.default_devices()[0 if tr.name == "mic" else 1]
            tr.open()
        except Exception:
            log.exception("falha ao reabrir %s", tr.name)

    def _on_utt(self, u: Utterance):
        if u.final:
            with self._lock:
                echo = u.source == "mic" and is_echo(u, [x for x in self._finals if x.source == "loop"])
                if echo:
                    return
                if u.source == "mic" and self.env.is_leak(u.t0, u.t1):  # só vazamento do alto-falante (sem fone)
                    rec = {"t0": round(u.t0, 2), "t1": round(u.t1, 2), "source": "mic", "text": u.text, "echo": True,
                           "leak": True}
                    self._jsonl.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    self._jsonl.flush()
                    return
                self._finals.append(u)
                if u.source == "loop" and self.speaker_hint is not None:
                    try:
                        u.speaker = self.speaker_hint(u.t0, u.t1)
                    except Exception:  # noqa: BLE001 - o nome ao vivo é um extra
                        u.speaker = None
                rec = {"t0": round(u.t0, 2), "t1": round(u.t1, 2), "source": u.source, "text": u.text}
                if u.speaker:
                    rec["speaker"] = u.speaker
                if u.words:
                    rec["words"] = u.words
                self._jsonl.write(json.dumps(rec, ensure_ascii=False) + "\n")
                self._jsonl.flush()
        self.on_utterance(u)

    def stop(self) -> Path:
        self._stop.set()
        end = self.now()
        for th in self._threads:
            th.join(timeout=5)
        for tr in self.tracks.values():
            tr.close()
        self.transcriber.stop(drain=True)
        self.rec.close(end)
        self._jsonl.close()
        h, self._log_handler = getattr(self, "_log_handler", None), None
        if h is not None:  # solta o app.log: com ele aberto o Windows não deixa mover a pasta para a Lixeira
            logging.getLogger().removeHandler(h)
            h.close()
        from .ui_helpers import read_names, read_parts
        md = render_markdown(read_jsonl(self.dir / "transcricao.jsonl"),
                             f"Transcrição {self.dir.name}", self.dir.name, read_parts(self.dir), read_names(self.dir))
        (self.dir / "transcricao.md").write_text(md, encoding="utf-8")
        self.on_status(f"Salvo em {self.dir}")
        return self.dir


def _dev(index: int, kind: str) -> dict:
    for d in audio.list_devices()[kind]:
        if d["index"] == index:
            return d
    raise ValueError(f"dispositivo {index} não encontrado")

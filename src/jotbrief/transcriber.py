"""Worker único de Whisper com fila prioritária por timestamp."""
from __future__ import annotations

import itertools
import logging
import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .config import Config
from .vad import SR, SpeechEvent

log = logging.getLogger(__name__)

HALLUCINATIONS = [
    r"legendas? pela comunidade", r"legenda\s+adriana\s+zanotto", r"^\W*legendas?\s+(por|pela|pelo|de|realizad[ao]|feit[ao])\b.{0,40}$", r"amara\.org", r"obrigad[oa] por assistir",
    r"продолжение следует", r"sous-titr", r"subtitles? by",
    r"inscreva-se", r"transcri[çc][ãa]o e legendas", r"tchau, tchau", r"thanks? for watching", r"thank you for watching", r"please subscribe", r"^\W*(tchau|obrigad[oa])\W*$",
]
_HALL_RE = re.compile("|".join(HALLUCINATIONS), re.IGNORECASE)


@dataclass
class Utterance:
    t0: float
    t1: float
    source: str
    text: str
    final: bool
    words: list | None = None  # [[início_s, fim_s, palavra], ...] na linha do tempo da sessão
    speaker: str | None = None  # nome visto no Meet enquanto falava (só ao vivo, canal da reunião)


AUTO_LANGS = ("pt", "en")  # o modo "Automático" escolhe entre estes (evita 'espanhol'/'russo' em trechos curtos)


def is_wrong_script(text: str, limit: float = 0.3) -> bool:
    """Texto em outro alfabeto (russo, chinês, árabe…): numa call em pt/en é alucinação/erro de idioma."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if ord(c) > 0x24F) / len(letters) > limit


def is_hallucination(text: str) -> bool:
    t = text.strip()
    if not t or _HALL_RE.search(t) or is_wrong_script(t):
        return True
    words = t.lower().split()
    return len(words) >= 6 and len(set(words)) <= 2  # repetição degenerada


def resolve_device(cfg: Config) -> tuple[str, str, str]:
    """Retorna (modelo, device, compute_type)."""
    if cfg.device in ("auto", "cuda"):
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                _preload_cuda_dlls()
                return cfg.model_gpu, "cuda", "float16"
        except Exception:
            log.exception("CUDA indisponível, usando CPU")
    return cfg.model_cpu, "cpu", "int8"


def _preload_cuda_dlls():
    """Torna as DLLs cublas/cudnn dos wheels pip visíveis ao CTranslate2."""
    import os

    from .runtime import dll_search_dirs

    for d in dll_search_dirs():  # pacotes pip (código-fonte), ao lado do executável ou a pasta baixada pelo instalador
        os.add_dll_directory(str(d))
        os.environ["PATH"] = str(d) + os.pathsep + os.environ["PATH"]


def load_whisper(name: str, device: str, compute: str, attempts: int = 4, wait: float = 2.0):
    """Abre o modelo; se o Windows/antivírus estiver segurando o arquivo (comum na 1ª leitura por um programa novo),
    espera um pouco e tenta de novo em vez de desistir."""
    import time

    from faster_whisper import WhisperModel

    for i in range(attempts):
        try:
            return WhisperModel(name, device=device, compute_type=compute)
        except Exception as e:
            if "Unable to open file" not in str(e) or i == attempts - 1:
                raise
            log.warning("arquivo do modelo indisponível (%s); nova tentativa %d/%d", e, i + 2, attempts)
            time.sleep(wait * (i + 1))


class Transcriber:
    def __init__(self, cfg: Config, on_utterance: Callable[[Utterance], None],
                 on_warning: Callable[[str], None] | None = None):
        self.cfg = cfg
        self.on_utterance = on_utterance
        self.on_warning = on_warning or (lambda m: None)
        self.q: queue.PriorityQueue = queue.PriorityQueue()
        self._seq = itertools.count()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.model = None
        self.model_name = ""
        self.rtf = 0.0
        self._last_lang = AUTO_LANGS[0]

    def load(self):
        name, device, compute = resolve_device(self.cfg)
        log.info("carregando Whisper %s (%s/%s)", name, device, compute)
        try:
            self.model = load_whisper(name, device, compute)
        except Exception as gpu_err:
            if device != "cuda":
                raise
            log.exception("falha em CUDA, caindo para CPU")
            name, device, compute = self.cfg.model_cpu, "cpu", "int8"
            try:
                self.model = load_whisper(name, device, compute)
            except Exception as cpu_err:  # mostra os DOIS motivos (antes só aparecia o da CPU)
                raise RuntimeError(f"GPU: {gpu_err} | Processador ({name}): {cpu_err}") from cpu_err
        self.model_name = f"{name} ({device})"

    def start(self):
        if self.model is None:
            self.load()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="whisper", daemon=True)
        self._thread.start()

    def submit(self, ev: SpeechEvent):
        # parciais são descartadas se há fila (finais têm prioridade)
        if ev.kind == "partial" and self.q.qsize() > 2:
            return
        self.q.put((ev.t0, next(self._seq), ev))

    def stop(self, drain: bool = True):
        if drain:
            self.q.put((float("inf"), next(self._seq), None))
        else:
            self._stop.set()
            self.q.put((float("inf"), next(self._seq), None))
        if self._thread:
            self._thread.join()

    def _run(self):
        while not self._stop.is_set():
            _, _, ev = self.q.get()
            if ev is None:
                return
            try:
                self._transcribe(ev)
            except Exception:
                log.exception("erro transcrevendo segmento")

    def _language(self, ev: SpeechEvent) -> str:
        """Idioma do trecho: o configurado, ou (Automático) o mais provável entre AUTO_LANGS.

        Trechos curtos/inseguros herdam o idioma do último trecho confiante.
        """
        if self.cfg.language != "auto":
            return self.cfg.language
        try:
            _lang, _prob, all_probs = self.model.detect_language(ev.pcm)
            probs = dict(all_probs)
            best = max(AUTO_LANGS, key=lambda k: probs.get(k, 0.0))
            share = probs.get(best, 0.0) / max(sum(probs.get(k, 0.0) for k in AUTO_LANGS), 1e-9)
            if probs.get(best, 0.0) >= 0.5 and share >= 0.6 and len(ev.pcm) >= 1.5 * SR:
                self._last_lang = best
                return best
        except Exception:  # noqa: BLE001 - detecção falhou: mantém o último idioma
            log.exception("falha ao detectar idioma")
        return self._last_lang

    def _transcribe(self, ev: SpeechEvent):
        t = time.perf_counter()
        segs, _ = self.model.transcribe(
            ev.pcm, language=self._language(ev), beam_size=1 if ev.kind == "partial" else 5,
            condition_on_previous_text=False, no_speech_threshold=0.6, log_prob_threshold=-1.0,
            vad_filter=False, word_timestamps=(ev.kind == "final"),
        )
        segs = list(segs)
        text = " ".join(s.text.strip() for s in segs).strip()
        words = [[round(ev.t0 + w.start, 2), round(ev.t0 + w.end, 2), w.word.strip()]
                 for s in segs for w in (s.words or []) if w.word.strip()] or None
        dur = len(ev.pcm) / SR
        self.rtf = 0.7 * self.rtf + 0.3 * ((time.perf_counter() - t) / dur) if self.rtf else (time.perf_counter() - t) / dur
        if self.rtf > 0.8:
            self.on_warning(f"Transcrição atrasada (RTF {self.rtf:.2f}); considere um modelo menor.")
        if is_hallucination(text):
            return
        self.on_utterance(Utterance(ev.t0, ev.t1, ev.source, text, ev.kind == "final", words))

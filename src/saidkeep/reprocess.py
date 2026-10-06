"""Reprocessar uma reunião salva: transcreve o audio.wav de novo com as configurações e filtros atuais."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import Config

CHANNELS = ((0, "mic"), (1, "loop"))  # L = microfone, R = reunião (como o app grava)
BLOCK_SECONDS = 30


def write_reprocessed(folder: Path, records: list[dict]) -> Path:
    """Guarda um backup da transcrição atual e grava a nova (jsonl + md). Nomes, assunto e partes não mudam."""
    from .session import render_markdown
    from .ui_helpers import read_names, read_parts

    folder = Path(folder)
    jsonl = folder / "transcricao.jsonl"
    bak = folder / f"transcricao.jsonl.bak-{datetime.now():%Y%m%d-%H%M%S}"
    if jsonl.exists():
        bak.write_bytes(jsonl.read_bytes())
    import json

    records = sorted(records, key=lambda r: (r["t0"], r["source"]))
    jsonl.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + ("\n" if records else ""),
                     encoding="utf-8")
    (folder / "transcricao.md").write_text(
        render_markdown(records, f"Transcrição {folder.name}", folder.name, read_parts(folder), read_names(folder)),
        encoding="utf-8")
    return bak


def mark_echoes(records: list[dict]) -> list[dict]:
    """Falas do microfone que só repetem o som da reunião (sem fone) ficam marcadas 'echo' (somem da tela)."""
    from .session import is_echo

    loops = [r for r in records if r["source"] == "loop"]
    for r in records:
        if r["source"] == "mic" and is_echo(r, loops):
            r["echo"] = True
    return records


def reprocess(folder: Path, cfg: Config | None = None, progress: Callable[[str], None] | None = None,
              identify: bool = False) -> dict:
    """Transcreve de novo os dois canais do audio.wav (VAD + Whisper). Retorna um resumo (contagens)."""
    import soundfile as sf

    from .transcriber import Transcriber
    from .vad import Segmenter

    cfg = cfg or Config.load()
    folder = Path(folder)
    wav = folder / "audio.wav"
    if not wav.exists():
        raise ValueError("Esta reunião não tem áudio para reprocessar.")
    say = progress or (lambda m: None)

    say("Carregando o modelo de transcrição…")
    records: list[dict] = []

    def on_utt(u) -> None:
        if u.final:
            rec = {"t0": round(u.t0, 2), "t1": round(u.t1, 2), "source": u.source, "text": u.text}
            if u.words:
                rec["words"] = u.words
            records.append(rec)

    tr = Transcriber(cfg, on_utt)
    tr.load()
    with sf.SoundFile(str(wav)) as f:
        if f.channels < 2:
            raise ValueError("O áudio não é estéreo (mic + reunião).")
        sr, total = f.samplerate, f.frames
        for ci, (ch, source) in enumerate(CHANNELS):
            seg = Segmenter(source, cfg.silence_ms, cfg.max_segment_s)
            f.seek(0)
            pos = 0
            while pos < total:
                block = f.read(sr * BLOCK_SECONDS, dtype="float32", always_2d=True)
                if not len(block):
                    break
                for ev in seg.feed(block[:, ch], pos / sr):
                    if ev.kind == "final":
                        tr._transcribe(ev)
                pos += len(block)
                pct = int((ci * total + pos) * 100 / (len(CHANNELS) * total))
                say(f"Reprocessando… {pct}%  ({'microfone' if source == 'mic' else 'reunião'})")
            for ev in seg.flush():
                tr._transcribe(ev)
    mark_echoes(records)
    try:
        from .echo import mark_echo_by_audio
        mark_echo_by_audio(folder, records)
    except Exception:  # noqa: BLE001
        pass
    bak = write_reprocessed(folder, records)
    result = {"falas": len(records), "backup": bak.name, "pessoas": 0}
    if identify:
        from . import speakers

        say("Identificando falantes…")
        try:
            result["pessoas"] = speakers.identify(folder, cfg, progress)
        except Exception as e:  # noqa: BLE001 - a transcrição já foi salva
            result["erro_falantes"] = str(e)
    return result

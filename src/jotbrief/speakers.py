"""Identificação de falantes do canal da reunião (local, sem token): embeddings de voz + agrupamento.

Cada fala do canal "Reunião" vira um vetor de voz (sherpa-onnx + modelo wespeaker) e as falas
de vozes parecidas recebem o mesmo rótulo: Pessoa 1, Pessoa 2… O microfone continua sendo "Eu".
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Callable

import numpy as np

SR = 16000
MODEL_NAME = "wespeaker_en_voxceleb_resnet34_LM.onnx"
MODEL_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
             + MODEL_NAME)  # (sic) o nome da release no GitHub tem esse erro de digitação
MODEL_DIR = Path(os.environ.get("APPDATA", Path.home())) / "jotbrief" / "models"
MIN_SECONDS = 1.0      # falas mais curtas não criam pessoa nova (embedding pouco confiável)
MAX_EMBED_SECONDS = 20.0


def model_path() -> Path:
    return MODEL_DIR / MODEL_NAME


def has_model() -> bool:
    return model_path().exists() and model_path().stat().st_size > 1_000_000


def ensure_model(progress: Callable[[str], None] | None = None) -> Path:
    """Baixa o modelo de voz (~25 MB) na primeira vez."""
    dst = model_path()
    if has_model():
        return dst
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".part")

    def hook(blocks, size, total):
        if progress and total > 0:
            progress(f"Baixando modelo de voz… {min(100, int(blocks * size * 100 / total))}%")

    urllib.request.urlretrieve(MODEL_URL, tmp, hook)
    tmp.replace(dst)
    return dst


SEG_ARCHIVE = "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
SEG_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/"
           + SEG_ARCHIVE)
SEG_FILE = "pyannote_segmentation_3_0.onnx"


def seg_model_path() -> Path:
    return MODEL_DIR / SEG_FILE


def has_seg_model() -> bool:
    return seg_model_path().exists() and seg_model_path().stat().st_size > 500_000


def ensure_seg_model(progress: Callable[[str], None] | None = None) -> Path:
    """Baixa o modelo de segmentação (troca de voz; ~7 MB) e extrai o model.onnx."""
    import tarfile
    import tempfile

    dst = seg_model_path()
    if has_seg_model():
        return dst
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        arc = Path(tmp) / SEG_ARCHIVE

        def hook(blocks, size, total):
            if progress and total > 0:
                progress(f"Baixando modelo de troca de voz… {min(100, int(blocks * size * 100 / total))}%")

        urllib.request.urlretrieve(SEG_URL, arc, hook)
        with tarfile.open(arc, "r:bz2") as tf:
            member = next(m for m in tf.getmembers() if m.name.endswith("model.onnx"))
            with tf.extractfile(member) as src, open(dst.with_suffix(".part"), "wb") as out:
                out.write(src.read())
    dst.with_suffix(".part").replace(dst)
    return dst


# ---------- agrupamento (puro, testável) ----------

def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def assign_speakers(embs: list[np.ndarray], durations: list[float], threshold: float = 0.5) -> list[int]:
    """Índice de pessoa (0, 1, 2…) para cada fala, em ordem de aparição.

    Online: compara com o centro de cada pessoa (cosseno); se ninguém passa de `threshold`, nasce uma
    pessoa nova, exceto para falas curtas, que vão para a mais parecida.
    """
    centers: list[np.ndarray] = []
    counts: list[int] = []
    out: list[int] = []
    for e, dur in zip(embs, durations):
        e = _unit(np.asarray(e, dtype=np.float64))
        if centers:
            sims = [float(np.dot(e, _unit(c))) for c in centers]
            best = int(np.argmax(sims))
        else:
            sims, best = [], -1
        if best >= 0 and (sims[best] >= threshold or dur < MIN_SECONDS):
            k = best
            centers[k] = centers[k] * counts[k] + e
            counts[k] += 1
            centers[k] = centers[k] / counts[k]
        else:
            centers.append(e.copy())
            counts.append(1)
            k = len(centers) - 1
        out.append(k)
    return out


def apply_speakers(records: list[dict], labels: dict[int, int]) -> list[dict]:
    """Grava 'speaker': 'Pessoa N' nas falas da reunião (índice da fala → pessoa); mic fica como está."""
    for i, r in enumerate(records):
        if r.get("source") == "loop" and i in labels:
            r["speaker"] = f"Pessoa {labels[i] + 1}"
        elif r.get("source") == "loop":
            r.pop("speaker", None)
    return records


# ---------- extração e orquestração ----------

def _preload_ort() -> None:
    """Windows: o sherpa-onnx pega um onnxruntime.dll antigo do System32 (1.17) e quebra. Carregamos antes,
    pelo caminho completo, a DLL nova que acompanha o pacote onnxruntime do projeto."""
    import ctypes
    import importlib.util

    if os.name != "nt":
        return
    spec = importlib.util.find_spec("onnxruntime")
    if not spec or not spec.origin:
        return
    capi = Path(spec.origin).parent / "capi"
    dll = capi / "onnxruntime.dll"
    if dll.exists():
        os.add_dll_directory(str(capi))
        ctypes.WinDLL(str(dll))


def _extractor():
    _preload_ort()
    import sherpa_onnx

    cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(model_path()), num_threads=2, debug=False,
                                                      provider="cpu")
    if not cfg.validate():
        raise RuntimeError("Modelo de voz inválido ou corrompido")
    return sherpa_onnx.SpeakerEmbeddingExtractor(cfg)


def speaker_at(segments: list[tuple[float, float, int]], t: float, max_gap: float = 0.6) -> int | None:
    """Pessoa (id da diarização) falando em `t`: o segmento mais longo que cobre `t`; senão o mais próximo
    (até `max_gap` s); senão None."""
    cover = [sg for sg in segments if sg[0] <= t <= sg[1]]
    if cover:
        return max(cover, key=lambda sg: sg[1] - sg[0])[2]
    near = min(segments, key=lambda sg: min(abs(sg[0] - t), abs(sg[1] - t)), default=None)
    if near is not None and min(abs(near[0] - t), abs(near[1] - t)) <= max_gap:
        return near[2]
    return None


def split_by_speaker(rec: dict, segments: list[tuple[float, float, int]], min_words: int = 2) -> list[tuple[dict, int | None]]:
    """Divide uma fala nos pontos em que a voz muda, usando o tempo de cada palavra.

    Retorna [(fala, id_da_pessoa)]. Trechos com menos de `min_words` palavras são incorporados ao vizinho
    (evita picotar por ruído). Se ninguém foi detectado, devolve a fala inteira com id None.
    """
    from .ui_helpers import word_timings

    tm = word_timings(rec)
    if not tm or not segments:
        return [(rec, speaker_at(segments, (rec["t0"] + rec["t1"]) / 2) if segments else None)]
    ids: list[int | None] = []
    for a, b, _w in tm:
        ids.append(speaker_at(segments, (a + b) / 2))
    # quem não foi detectado herda o vizinho (primeiro: o próximo detectado)
    last = next((i for i in ids if i is not None), None)
    for k, i in enumerate(ids):
        if i is None:
            ids[k] = last
        else:
            last = i
    groups: list[list[int]] = []  # índices de palavras, agrupados por pessoa consecutiva
    for k, i in enumerate(ids):
        if groups and ids[groups[-1][-1]] == i:
            groups[-1].append(k)
        else:
            groups.append([k])
    merged = True
    while merged and len(groups) > 1:  # absorve trechos curtos no vizinho maior
        merged = False
        for gi, g in enumerate(groups):
            if len(g) < min_words and (tm[g[-1]][1] - tm[g[0]][0]) < 0.8:  # 1 palavra curta = ruído; longa, interjeição
                nb = gi - 1 if gi > 0 and (gi + 1 >= len(groups) or len(groups[gi - 1]) >= len(groups[gi + 1])) else gi + 1
                groups[nb] += g
                groups[nb].sort()
                del groups[gi]
                merged = True
                break
        # junta vizinhos que ficaram com a mesma pessoa
        i = 0
        while i + 1 < len(groups):
            if ids[groups[i][0]] == ids[groups[i + 1][0]]:
                groups[i] += groups.pop(i + 1)
            else:
                i += 1
    out = []
    for g in groups:
        ws = [tm[k] for k in g]
        piece = dict(rec)
        piece["t0"], piece["t1"] = round(ws[0][0], 2), round(ws[-1][1], 2)
        piece["text"] = " ".join(w for _a, _b, w in ws)
        piece["words"] = [[round(a, 2), round(b, 2), w] for a, b, w in ws]
        out.append((piece, ids[g[0]]))
    return out


def merge_small_speakers(segments: list[tuple[float, float, int]], min_seconds: float = 1.5,
                         min_share: float = 0.08) -> list[tuple[float, float, int]]:
    """Funde 'pessoas' com quase nenhuma fala (ruído, eco, estalos) na pessoa mais próxima no tempo.

    Uma voz só conta se falou pelo menos `min_seconds` e `min_share` do total de fala do canal.
    """
    if not segments:
        return []
    total: dict[int, float] = {}
    for a, b, sid in segments:
        total[sid] = total.get(sid, 0.0) + (b - a)
    limit = max(min_seconds, min_share * sum(total.values()))
    keep = {sid for sid, t in total.items() if t >= limit} or {max(total, key=total.get)}
    if len(keep) == len(total):
        return list(segments)
    anchors = [sg for sg in segments if sg[2] in keep]

    def gap(x, y) -> float:  # distância no tempo entre dois intervalos (0 se sobrepõem)
        return max(0.0, max(x[0], y[0]) - min(x[1], y[1]))

    out = []
    for sg in segments:
        if sg[2] in keep:
            out.append(sg)
        else:
            near = min(anchors, key=lambda an: gap(sg, an))
            out.append((sg[0], sg[1], near[2]))
    return out


def diarize_channel(right: np.ndarray, sr: int, threshold: float, num_speakers: int = 0) -> list[tuple[float, float, int]]:
    """Diarização (segmentação + agrupamento) do canal da reunião → [(início, fim, id)]."""
    _preload_ort()
    import sherpa_onnx

    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(seg_model_path())),
            num_threads=2),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(model_path()), num_threads=2),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=num_speakers if num_speakers > 0 else -1,
                                                    threshold=threshold),
        min_duration_on=0.3, min_duration_off=0.3)
    if not cfg.validate():
        raise RuntimeError("Modelos de voz inválidos ou corrompidos")
    sd = sherpa_onnx.OfflineSpeakerDiarization(cfg)
    if sd.sample_rate != sr:
        raise RuntimeError(f"Taxa de amostragem inesperada: {sd.sample_rate} != {sr}")
    res = sd.process(np.ascontiguousarray(right, dtype=np.float32)).sort_by_start_time()
    return [(float(r.start), float(r.end), int(r.speaker)) for r in res]


def identify(folder: Path, cfg=None, progress: Callable[[str], None] | None = None) -> int:
    """Rotula as falas do canal da reunião (Pessoa 1, 2…) e reescreve transcricao.jsonl/.md; retorna nº de pessoas.

    Com o modelo de troca de voz, divide também as falas em que duas pessoas falam; sem ele, rotula por fala.
    """
    import soundfile as sf

    from .config import Config
    from .session import is_echo, read_jsonl, render_markdown

    cfg = cfg or Config.load()
    folder = Path(folder)
    ensure_model(progress)
    jsonl = folder / "transcricao.jsonl"
    records = read_jsonl(jsonl)
    loops = [r for r in records if r["source"] == "loop"]
    if not loops:
        return 0
    use_seg = True
    try:
        ensure_seg_model(progress)
    except Exception:  # noqa: BLE001 - sem o modelo de segmentação: cai para rótulo por fala
        use_seg = False

    if use_seg:
        if progress:
            progress("Separando as vozes da reunião…")
        with sf.SoundFile(str(folder / "audio.wav")) as f:
            sr = f.samplerate
            data = f.read(dtype="float32", always_2d=True)
        if data.shape[1] < 2:
            return 0
        segs = diarize_channel(data[:, 1], sr, cfg.diarization_threshold, cfg.num_speakers)
        if cfg.num_speakers <= 0:  # automático: descarta 'pessoas' fantasma; se você informou o número, respeita
            segs = merge_small_speakers(segs)
        # ids pela ordem em que aparecem na reunião
        order: dict[int, int] = {}
        for _a, _b, sid in sorted(segs):
            order.setdefault(sid, len(order))
        new_records: list[dict] = []
        for r in records:
            if r["source"] == "mic":
                if is_echo(r, loops):
                    r["echo"] = True  # o microfone só captou o som da reunião; some da tela, sem apagar
                new_records.append(r)
                continue
            for piece, sid in split_by_speaker(r, segs):
                if sid is not None:
                    piece["speaker"] = f"Pessoa {order[sid] + 1}"
                else:
                    piece.pop("speaker", None)
                new_records.append(piece)
        records = sorted(new_records, key=lambda r: r["t0"])
        n_people = len({r.get("speaker") for r in records if r.get("speaker")})
        _recognize_known_voices(folder, data[:, 1], sr, segs, order, cfg, progress)
    else:
        n_people = _identify_by_utterance(folder, records, cfg.speaker_threshold, progress)

    try:  # mic que só captou o alto-falante (sem fone): detectado pelo áudio, some da tela sem apagar
        from .echo import mark_echo_by_audio
        mark_echo_by_audio(folder, records)
    except Exception:  # noqa: BLE001
        pass
    bak = jsonl.with_suffix(".jsonl.bak")
    if not bak.exists():
        bak.write_bytes(jsonl.read_bytes())
    jsonl.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    try:  # nomes vistos no Meet pela extensão do Chrome (se houve): valem mais que o reconhecimento por voz
        from .meet_names import apply_meet_names
        got = apply_meet_names(folder)
        if got and progress:
            progress("Nomes do Meet aplicados: " + ", ".join(f"{k} → {v}" for k, v in got.items()))
    except Exception:  # noqa: BLE001 - a identificação por voz já está salva
        pass
    from .ui_helpers import read_names, read_parts

    (folder / "transcricao.md").write_text(
        render_markdown(records, f"Transcrição {folder.name}", folder.name, read_parts(folder), read_names(folder)),
        encoding="utf-8")
    return n_people


def _recognize_known_voices(folder: Path, right, sr: int, segs, order: dict[int, int], cfg,
                            progress: Callable[[str], None] | None = None) -> dict[str, str]:
    """Dá o nome de quem você já nomeou em outras reuniões, comparando a voz de cada 'Pessoa N'."""
    from . import voices
    from .ui_helpers import apply_auto_names

    known = voices.load_voices()
    found: dict[str, str] = {}
    if known:
        if progress:
            progress("Reconhecendo vozes já conhecidas…")
        embs = {}
        for sid in order:
            got = voices.embed_windows(right, sr, [(a, b) for a, b, s in segs if s == sid])
            if got:
                embs[sid] = got[0]
        for sid, (name, _sim) in voices.assign_names(embs, known, cfg.voice_match_threshold,
                                                     cfg.voice_match_margin).items():
            found[f"Pessoa {order[sid] + 1}"] = name
    apply_auto_names(folder, found)  # também limpa nomes automáticos antigos quando nada é reconhecido
    return found


def _identify_by_utterance(folder: Path, records: list[dict], threshold: float,
                           progress: Callable[[str], None] | None = None) -> int:
    """Plano B (sem o modelo de troca de voz): um vetor de voz por fala + agrupamento."""
    import soundfile as sf

    loop_idx = [i for i, r in enumerate(records) if r["source"] == "loop"]
    if not loop_idx:
        return 0
    ex = _extractor()
    embs, durs, idxs = [], [], []
    with sf.SoundFile(str(folder / "audio.wav")) as f:
        sr = f.samplerate
        for n, i in enumerate(loop_idx):
            if progress:
                progress(f"Identificando vozes… {n + 1}/{len(loop_idx)}")
            r = records[i]
            start = max(int(r["t0"] * sr), 0)
            frames = min(int((r["t1"] - r["t0"]) * sr), int(MAX_EMBED_SECONDS * sr))
            if frames < int(0.4 * sr):
                continue  # curto demais: fica sem pessoa (herda a anterior abaixo)
            f.seek(start)
            audio = f.read(frames, dtype="float32", always_2d=True)
            if audio.shape[1] < 2 or len(audio) < int(0.4 * sr):
                continue
            wav = np.ascontiguousarray(audio[:, 1])  # canal direito = reunião
            if float(np.abs(wav).max()) < 1e-4:
                continue
            s = ex.create_stream()
            s.accept_waveform(sample_rate=sr, waveform=wav)
            s.input_finished()
            embs.append(np.array(ex.compute(s), dtype=np.float64))
            durs.append(r["t1"] - r["t0"])
            idxs.append(i)
    if not embs:
        return 0
    ks = assign_speakers(embs, durs, threshold)
    labels = dict(zip(idxs, ks))
    last = None  # falas sem embedding herdam a pessoa da fala anterior
    for i in loop_idx:
        if i in labels:
            last = labels[i]
        elif last is not None:
            labels[i] = last
    apply_speakers(records, labels)
    return len(set(labels.values()))

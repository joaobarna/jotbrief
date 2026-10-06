from saidkeep.session import clean_records, fmt_time, is_echo, render_markdown
from saidkeep.transcriber import is_hallucination


def rec(t0, t1, src, text):
    return {"t0": t0, "t1": t1, "source": src, "text": text}


def test_echo_removed():
    recs = [rec(1, 4, "loop", "vamos fechar o orçamento amanhã"),
            rec(1.1, 4.1, "mic", "vamos fechar o orçamento amanha"),
            rec(5, 6, "mic", "combinado")]
    out = clean_records(recs)
    assert [r["text"] for r in out] == ["vamos fechar o orçamento amanhã", "combinado"]


def test_no_echo_when_text_differs():
    assert not is_echo(rec(1, 3, "mic", "concordo totalmente"), [rec(1, 3, "loop", "qual o prazo?")])


def test_markdown_sorted_and_labeled():
    md = render_markdown([rec(65, 67, "loop", "b"), rec(2, 3, "mic", "a")])
    assert md.index("Eu") < md.index("Reunião")
    assert "00:01:05 | Reunião | b" in md and "00:00:02 | Eu | a" in md


def test_fmt_time():
    assert fmt_time(3725) == "01:02:05"


def test_hallucinations():
    assert is_hallucination("Legendas pela comunidade Amara.org")
    assert is_hallucination("")
    assert is_hallucination("sim sim sim sim sim sim sim")
    assert not is_hallucination("Vamos revisar o contrato hoje")


def test_wall_clock_and_transcript_lines():
    from datetime import datetime

    from saidkeep.session import render_transcript, transcript_meta, wall_clock
    recs = [{"t0": 2.0, "t1": 5.0, "source": "loop", "speaker": "Pessoa 1", "text": "Conta,\nCarlos."},
            {"t0": 19.4, "t1": 22.4, "source": "mic", "text": "Legal."}]
    assert wall_clock("2026-09-29_1552", None, 8.0) == datetime(2026, 9, 29, 15, 52, 8)
    out = render_transcript(recs, "2026-09-29_1552", None)
    assert out.splitlines() == ["2026-09-29 15:52:02 | Pessoa 1 | Conta, Carlos.",
                                "2026-09-29 15:52:19 | Eu | Legal."]
    assert transcript_meta(recs) == "Duração: 00:00:22 | Participantes: Pessoa 1, Eu"


def test_wall_clock_with_resumed_parts_and_midnight():
    from datetime import datetime

    from saidkeep.session import wall_clock
    parts = [{"start": 0.0, "at": "23:50"}, {"start": 600.0, "at": "00:05"}]   # retomou após a meia-noite
    assert wall_clock("2026-09-29_2350", parts, 30.0) == datetime(2026, 9, 29, 23, 50, 30)
    assert wall_clock("2026-09-29_2350", parts, 630.0) == datetime(2026, 9, 30, 0, 5, 30)


def test_hallucinations_wrong_script_and_known_phrases():
    assert is_hallucination("Legenda Adriana Zanotto")
    assert is_hallucination("Legenda por Sônia Ruberti")          # variante com outro nome
    assert is_hallucination("Legendas pela comunidade Amara.org")
    assert not is_hallucination("A legenda da figura está errada, vamos corrigir isso hoje.")
    assert is_hallucination("Продолжение следует...")
    assert is_hallucination("То есть кутаем.")                 # alfabeto cirílico numa call em pt/en
    assert not is_hallucination("Tô trocando seis telhas.")
    assert not is_hallucination("Vamos revisar o contrato 12.")


def test_clean_records_drops_old_garbage_but_keeps_real_speech():
    recs = [rec(1, 2, "loop", "Vou trocando seis telhas."), rec(3, 4, "mic", "Продолжение следует..."),
            rec(150, 152, "loop", "Legenda Adriana Zanotto")]
    assert [r["text"] for r in clean_records(recs)] == ["Vou trocando seis telhas."]




def test_echo_when_mic_text_spans_several_loop_segments():
    # o Whisper corta a frase em lugares diferentes nos dois canais: o mic é a soma de vários trechos da reunião
    loops = [{"t0": 29.55, "t1": 43.47, "source": "loop", "text": "Ainda temos a atualização dos modelos da 4.966 e tenho a referência a essa atualização "
              "que temos que fazer todos os anos. Acho que o grande miss nas previsões do mercado aqui para o resultado "
              "de vocês não foi na provisão, porque já tinha uma certa"},
             {"t0": 43.47, "t1": 44.47, "source": "loop", "text": "preocupação com o trimestre."}]
    mic = {"t0": 29.66, "t1": 44.67, "source": "mic", "text": "Ainda temos atualização dos modelos a 4, 9,5 mil. Tenho a referência a essa "
           "atualização que temos que fazer todos os anos. Acho que o grande miss das previsões do mercado que prestaram "
           "de vocês não foi a provisão, que já tinha uma certa preocupação."}
    assert is_echo(mic, loops)
    assert not is_echo({"t0": 30.0, "t1": 33.0, "source": "mic", "text": "Beleza, vou anotar isso aqui agora"}, loops)


def test_echo_by_audio_marks_leaked_mic_but_keeps_real_speech(tmp_path):
    import numpy as np
    import soundfile as sf

    from saidkeep.echo import mark_echo_by_audio

    sr = 16000
    t = np.arange(sr * 12) / sr
    rng = np.random.default_rng(0)
    speech_env = (np.sin(2 * np.pi * 0.7 * t) > 0).astype(float) * 0.5 + 0.1  # "sílabas" da reunião
    loop = (rng.standard_normal(len(t)) * speech_env * 0.1).astype("float32")
    mic = np.zeros_like(loop)
    mic[: sr * 6] = loop[: sr * 6] * 0.01                  # 0–6 s: só vazamento do alto-falante
    own_env = (np.sin(2 * np.pi * 1.9 * t + 1) > 0).astype(float) * 0.5 + 0.1
    mic[sr * 6:] = (rng.standard_normal(len(t)) * own_env * 0.05).astype("float32")[sr * 6:]  # 6–12 s: você falando
    sf.write(str(tmp_path / "audio.wav"), np.stack([mic, loop], 1), sr)
    recs = [{"t0": 0.5, "t1": 5.5, "source": "mic", "text": "a"}, {"t0": 6.5, "t1": 11.5, "source": "mic", "text": "b"}]
    assert mark_echo_by_audio(tmp_path, recs) == 1
    assert recs[0].get("echo") and not recs[1].get("echo")


def test_live_envelope_log_flags_leak_and_keeps_own_voice():
    import numpy as np

    from saidkeep.echo import EnvelopeLog

    sr = 16000
    rng = np.random.default_rng(1)
    t = np.arange(sr * 12) / sr
    env_a = (np.sin(2 * np.pi * 0.7 * t) > 0) * 0.5 + 0.1
    env_b = (np.sin(2 * np.pi * 1.9 * t + 1) > 0) * 0.5 + 0.1
    loop = (rng.standard_normal(len(t)) * env_a * 0.1).astype("float32")
    mic = np.concatenate([loop[: sr * 6] * 0.01, (rng.standard_normal(sr * 6) * env_b[sr * 6:] * 0.05).astype("float32")])
    log = EnvelopeLog()
    for i in range(0, len(t), sr // 10):
        log.add("mic", i / sr, mic[i:i + sr // 10])
        log.add("loop", i / sr, loop[i:i + sr // 10])
    assert log.is_leak(0.5, 5.5) and not log.is_leak(6.5, 11.5)


def test_chat_usage_cost_and_format():
    from saidkeep.chat import fmt_usage, sum_usage, usage_cost

    u = {"in": 10_000, "out": 1_000, "read": 90_000, "write": 0}
    assert round(usage_cost("claude-sonnet-5-5", u), 4) == round(0.02 + 0.01 + 0.018, 4)   # 2/10/0,20 por milhão
    assert usage_cost("modelo-desconhecido", u) is None
    assert sum_usage([{"usage": u}, {"usage": u}, {"role": "user"}])["read"] == 180_000
    txt = fmt_usage("claude-sonnet-5-5", u, "Última resposta")
    assert "100,0 mil entrada (90,0 mil do cache)" in txt and "1,0 mil saída" in txt and "US$ 0,048" in txt


def test_effort_support_and_total_cost_per_model():
    from saidkeep.chat import total_cost
    from saidkeep.config import supports_effort

    assert supports_effort("claude-sonnet-5-5") and supports_effort("claude-opus-5-5")
    assert not supports_effort("claude-haiku-4-5")
    a = {"role": "assistant", "usage": {"in": 1_000_000, "out": 0, "read": 0, "write": 0, "model": "claude-sonnet-5-5"}}
    b = {"role": "assistant", "usage": {"in": 1_000_000, "out": 0, "read": 0, "write": 0, "model": "claude-opus-5-5"}}
    assert total_cost([a, b]) == 2.0 + 4.0                                  # cada resposta com o preço do seu modelo
    assert total_cost([a, {"role": "assistant", "usage": {"in": 5, "model": "x"}}]) is None


def test_release_logs_lets_windows_delete_the_folder(tmp_path):
    import logging
    import shutil

    from saidkeep.session import release_logs

    folder = tmp_path / "2026-10-02_1107"
    folder.mkdir()
    h = logging.FileHandler(folder / "app.log", encoding="utf-8")
    logging.getLogger().addHandler(h)
    try:
        assert release_logs(folder) == 1 and h not in logging.getLogger().handlers
        shutil.rmtree(folder)                       # com o log aberto isto falharia no Windows (arquivo em uso)
        assert not folder.exists()
    finally:
        logging.getLogger().removeHandler(h)
        h.close()


def test_leak_rule_never_hides_your_own_loud_voice():
    from saidkeep.echo import is_leak_score

    assert is_leak_score(0.89, 0.0017, 0.06)          # vazamento medido: mic baixíssimo
    assert not is_leak_score(0.73, 0.0408, 0.034)     # sua voz por cima da reunião, mesmo com envelope parecido
    assert not is_leak_score(0.18, 0.0129, 0.077)     # fala real medida antes
    assert not is_leak_score(0.9, 0.0005, 0.002)      # reunião calada: nada a vazar


def test_overlapped_second_speaker_is_recovered_only_when_meet_confirms_overlap(tmp_path):
    import json

    from saidkeep import meet_names
    from saidkeep.echo import recover_overlapped

    folder = tmp_path / "2026-10-02_1114"
    folder.mkdir()
    for t, name, on in [(0, "Carlos", True), (26.7, "Dora", True), (32.0, "Dora", False), (60, "Carlos", False)]:
        meet_names.append_event(folder, t, name, on)
    loop = {"t0": 20.0, "t1": 35.0, "source": "loop", "speaker": "Pessoa 1", "text": "falando sobre traumas e sobre o trabalho"}
    dora = {"t0": 27.0, "t1": 31.0, "source": "mic", "echo": True, "leak": True, "text": "oi vocês estão me escutando aí"}
    junk = {"t0": 40.0, "t1": 43.0, "source": "mic", "echo": True, "leak": True, "text": "puxa a luz pra eu chegar"}
    records = [loop, dora, junk]
    assert recover_overlapped(folder, records, [dora, junk]) == 1
    assert dora["source"] == "loop" and dora["speaker"] == "Dora" and dora["recovered"] and not dora["echo"]
    assert junk["echo"] and junk["source"] == "mic"            # sem 2ª pessoa falando junto: continua escondido
    assert [r["t0"] for r in records] == sorted(r["t0"] for r in records)
    (tmp_path / "x").mkdir()
    assert recover_overlapped(tmp_path / "x", [loop, dora], [dora]) == 0     # sem extensão: não recupera nada


def test_meet_event_file_survives_concurrent_writes(tmp_path):
    import json
    import threading

    from saidkeep import meet_names

    folder = tmp_path / "r"
    folder.mkdir()
    ts = [threading.Thread(target=lambda i=i: [meet_names.append_event(folder, k, f"Pessoa {i}", True) for k in range(200)])
          for i in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    lines = (folder / meet_names.FILE).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1200 and all(json.loads(l)["name"].startswith("Pessoa") for l in lines)   # nenhuma linha quebrada


def test_load_whisper_retries_when_file_is_temporarily_locked(monkeypatch):
    import faster_whisper

    from saidkeep import transcriber

    calls = []

    class FakeModel:
        def __init__(self, name, device, compute_type):
            calls.append(name)
            if len(calls) < 3:
                raise RuntimeError("Unable to open file 'model.bin' in model 'x'")

    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeModel)
    assert isinstance(transcriber.load_whisper("small", "cpu", "int8", attempts=4, wait=0), FakeModel)
    assert len(calls) == 3                                           # 2 falhas por arquivo preso, 3ª funciona
    calls.clear()
    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda *a, **k: (_ for _ in ()).throw(ValueError("outro erro")))
    import pytest
    with pytest.raises(ValueError):
        transcriber.load_whisper("small", "cpu", "int8", attempts=4, wait=0)   # outros erros não ficam repetindo


def test_gpu_and_cpu_failures_are_both_reported(monkeypatch):
    from saidkeep import transcriber
    from saidkeep.config import Config

    monkeypatch.setattr(transcriber, "resolve_device", lambda cfg: ("large-v3-turbo", "cuda", "float16"))

    def fail(name, device, compute, **k):
        raise RuntimeError(f"erro {device}")

    monkeypatch.setattr(transcriber, "load_whisper", fail)
    import pytest
    with pytest.raises(RuntimeError, match=r"GPU: erro cuda \| Processador \(small\): erro cpu"):
        transcriber.Transcriber(Config(), lambda u: None).load()


def test_logs_setup_writes_file_and_records_thread_exceptions(tmp_path):
    import logging
    import sys
    import threading

    from saidkeep import logs

    saved = (sys.excepthook, threading.excepthook, list(logging.getLogger().handlers))
    try:
        logs._installed = False
        p = logs.setup(tmp_path / "x.log")
        t = threading.Thread(target=lambda: 1 / 0, name="teste")
        t.start()
        t.join()
        for h in logging.getLogger().handlers:
            h.flush()
        txt = (tmp_path / "x.log").read_text(encoding="utf-8")
        assert p == tmp_path / "x.log" and "início" in txt and "exceção em thread teste" in txt and "ZeroDivisionError" in txt
    finally:
        sys.excepthook, threading.excepthook = saved[0], saved[1]
        for h in list(logging.getLogger().handlers):
            if h not in saved[2]:
                logging.getLogger().removeHandler(h)
                h.close()
        logs._installed = False

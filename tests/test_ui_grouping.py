from datetime import date
from pathlib import Path

from saidkeep.ui_helpers import call_title, clean_subject, group_by_day, pretty_name


def test_grouping_one_group_per_day():
    fs = [Path(n) for n in ("2026-09-29_1010", "2026-09-28_0900", "2026-09-25_1500",
                            "2026-08-01_1200", "2026-09-29_0800", "lixo")]
    out = group_by_day(fs, date(2026, 9, 29))
    labels = [k for k, _ in out]
    assert labels == ["Hoje · 2026-09-29", "Ontem · 2026-09-28", "Sexta · 2026-09-25", "Sábado · 2026-08-01", "Outras"]
    assert [p.name for p in out[0][1]] == ["2026-09-29_1010", "2026-09-29_0800"]
    assert [p.name for p in out[-1][1]] == ["lixo"]


def test_pretty_name():
    assert pretty_name("2026-09-29_1010") == "29/09 às 10:10"


def test_call_title_format():
    assert call_title("2026-09-29_1513", "Revisão do orçamento | 3º tri.") == \
        "2026-09-29 | 15:13 | Revisão do orçamento - 3º tri"
    assert clean_subject("  ") == "Sem assunto"


def test_playable_wav_mono_mix(tmp_path):
    import numpy as np
    import soundfile as sf

    from saidkeep.ui_helpers import playable_wav
    folder = tmp_path / "2026-09-29_1000"
    folder.mkdir()
    sr = 16000
    st = np.zeros((sr, 2), np.float32)
    st[:, 0], st[:, 1] = 0.2, 0.1
    sf.write(str(folder / "audio.wav"), st, sr)
    out = playable_wav(folder, tmp_path / "cache")
    info = sf.info(str(out))
    assert info.channels == 1 and info.frames == sr
    data, _ = sf.read(str(out))
    assert abs(np.abs(data).max() - 0.9) < 0.01   # normalizado para ~0,9
    assert playable_wav(tmp_path / "vazio", tmp_path / "cache") is None


def test_parts_and_items(tmp_path):
    from saidkeep.ui_helpers import add_part, build_items, read_parts, read_subject, write_subject
    f = tmp_path / "2026-09-29_1542"
    f.mkdir()
    write_subject(f, "Teste")
    assert add_part(f, 15.2, "15:50") == [{"start": 0.0, "at": "15:42"}, {"start": 15.2, "at": "15:50"}]  # retroativa
    assert read_subject(f) == "Teste" and len(read_parts(f)) == 2                                          # meta preservada
    recs = [{"t0": 1.0, "t1": 2, "source": "mic", "text": "a"},
            {"t0": 16.0, "t1": 18, "source": "loop", "text": "b"}]
    items = build_items(recs, read_parts(f), 30.0)
    kinds = [i[0] for i in items]
    assert kinds == ["sep", "utt", "sep", "utt"]
    assert items[0][2] == "Parte 1 · 15:42" and items[0][4] == 15.2 and items[2][2] == "Parte 2 · 15:50"
    assert items[1][1]["text"] == "a" and items[3][1]["text"] == "b"
    # uma parte só: sem separador
    assert [i[0] for i in build_items(recs, [{"start": 0.0, "at": "15:42"}], 30.0)] == ["utt", "utt"]


def test_word_timings_real_and_estimated():
    from saidkeep.ui_helpers import active_word, word_timings
    real = {"t0": 1.0, "t1": 3.0, "text": "oi tudo bem", "words": [[1.0, 1.4, "oi"], [1.5, 2.0, "tudo"], [2.1, 2.9, "bem"]]}
    tm = word_timings(real)
    assert [w for *_, w in tm] == ["oi", "tudo", "bem"]
    assert active_word(tm, 0.5) == -1 and active_word(tm, 1.2) == 0 and active_word(tm, 2.5) == 2
    est = word_timings({"t0": 0.0, "t1": 4.0, "text": "aa bbbbbbb"})
    assert abs(est[0][0]) < 1e-9 and abs(est[-1][1] - 4.0) < 1e-6 and est[0][1] == est[1][0]
    assert word_timings({"t0": 0, "t1": 1, "text": ""}) == []


def test_duplicate_parts_are_merged(tmp_path):
    from saidkeep.ui_helpers import add_part, read_parts, write_meta
    write_meta(tmp_path, parts=[{"start": 0.0, "at": "16:52"}, {"start": 0.0, "at": "16:52"}, {"start": 29.06, "at": "16:53"}])
    assert read_parts(tmp_path) == [{"start": 0.0, "at": "16:52"}, {"start": 29.06, "at": "16:53"}]
    add_part(tmp_path, 29.2, "16:54")                       # reiniciou em seguida: substitui em vez de duplicar
    assert [p["at"] for p in read_parts(tmp_path)] == ["16:52", "16:54"]

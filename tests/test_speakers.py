import numpy as np

from jotbrief.speakers import apply_speakers, assign_speakers


def _v(*x):
    return np.array(x, dtype=float)


def test_two_voices_and_short_utterance():
    a1, a2 = _v(1, 0.1, 0), _v(0.9, 0.0, 0.1)      # voz A
    b1 = _v(0, 1, 0.1)                               # voz B
    short_noise = _v(0.3, 0.3, 0.9)                  # curta e diferente de todos
    ks = assign_speakers([a1, b1, a2, short_noise, b1], [3.0, 2.5, 2.0, 0.5, 2.0])
    assert ks[0] == ks[2] and ks[1] == ks[4] and ks[0] != ks[1]
    assert ks[3] in (ks[0], ks[1])                   # fala curta não cria pessoa nova
    assert max(ks) == 1


def test_long_different_utterance_creates_new_person():
    ks = assign_speakers([_v(1, 0, 0), _v(0, 1, 0), _v(0, 0, 1)], [3, 3, 3])
    assert ks == [0, 1, 2]


def test_apply_speakers_only_loop():
    recs = [{"source": "mic", "text": "a"}, {"source": "loop", "text": "b"}, {"source": "loop", "text": "c"}]
    out = apply_speakers(recs, {1: 0, 2: 1})
    assert "speaker" not in out[0] and out[1]["speaker"] == "Pessoa 1" and out[2]["speaker"] == "Pessoa 2"

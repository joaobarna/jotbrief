from jotbrief.speakers import speaker_at, split_by_speaker

SEGS = [(0.0, 3.0, 0), (3.2, 6.0, 1)]


def test_speaker_at_cover_nearest_and_none():
    assert speaker_at(SEGS, 1.0) == 0 and speaker_at(SEGS, 4.0) == 1
    assert speaker_at(SEGS, 3.1) in (0, 1)          # vão entre segmentos: pega o mais próximo
    assert speaker_at(SEGS, 20.0) is None


def test_split_inside_one_utterance_with_real_word_times():
    rec = {"t0": 0.5, "t1": 5.5, "source": "loop", "text": "não acredito sozinho nossa então",
           "words": [[0.5, 1.0, "não"], [1.1, 1.8, "acredito"], [1.9, 2.8, "sozinho"],
                     [3.3, 3.8, "nossa"], [4.0, 5.5, "então"]]}
    out = split_by_speaker(rec, SEGS)
    assert [(p["text"], sid) for p, sid in out] == [("não acredito sozinho", 0), ("nossa então", 1)]
    assert out[0][0]["t0"] == 0.5 and out[1][0]["t1"] == 5.5
    assert all(p["source"] == "loop" for p, _ in out)


def test_short_flip_is_absorbed_and_no_segments_keeps_record():
    rec = {"t0": 0.0, "t1": 2.0, "source": "loop", "text": "a b c d",
           "words": [[0.0, 0.4, "a"], [0.5, 0.9, "b"], [3.3, 3.5, "c"], [0.9, 1.9, "d"]]}
    segs = [(0.0, 3.0, 0), (3.2, 3.6, 1)]
    out = split_by_speaker(rec, segs, min_words=2)
    assert len(out) == 1 and out[0][1] == 0                 # "c" sozinho (1 palavra) vira parte da pessoa 0
    assert split_by_speaker(rec, [])[0][0] is rec           # sem segmentos: devolve a fala intacta


def test_merge_small_speakers_removes_ghost_voices():
    from jotbrief.speakers import merge_small_speakers
    segs = [(0.0, 10.0, 0), (12.0, 14.0, 1), (15.0, 16.0, 7),   # pessoa 7: só 1 s de fala (ruído)
            (20.0, 32.0, 0), (33.0, 40.0, 1)]
    out = merge_small_speakers(segs)
    assert sorted({s for *_, s in out}) == [0, 1]
    assert (15.0, 16.0, 1) in out          # o fantasma vai para a voz mais próxima no tempo (pessoa 1, aos 12–14 s)
    assert merge_small_speakers([]) == []
    only = merge_small_speakers([(0.0, 0.5, 3), (1.0, 1.4, 4)])   # ninguém passa do mínimo: fica a maior
    assert len({s for *_, s in only}) == 1


def test_short_meeting_keeps_real_speakers():
    from jotbrief.speakers import merge_small_speakers
    segs = [(1.97, 5.25, 0), (7.47, 8.65, 1), (9.04, 11.61, 0), (11.73, 13.53, 1)]   # a call curta de 27 s
    assert {s for *_, s in merge_small_speakers(segs)} == {0, 1}

import numpy as np

from jotbrief import voices
from jotbrief.ui_helpers import (apply_auto_names, mark_manual, read_auto_names, read_names, write_names)


def v(*x):
    return np.array(x, dtype=float)


ANA, BIA = v(1, 0.1, 0, 0), v(0, 1, 0.1, 0)


def test_add_sample_weighted_mean_and_forget(tmp_path):
    p = tmp_path / "voices.json"
    voices.add_sample("Ana", ANA, 10.0, p)
    voices.add_sample("Ana", v(0.9, 0.2, 0, 0), 30.0, p)
    got = voices.load_voices(p)["Ana"]
    assert got["seconds"] == 40.0 and abs(np.linalg.norm(got["emb"]) - 1.0) < 1e-3
    assert voices.forget_voice("ana", p) and voices.load_voices(p) == {}


def test_match_threshold_and_margin(tmp_path):
    p = tmp_path / "voices.json"
    voices.add_sample("Ana", ANA, 20.0, p)
    voices.add_sample("Bia", BIA, 20.0, p)
    known = voices.load_voices(p)
    assert voices.match(v(0.95, 0.15, 0, 0), known)[0] == "Ana"
    assert voices.match(v(0, 0, 1, 0), known) is None                      # ninguém parecido
    ambiguous = voices._unit(ANA) + voices._unit(BIA)                      # exatamente no meio: não chuta
    assert voices.match(ambiguous, known) is None


def test_assign_names_can_give_the_same_name_to_split_voices():
    known = {"Ana": {"emb": ANA.tolist(), "seconds": 30}}
    out = voices.assign_names({0: v(0.9, 0.1, 0, 0), 1: v(0.97, 0.1, 0, 0), 2: BIA}, known)
    assert sorted(out) == [0, 1] and {n for n, _ in out.values()} == {"Ana"}   # a mesma pessoa dividida em duas vozes
    assert 2 not in out                                                         # outra voz: fica "Pessoa N"


def test_auto_names_never_override_manual_ones(tmp_path):
    write_names(tmp_path, {"Pessoa 1": "Gestor"})                             # você digitou
    apply_auto_names(tmp_path, {"Pessoa 1": "Ana", "Pessoa 2": "Bia"})
    assert read_names(tmp_path) == {"Pessoa 1": "Gestor", "Pessoa 2": "Bia"} and read_auto_names(tmp_path) == ["Pessoa 2"]
    apply_auto_names(tmp_path, {})                                         # reidentificou e ninguém foi reconhecido
    assert read_names(tmp_path) == {"Pessoa 1": "Gestor"} and read_auto_names(tmp_path) == []
    apply_auto_names(tmp_path, {"Pessoa 2": "Bia"})
    mark_manual(tmp_path, ["Pessoa 2"])                                    # você corrigiu/confirmou
    assert read_auto_names(tmp_path) == [] and read_names(tmp_path)["Pessoa 2"] == "Bia"

from saidkeep.session import render_markdown, render_transcript, speaker_labels, transcript_meta
from saidkeep.ui_helpers import read_names, read_subject, write_names, write_subject

RECS = [{"t0": 2.0, "t1": 5.0, "source": "loop", "speaker": "Pessoa 1", "text": "Conta, Carlos."},
        {"t0": 8.0, "t1": 10.0, "source": "loop", "speaker": "Pessoa 2", "text": "Não acredito."},
        {"t0": 19.0, "t1": 20.0, "source": "mic", "text": "Legal."},
        {"t0": 25.0, "t1": 26.0, "source": "loop", "text": "Sem identificação."}]


def test_labels_in_order_of_appearance():
    assert speaker_labels(RECS) == ["Pessoa 1", "Pessoa 2", "Eu", "Reunião"]


def test_names_apply_to_export_and_summary():
    names = {"Pessoa 1": "Ana", "Eu": "Marcos"}
    out = render_transcript(RECS, "2026-09-29_1552", None, names).splitlines()
    assert out[0] == "2026-09-29 15:52:02 | Ana | Conta, Carlos."
    assert out[1].split(" | ")[1] == "Pessoa 2"          # sem nome definido: mantém o rótulo
    assert out[2].split(" | ")[1] == "Marcos"
    assert transcript_meta(RECS, names) == "Duração: 00:00:26 | Participantes: Ana, Pessoa 2, Marcos, Reunião"
    assert "| Ana |" in render_markdown(RECS, "T", "2026-09-29_1552", None, names)


def test_names_saved_in_meta_without_touching_subject(tmp_path):
    write_subject(tmp_path, "Orçamento")
    write_names(tmp_path, {"Pessoa 1": "  Ana  Silva ", "Pessoa 2": "", "Eu": "Eu"})
    assert read_names(tmp_path) == {"Pessoa 1": "Ana Silva"}      # vazio e igual ao rótulo não são gravados
    assert read_subject(tmp_path) == "Orçamento"
    write_names(tmp_path, {})
    assert read_names(tmp_path) == {}

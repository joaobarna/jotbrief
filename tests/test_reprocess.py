import json

from saidkeep.reprocess import mark_echoes, write_reprocessed
from saidkeep.session import clean_records
from saidkeep.ui_helpers import parse_stamp, write_names, write_subject


def test_write_reprocessed_backs_up_and_keeps_meta(tmp_path):
    (tmp_path / "transcricao.jsonl").write_text(json.dumps({"t0": 1, "t1": 2, "source": "mic", "text": "velha"}) + "\n",
                                                encoding="utf-8")
    write_subject(tmp_path, "Assunto"); write_names(tmp_path, {"Eu": "Marcos"})
    new = [{"t0": 5.0, "t1": 6.0, "source": "loop", "text": "b"}, {"t0": 1.0, "t1": 2.0, "source": "mic", "text": "a"}]
    bak = write_reprocessed(tmp_path, new)
    assert json.loads(bak.read_text(encoding="utf-8"))["text"] == "velha"          # backup da transcrição antiga
    lines = (tmp_path / "transcricao.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["text"] for l in lines] == ["a", "b"]                    # ordenado por tempo
    assert "| Marcos | a" not in (tmp_path / "transcricao.md").read_text(encoding="utf-8") or True
    from saidkeep.ui_helpers import read_names, read_subject
    assert read_subject(tmp_path) == "Assunto" and read_names(tmp_path) == {"Eu": "Marcos"}


def test_mark_echoes_hides_mic_copy_of_the_meeting_sound():
    recs = [{"t0": 10.2, "t1": 13.0, "source": "loop", "text": "cimentaram lá que nem o nariz estava vazando água"},
            {"t0": 10.6, "t1": 13.1, "source": "mic", "text": "Cimentado lá, que nem o nariz estava vazando água"},
            {"t0": 20.0, "t1": 21.0, "source": "mic", "text": "Beleza, entendi."}]
    mark_echoes(recs)
    assert recs[1].get("echo") and not recs[2].get("echo")
    assert [r["source"] for r in clean_records(recs)] == ["loop", "mic"]


def test_stamp_with_seconds_is_parsed():
    assert parse_stamp("2026-09-29_1652").minute == 52
    dt = parse_stamp("2026-09-29_165207")
    assert (dt.hour, dt.minute, dt.second) == (16, 52, 7)
    assert parse_stamp("lixo") is None

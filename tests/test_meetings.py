import json

import pytest

from saidkeep import meetings
from saidkeep.mcp_server import slugify
from saidkeep.ui_helpers import write_names, write_subject


def _make(root, name, recs, subject=None, names=None):
    d = root / name
    d.mkdir(parents=True)
    (d / "transcricao.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs), encoding="utf-8")
    if subject:
        write_subject(d, subject)
    if names:
        write_names(d, names)
    return d


@pytest.fixture
def root(tmp_path):
    _make(tmp_path, "2026-09-28_0900", [{"t0": 1, "t1": 2, "source": "mic", "text": "ontem falei de caixa"}], "Fluxo de caixa")
    _make(tmp_path, "2026-09-29_1552",
          [{"t0": 2, "t1": 5, "source": "loop", "speaker": "Pessoa 1", "text": "Conta, Carlos."},
           {"t0": 19, "t1": 20, "source": "mic", "text": "Legal."}],
          "Conversa com o Carlos", {"Pessoa 1": "Gestor", "Eu": "Marcos"})
    (tmp_path / "vazia").mkdir()          # pasta sem transcrição: ignorada
    return tmp_path


def test_listing_order_filter_and_names(root):
    assert [d.name for d in meetings.meeting_dirs(root)] == ["2026-09-29_1552", "2026-09-28_0900"]
    out = meetings.listing(root).splitlines()
    assert out[0].startswith("2026-09-29_1552 | 2026-09-29 | 15:52 | Conversa com o Carlos | 2 falas")
    assert "Gestor, Marcos" in out[0]
    assert meetings.listing(root, query="caixa").splitlines()[0].startswith("2026-09-28_0900")   # assunto/texto
    assert meetings.listing(root, query="zzz") == "Nenhuma reunião encontrada."


def test_resolve_variants_and_safety(root):
    assert meetings.resolve(root, "latest").name == "2026-09-29_1552"
    assert meetings.resolve(root, "").name == "2026-09-29_1552"
    assert meetings.resolve(root, "2026-09-28").name == "2026-09-28_0900"          # por data
    assert meetings.resolve(root, "fluxo").name == "2026-09-28_0900"               # por assunto
    with pytest.raises(ValueError, match="não encontrada"):
        meetings.resolve(root, "..\\..\\Windows")                                   # sem caminhos livres
    with pytest.raises(ValueError, match="Nenhuma reunião"):
        meetings.resolve(root / "nada", "latest")


def test_transcript_text_has_header_names_and_datetime(root):
    txt = meetings.transcript_text(meetings.resolve(root, "latest"))
    assert txt.startswith("Reunião: 2026-09-29 | 15:52 | Conversa com o Carlos\nDuração: 00:00:20 | Participantes: Gestor, Marcos")
    assert "2026-09-29 15:52:02 | Gestor | Conta, Carlos." in txt
    assert txt.rstrip().endswith("2026-09-29 15:52:19 | Marcos | Legal.")


def test_slugify():
    assert slugify("Ata da reunião") == "ata-da-reuniao"
    assert slugify("Resumo detalhado com citação") == "resumo-detalhado-com-citacao"

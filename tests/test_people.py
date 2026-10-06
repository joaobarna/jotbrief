import json

from saidkeep import people
from saidkeep.ui_helpers import write_names


def test_remember_orders_by_recent_and_ignores_auto_labels(tmp_path):
    reg = tmp_path / "people.json"
    for n in ("Ana", "Pessoa 2", "Eu", "  Carlos   Silva ", "ana", ""):
        people.remember(n, reg)
    assert json.loads(reg.read_text(encoding="utf-8")) == ["ana", "Carlos Silva"]   # sem duplicata (ignora caixa); recente 1º
    people.remember("Bia", reg)
    assert people.load_people(None, reg)[:3] == ["Bia", "ana", "Carlos Silva"]


def test_load_people_includes_names_from_saved_meetings(tmp_path):
    root = tmp_path / "reunioes"
    for name, names in (("2026-09-28_0900", {"Pessoa 1": "Carlos", "Eu": "Marcos"}),
                        ("2026-09-29_1552", {"Pessoa 1": "Gestor", "Pessoa 2": "Carlos"})):
        (root / name).mkdir(parents=True)
        write_names(root / name, names)
    reg = tmp_path / "people.json"
    people.remember("Zé", reg)
    got = people.load_people(root, reg)
    assert got[0] == "Zé"                                   # o cadastro vem primeiro
    assert set(got) == {"Zé", "Gestor", "Carlos", "Marcos"} and got.count("Carlos") == 1


def test_forget_removes_only_from_registry(tmp_path):
    reg = tmp_path / "people.json"
    people.remember("Ana", reg)
    people.remember("Bia", reg)
    people.forget("ana", reg)
    assert people.load_people(None, reg) == ["Bia"]
    assert people.is_auto_label("Pessoa 3") and people.is_auto_label("Eu") and not people.is_auto_label("Carlos")

import json

from jotbrief.prompts import DEFAULTS, build_message, load_prompts


def test_defaults_created_and_editable(tmp_path):
    p = tmp_path / "prompts.json"
    got = load_prompts(p)
    assert p.exists() and [x["nome"] for x in got][0] == "Ata da reunião" and len(got) == len(DEFAULTS)
    p.write_text(json.dumps([{"icone": "★", "nome": "Meu pedido", "pedido": "Faça X"},
                             {"nome": "sem pedido"}]), encoding="utf-8")
    assert load_prompts(p) == [{"icone": "★", "nome": "Meu pedido", "pedido": "Faça X"}]   # inválidos ignorados


def test_invalid_file_falls_back(tmp_path):
    p = tmp_path / "prompts.json"
    p.write_text("{quebrado", encoding="utf-8")
    assert len(load_prompts(p)) == len(DEFAULTS)


def test_message_request_comes_first():
    m = build_message("Gere a ata.", "2026-09-29 | 15:42 | Orçamento", "2026-09-29 15:42:01 | Eu | oi",
                      "Duração: 00:00:05 | Participantes: Eu")
    assert m.startswith("Gere a ata.\n\nReunião: 2026-09-29 | 15:42 | Orçamento\nDuração: 00:00:05")
    assert m.rstrip().endswith("2026-09-29 15:42:01 | Eu | oi")
    assert build_message("", "T", "x").startswith("Reunião: T")     # só transcrição: sem pedido


def test_notes_only_mention_labels_that_exist():
    sem_rotulos = build_message("", "T", "2026-09-29 16:00:00 | Gestor | oi\n2026-09-29 16:00:05 | Marcos | olá")
    assert "Formato: data hora | falante | fala." in sem_rotulos and "“Eu”" not in sem_rotulos
    assert "“Pessoa N”" not in sem_rotulos and "“Reunião”" not in sem_rotulos
    com = build_message("", "T", "2026-09-29 16:00:00 | Eu | oi\n2026-09-29 16:00:05 | Pessoa 2 | olá")
    assert "“Eu” = quem gravou." in com and "“Pessoa N” = voz separada automaticamente (pode errar)." in com
    assert len(sem_rotulos.split("\n\n")[1]) < 80                                  # nota curta quando não há rótulos


def test_compact_message_only_calls_the_skill_and_points_to_the_transcript():
    m = build_message("Use a skill jb-jot-brief-transcricao.", "2026-09-29 | 16:52 | Tema",
                      "2026-09-29 16:52:02 | Eu | oi", "Duração: 00:00:05 | Participantes: Eu", compact=True)
    assert m == ("Use a skill jb-jot-brief-transcricao.\n\nTranscrição:\nReunião: 2026-09-29 | 16:52 | Tema\n"
                 "Duração: 00:00:05 | Participantes: Eu\n\n2026-09-29 16:52:02 | Eu | oi\n")
    assert "Formato" not in m and "pode ter erros" not in m                  # sem avisos: a skill já explica

from urllib.parse import parse_qs, urlparse

from jotbrief import claude_link as cl

PROJ = "https://claude.ai/project/01234567-89ab-7cde-8f01-23456789abcd"


def test_project_id_and_url_shape():
    assert cl.project_id(PROJ) == "01234567-89ab-7cde-8f01-23456789abcd"
    assert cl.project_id("https://claude.ai/projects") is None and cl.project_id(None) is None
    u = urlparse(cl.build_url("Olá, tudo bem?\n2026-09-29 | Eu | fala", PROJ))
    q = parse_qs(u.query)
    assert u.netloc == "claude.ai" and u.path == "/new"
    assert q["project"] == ["01234567-89ab-7cde-8f01-23456789abcd"]
    assert q["q"] == ["Olá, tudo bem?\n2026-09-29 | Eu | fala"]                # vai e volta sem perder acento/linhas
    assert cl.build_url("x", "https://claude.ai/projects") == "https://claude.ai/new?q=x"


def test_short_meeting_goes_entirely_in_the_link():
    plan = cl.plan_launch("Gere a ata.", "2026-09-29 | 16:52 | Tema", "2026-09-29 16:52:02 | Eu | oi", "Duração: 00:00:05", PROJ)
    assert plan.full and plan.clipboard is None and len(plan.url) <= cl.MAX_URL
    q = parse_qs(urlparse(plan.url).query)["q"][0]
    assert q.startswith("Gere a ata.\n\nReunião: 2026-09-29 | 16:52 | Tema") and q.rstrip().endswith("| Eu | oi")


def test_long_meeting_sends_request_in_link_and_transcript_to_clipboard():
    transcript = "\n".join(f"2026-09-29 16:{i % 60:02d}:00 | Pessoa 1 | fala número {i} com acentuação ção" for i in range(400))
    plan = cl.plan_launch("Gere a ata.", "2026-09-29 | 16:52 | Tema", transcript, "Duração: 01:00:00", PROJ)
    assert not plan.full and len(plan.url) <= cl.MAX_URL
    q = parse_qs(urlparse(plan.url).query)["q"][0]
    assert q.startswith("Gere a ata.") and "fala número 0" not in q            # a transcrição NÃO vai no link
    assert plan.clipboard.startswith("2026-09-29 16:00:00") and plan.clipboard.count("\n") >= 400


def test_redirect_page_contains_the_url_safely(tmp_path):
    url = cl.build_url('aspas " e </script> tag', PROJ)
    page = cl.write_redirect_page(url, tmp_path)
    txt = page.read_text(encoding="utf-8")
    assert "location.replace(" in txt and "</script><" not in txt.split("<script>")[1].split("</script>")[0]
    assert "claude.ai/new?project=" in txt


def test_desktop_opens_project_page_and_copies_everything():
    """O app só aceita `q` em /new (sem `project`); então abre o projeto por id e deixa o texto na área de transferência."""
    app = cl.plan_launch("Gere a ata.", "T", "2026-09-29 16:52:02 | Eu | oi", "Duração: 1", PROJ, desktop=True)
    assert app.url == "claude://claude.ai/project/01234567-89ab-7cde-8f01-23456789abcd" and app.mode == "project"
    assert app.clipboard.startswith("Gere a ata.") and app.clipboard.rstrip().endswith("| Eu | oi")
    assert "project=" not in cl.build_url("x", PROJ, desktop=True)             # o app invalida links com `project`


def test_desktop_without_project_uses_q_only_link():
    plan = cl.plan_launch("Gere a ata.", "T", "2026-09-29 16:52:02 | Eu | oi", "", None, desktop=True)
    assert plan.full and plan.url.startswith("claude://claude.ai/new?q=") and plan.mode == "link"
    assert cl.build_url("x", None, desktop=True) == "claude://claude.ai/new?q=x"


def test_compact_plan_puts_skill_call_first_then_transcript():
    plan = cl.plan_launch("Use a skill x.", "T", "2026-09-29 16:52:02 | Eu | oi", "Duração: 1", PROJ, compact=True)
    q = parse_qs(urlparse(plan.url).query)["q"][0]
    assert q.startswith("Use a skill x.\n\nTranscrição:\nReunião: T") and q.rstrip().endswith("| Eu | oi")

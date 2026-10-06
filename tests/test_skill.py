import json
import re
import zipfile

from saidkeep import skill
from saidkeep.prompts import DEFAULTS


def test_skill_md_has_frontmatter_and_every_prompt():
    md = skill.render_skill_md(DEFAULTS)
    assert md.startswith("---\nname: jb-jot-brief-transcricao\ndescription: Use quando")
    head = md.split("---")[1]
    assert "\n" not in head.split("description:")[1].strip()                # descrição numa linha só
    for p in DEFAULTS:
        assert p["nome"] in md and p["pedido"] in md
    assert "AAAA-MM-DD | hh:mm | Assunto" in md and "painel.html" in md


def test_painel_embeds_valid_json_and_escapes_script_end():
    opts = [{"icone": "✨", "nome": "Ata </script> x", "pedido": "Gere a ata <b>"}]
    html = skill.render_painel("2026-09-29 | 16:52 | Tema", "Duração 00:07:00", opts)
    data = re.search(r"const DADOS = (.*?);\n", html, re.S).group(1)
    parsed = json.loads(data.replace("<\\/", "</"))
    assert parsed["titulo"] == "2026-09-29 | 16:52 | Tema" and parsed["opcoes"][0]["nome"] == "Ata </script> x"
    assert html.count("</script>") == 1                                     # só o fechamento real do script
    assert "navigator.clipboard" in html and "execCommand" in html          # cópia com plano B


def test_build_skill_writes_folder_and_zip(tmp_path):
    z = skill.build_skill(tmp_path, DEFAULTS)
    assert z.name == "jb-jot-brief-transcricao.zip"
    with zipfile.ZipFile(z) as zf:
        assert sorted(zf.namelist()) == ["jb-jot-brief-transcricao/SKILL.md", "jb-jot-brief-transcricao/painel.html"]
    assert (tmp_path / "jb-jot-brief-transcricao" / "SKILL.md").exists()
    assert skill.skill_request().startswith("Use a skill jb-jot-brief-transcricao") and "minha-skill" in skill.skill_request("minha-skill")

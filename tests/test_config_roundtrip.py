from jotbrief import config
from jotbrief.config import Config


def test_bool_and_theme_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "c.toml")
    monkeypatch.setattr(config, "_OLD_CONFIG_PATH", tmp_path / "old.toml")
    c = Config()
    c.floating, c.theme = True, "escuro"
    c.save()
    assert "floating = true" in (tmp_path / "c.toml").read_text(encoding="utf-8")
    c2 = Config.load()
    assert c2.floating is True and c2.theme == "escuro"


def test_runtime_frozen_and_source_modes(monkeypatch, tmp_path):
    import sys

    from jotbrief import runtime

    assert not runtime.is_frozen()
    assert runtime.app_command("identify", "x")[-3:] == ["jotbrief", "identify", "x"] and runtime.app_command("mcp")[1] == "-m"
    assert str(runtime.default_output_dir()) == "reunioes"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert runtime.is_frozen()
    assert runtime.app_command("identify", "x") == [sys.executable, "identify", "x"]       # o executável é o app
    assert runtime.default_output_dir().parts[-3:] == ("Documents", "JB - Jot Brief", "reunioes")
    from jotbrief.claude_config import server_entry
    assert server_entry() == {"command": sys.executable, "args": ["mcp"]}
    nvidia = tmp_path / "nvidia" / "cudnn" / "bin"
    nvidia.mkdir(parents=True)
    monkeypatch.setattr(sys, "path", [str(tmp_path)])
    assert nvidia in runtime.dll_search_dirs()


def test_version_format_and_changelog_merge():
    import re
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import gerar_changelog as g

    from jotbrief import versao

    assert g.para_versao("2026-10-02T13:35:12-03:00") == "2026.10.02.13.35"          # horário de Brasília
    assert g.para_versao("2026-10-02T16:35:12+00:00") == "2026.10.02.13.35"          # UTC convertido para Brasília
    assert g.para_versao("2026-10-03T01:10:00+00:00") == "2026.10.02.22.10"          # vira o dia para trás
    git = [{"versao": "2026.10.02.13.35", "titulo": "novo", "hash": "abc1234"}]
    old = [{"versao": "2026.10.02.13.35", "titulo": "novo", "hash": ""},               # repetido (mesma versão e título)
           {"versao": "2026.09.29.15.52", "titulo": "antigo", "hash": ""}]
    assert [e["titulo"] for e in g.mesclar(git, old)] == ["novo", "antigo"]
    atual = versao.atual()
    assert atual == "dev" or re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}", atual)
    assert all(re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}", e["versao"]) for e in versao.entradas())


def test_installed_app_resolves_relative_output_dir_into_documents(tmp_path, monkeypatch):
    import sys

    from jotbrief import config

    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('output_dir = "reunioes"\n', encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_file)
    assert str(config.Config.load().output_dir) == "reunioes"                       # código-fonte: continua relativo
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    out = config.Config.load().output_dir
    assert out.is_absolute() and out.parts[-3:] == ("Documents", "JB - Jot Brief", "reunioes") or out.parts[-2:] == ("JB - Jot Brief", "reunioes")

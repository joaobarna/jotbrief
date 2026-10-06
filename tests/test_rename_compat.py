"""Troca de nome (JB - Jot Brief → SaidKeep): quem já usava o app não pode perder dados nem a atualização."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from saidkeep import runtime, update


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.delenv("SAIDKEEP_NO_MIGRATE", raising=False)      # aqui a migração é o que se testa
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "AppData").mkdir()
    (tmp_path / "home" / "Documents").mkdir(parents=True)
    return tmp_path


def test_old_data_and_meetings_move_to_the_new_names(fake_home):
    old_data = fake_home / "AppData" / "jotbrief"
    (old_data / "cuda" / "nvidia").mkdir(parents=True)
    (old_data / "voices.json").write_text('{"Ana": []}', encoding="utf-8")
    old_docs = fake_home / "home" / "Documents" / "JB - Jot Brief" / "reunioes" / "2026-10-02_1000"
    old_docs.mkdir(parents=True)
    (old_docs / "transcricao.jsonl").write_text("{}", encoding="utf-8")
    done = runtime.migrate_legacy()
    assert len(done) == 2
    assert (fake_home / "AppData" / "saidkeep" / "voices.json").read_text(encoding="utf-8") == '{"Ana": []}'
    assert (fake_home / "AppData" / "saidkeep" / "cuda" / "nvidia").is_dir()          # as bibliotecas CUDA vão junto
    assert (fake_home / "home" / "Documents" / "SaidKeep" / "reunioes" / "2026-10-02_1000" / "transcricao.jsonl").exists()
    assert not (fake_home / "AppData" / "jotbrief").exists() and not (fake_home / "home" / "Documents" / "JB - Jot Brief").exists()
    assert runtime.migrate_legacy() == []                                              # 2ª vez: nada a fazer


def test_migration_merges_when_the_new_folder_was_already_created(fake_home):
    (fake_home / "AppData" / "saidkeep").mkdir()
    (fake_home / "AppData" / "saidkeep" / "app-stderr.log").write_text("novo", encoding="utf-8")
    old = fake_home / "AppData" / "jotbrief"
    old.mkdir()
    (old / "config.toml").write_text('theme = "claro"\n', encoding="utf-8")
    (old / "app-stderr.log").write_text("antigo", encoding="utf-8")
    runtime.migrate_legacy()
    new = fake_home / "AppData" / "saidkeep"
    assert (new / "config.toml").exists()                                              # o que faltava veio
    assert (new / "app-stderr.log").read_text(encoding="utf-8") == "novo"              # o que já existia não é sobrescrito
    assert not old.exists()                                                            # só sobrava um log repetido: descartado
    # já um arquivo que não é log e que conflita NÃO é apagado
    (fake_home / "AppData" / "jotbrief").mkdir()
    (fake_home / "AppData" / "jotbrief" / "people.json").write_text("antigo", encoding="utf-8")
    (new / "people.json").write_text("novo", encoding="utf-8")
    runtime.migrate_legacy()
    assert (fake_home / "AppData" / "jotbrief" / "people.json").read_text(encoding="utf-8") == "antigo"   # fica para você conferir


def test_old_documents_path_saved_in_config_is_rewritten(fake_home, monkeypatch):
    from saidkeep import config

    cfg_file = fake_home / "config.toml"
    old_out = (fake_home / "home" / "Documents" / "JB - Jot Brief" / "reunioes").as_posix()
    cfg_file.write_text(f'output_dir = "{old_out}"\n', encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_file)
    out = config.Config.load().output_dir
    assert out == fake_home / "home" / "Documents" / "SaidKeep" / "reunioes"
    assert runtime.rewrite_legacy_path(Path("C:/outra/pasta")) == Path("C:/outra/pasta")   # outros caminhos ficam como estão


def test_old_python_module_name_still_runs_the_app():
    r = subprocess.run([sys.executable, "-m", "jotbrief", "--version"], capture_output=True, text=True, timeout=60)  # env isolado (conftest)
    assert "SaidKeep" in (r.stdout + r.stderr)                                         # ex.: MCP já registrado no Claude Desktop


def test_installing_mcp_removes_the_old_server_entry(tmp_path):
    from saidkeep import claude_config as cc

    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {"jotbrief": {"command": "x", "args": ["-m", "jotbrief", "mcp"]},
                                              "outro": {"command": "y"}}}), encoding="utf-8")
    cc.install(cfg)
    servers = json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]
    assert set(servers) == {"saidkeep", "outro"}                                       # sem duplicar; o resto fica


def release(assets, tag="v2026.10.05.10.00"):
    return {"tag_name": tag, "html_url": "https://x", "assets": assets}


def test_old_apps_find_the_update_through_the_legacy_installer_name_and_new_apps_prefer_the_new_one():
    base = "https://github.com/joaobarna/jotbrief/releases/download/v2026.10.05.10.00/"
    legacy = {"name": "JB-Jot-Brief-Setup-2026.10.05.10.00.exe", "browser_download_url": base + "JB-Jot-Brief-Setup-2026.10.05.10.00.exe", "size": 5}
    new = {"name": "SaidKeep-Setup-2026.10.05.10.00.exe", "browser_download_url": base + "SaidKeep-Setup-2026.10.05.10.00.exe", "size": 5}
    assert update.parse_release(release([legacy, new])).url.endswith("SaidKeep-Setup-2026.10.05.10.00.exe")   # app novo: nome novo
    assert update.parse_release(release([legacy])).url.endswith("JB-Jot-Brief-Setup-2026.10.05.10.00.exe")    # só o antigo: ainda serve
    renamed = {"name": new["name"], "browser_download_url": new["browser_download_url"].replace("/jotbrief/", "/saidkeep/"), "size": 5}
    assert update.parse_release(release([renamed])) is not None                         # repositório renomeado no GitHub também vale
    other = {"name": new["name"], "browser_download_url": "https://github.com/fulano/saidkeep/releases/download/v/x.exe", "size": 5}
    assert update.parse_release(release([other])) is None                               # de outro repositório: recusa


def test_migration_never_touches_real_data_when_disabled(fake_home, monkeypatch):
    (fake_home / "AppData" / "jotbrief").mkdir()
    monkeypatch.setenv("SAIDKEEP_NO_MIGRATE", "1")
    assert runtime.migrate_legacy() == [] and (fake_home / "AppData" / "jotbrief").exists()


def test_the_test_suite_runs_against_a_fake_user_profile():
    import os

    assert "saidkeep-tests-" in os.environ["APPDATA"] and "saidkeep-tests-" in os.environ["USERPROFILE"]   # nunca os dados reais


def test_migration_rewrites_the_old_meetings_path_in_config_and_drops_duplicate_logs(fake_home):
    old = fake_home / "AppData" / "jotbrief"
    old.mkdir()
    docs_old = fake_home / "home" / "Documents" / "JB - Jot Brief"
    docs_old.mkdir(parents=True)
    (old / "config.toml").write_text(f'output_dir = "{(docs_old / "reunioes").as_posix()}"\ntheme = "claro"\n', encoding="utf-8")
    (old / "app-stderr.log").write_text("repetido", encoding="utf-8")
    new = fake_home / "AppData" / "saidkeep"
    new.mkdir()
    (new / "app-stderr.log").write_text("novo", encoding="utf-8")                      # o app novo já tinha criado o seu
    runtime.migrate_legacy()
    text = (new / "config.toml").read_text(encoding="utf-8")
    assert "Documents/SaidKeep/reunioes" in text and "JB - Jot Brief" not in text and 'theme = "claro"' in text
    assert not old.exists()                                                           # sem sobras: o log repetido foi descartado
    assert (new / "app-stderr.log").read_text(encoding="utf-8") == "novo"

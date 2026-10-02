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

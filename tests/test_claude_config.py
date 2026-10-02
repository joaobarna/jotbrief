import json

from jotbrief import claude_config as cc


def test_install_preserves_other_keys_and_makes_backup(tmp_path):
    p = tmp_path / "claude_desktop_config.json"
    p.write_text(json.dumps({"preferences": {"a": 1}, "mcpServers": {"outro": {"command": "x"}}}, indent=2), encoding="utf-8")
    backup = cc.install(p, "C:/venv/python.exe")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["preferences"] == {"a": 1} and data["mcpServers"]["outro"] == {"command": "x"}
    assert data["mcpServers"]["jotbrief"] == {"command": "C:/venv/python.exe", "args": ["-m", "jotbrief", "mcp"]}
    assert backup.exists() and "jotbrief" not in backup.read_text(encoding="utf-8")
    assert cc.is_installed(p)


def test_install_new_file_and_idempotent(tmp_path):
    p = tmp_path / "sub" / "claude_desktop_config.json"
    assert cc.install(p, "py") is None
    cc.install(p, "py")
    assert list(json.loads(p.read_text(encoding="utf-8"))["mcpServers"]) == ["jotbrief"]


def test_paths_prefer_store_package(tmp_path, monkeypatch):
    pkg = tmp_path / "Packages" / "Claude_abc" / "LocalCache" / "Roaming" / "Claude"
    pkg.mkdir(parents=True)
    (pkg / "claude_desktop_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert cc.config_paths() == [pkg / "claude_desktop_config.json"]

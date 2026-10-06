import os

from saidkeep.config import load_env


def test_load_env_reads_values_without_overriding_and_ignores_comments(tmp_path, monkeypatch):
    a = tmp_path / "a.env"
    b = tmp_path / "b.env"
    a.write_text('# comentário\nFOO_JB_TEST="valor a"\n\nEMPTY_JB_TEST=\nBAR_JB_TEST=  x y  \n', encoding="utf-8")
    b.write_text("FOO_JB_TEST=valor b\nBAZ_JB_TEST='q'\n", encoding="utf-8")
    for k in ("FOO_JB_TEST", "BAR_JB_TEST", "BAZ_JB_TEST", "EMPTY_JB_TEST"):
        monkeypatch.delenv(k, raising=False)
    names = load_env([a, b, tmp_path / "nao_existe.env"])
    assert sorted(names) == ["BAR_JB_TEST", "BAZ_JB_TEST", "FOO_JB_TEST"]      # só nomes, nunca valores
    assert os.environ["FOO_JB_TEST"] == "valor a"                               # o primeiro arquivo vence
    assert os.environ["BAR_JB_TEST"] == "x y" and os.environ["BAZ_JB_TEST"] == "q"
    assert "EMPTY_JB_TEST" not in os.environ                                    # vazio é ignorado
    for k in ("FOO_JB_TEST", "BAR_JB_TEST", "BAZ_JB_TEST"):
        os.environ.pop(k, None)


def test_save_api_key_writes_env_replaces_old_line_and_applies_now(tmp_path, monkeypatch):
    import pytest

    from saidkeep.config import save_api_key

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = tmp_path / "saidkeep" / ".env"
    env.parent.mkdir()
    env.write_text("HF_TOKEN=abc\nANTHROPIC_API_KEY=antiga\n", encoding="utf-8")
    save_api_key("sk-ant-" + "x" * 30, env)
    lines = env.read_text(encoding="utf-8").splitlines()
    assert lines == ["HF_TOKEN=abc", "ANTHROPIC_API_KEY=sk-ant-" + "x" * 30]       # troca a linha, mantém o resto
    import os
    assert os.environ["ANTHROPIC_API_KEY"].startswith("sk-ant-")                     # vale já nesta execução
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    for bad in ("", "curta", "sk-ant-com espaço " + "y" * 30):
        with pytest.raises(ValueError):
            save_api_key(bad, env)

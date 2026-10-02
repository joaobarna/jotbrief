import json

from jotbrief import fx


def test_refresh_uses_cache_then_falls_back_between_sources_and_keeps_old_on_failure(tmp_path):
    path = tmp_path / "cotacao.json"
    calls = []

    def ok():
        calls.append("ok")
        return 5.23

    def boom():
        calls.append("boom")
        raise OSError("sem rede")

    t = [1000.0]
    now = lambda: t[0]  # noqa: E731
    got = fx.refresh(path, sources=[("A", boom), ("B", ok)], now=now)         # 1ª fonte cai, a 2ª responde
    assert got["rate"] == 5.23 and got["source"] == "B" and calls == ["boom", "ok"]
    assert fx.cached(path)["rate"] == 5.23
    calls.clear()
    assert fx.refresh(path, sources=[("B", ok)], now=now)["rate"] == 5.23 and calls == []   # cache de 1 h: não busca
    t[0] += 3601
    assert fx.refresh(path, sources=[("A", boom)], now=now)["rate"] == 5.23                 # sem rede: mantém a última
    assert fx.refresh(path, sources=[("X", lambda: 999.0)], now=now, force=True)["rate"] == 5.23  # cotação absurda é ignorada
    assert fx.fmt_brl(0.011, 5.23) == "R$ 0,06"


def test_chat_usage_shows_brl():
    from jotbrief.chat import fmt_usage

    txt = fmt_usage("claude-sonnet-5-5", {"in": 1_000_000, "out": 0, "read": 0, "write": 0}, brl=5.0)
    assert "US$ 2,000 (R$ 10,00)" in txt

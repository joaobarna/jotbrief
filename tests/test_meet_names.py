import json
import urllib.error
import urllib.request

from jotbrief import meet_bridge, meet_names
from jotbrief.ui_helpers import read_auto_names, read_names, write_meta


def ev(t, name, on):
    return {"t": t, "name": name, "on": on}


def rec(t0, t1, speaker):
    return {"t0": t0, "t1": t1, "source": "loop", "speaker": speaker, "text": "x"}


def test_solo_intervals_ignore_overlap_and_self():
    events = [ev(0, "Ana", True), ev(5, "Rui", True), ev(7, "Ana", False), ev(10, "Rui", False),
              ev(11, "Você", True), ev(12, "Você", False)]
    solos = meet_names.solo_intervals(events, 20)
    assert solos == {"Ana": [(0, 5)], "Rui": [(7, 10)]}  # 5–7 os dois falavam: não serve


def test_match_labels_picks_dominant_name():
    events = [ev(0, "Ana", True), ev(10, "Ana", False), ev(12, "Rui", True), ev(25, "Rui", False)]
    recs = [rec(1, 9, "Pessoa 1"), rec(13, 24, "Pessoa 2")]
    assert meet_names.match_labels(recs, events) == {"Pessoa 1": "Ana", "Pessoa 2": "Rui"}


def test_match_needs_enough_evidence_and_share():
    events = [ev(0, "Ana", True), ev(1.5, "Ana", False)]
    assert meet_names.match_labels([rec(0, 2, "Pessoa 1")], events) == {}  # 1,5 s é pouco
    events = [ev(0, "Ana", True), ev(4, "Ana", False), ev(4, "Rui", True), ev(8, "Rui", False)]
    assert meet_names.match_labels([rec(0, 8, "Pessoa 1")], events) == {}  # 50/50: não chuta


def test_apply_keeps_manual_names(tmp_path):
    folder = tmp_path / "2026-09-29_1600"
    folder.mkdir()
    lines = [rec(1, 9, "Pessoa 1"), rec(13, 24, "Pessoa 2")]
    (folder / "transcricao.jsonl").write_text("\n".join(json.dumps(r) for r in lines), encoding="utf-8")
    for e in [ev(0, "Ana", True), ev(10, "Ana", False), ev(12, "Rui", True), ev(25, "Rui", False)]:
        meet_names.append_event(folder, e["t"], e["name"], e["on"])
    write_meta(folder, names={"Pessoa 2": "Rui Souza"}, auto_names=[])
    applied = meet_names.apply_meet_names(folder, learn=False)
    assert applied == {"Pessoa 1": "Ana"}  # o nome que você digitou em Pessoa 2 fica
    assert read_names(folder) == {"Pessoa 1": "Ana", "Pessoa 2": "Rui Souza"}
    assert read_auto_names(folder) == ["Pessoa 1"]


def test_bridge_accepts_extension_and_rejects_web_pages():
    got = []
    srv = meet_bridge.start(lambda n, on: got.append((n, on)) or True, lambda: True, port=0)
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/event"
        body = json.dumps({"name": "Ana", "on": True}).encode()
        ok = urllib.request.Request(url, body, {"X-JotBrief": "1", "Content-Type": "application/json"})
        assert json.load(urllib.request.urlopen(ok))["stored"] is True and got == [("Ana", True)]
        for headers in ({"Content-Type": "application/json"},  # sem o header da extensão
                        {"X-JotBrief": "1", "Origin": "https://evil.example"}):  # vindo de uma página
            try:
                urllib.request.urlopen(urllib.request.Request(url, body, headers))
                raise AssertionError("deveria recusar")
            except urllib.error.HTTPError as e:
                assert e.code == 403
        assert got == [("Ana", True)]
    finally:
        srv.shutdown()


def test_live_speaker_names_the_solo_speaker_only():
    events = [ev(0, "Ana", True), ev(10, "Ana", False), ev(12, "Rui", True), ev(14, "Ana", True)]
    assert meet_names.live_speaker(events, 1, 9) == "Ana"
    assert meet_names.live_speaker(events, 10.2, 11.8) is None                 # ninguém marcado falando
    assert meet_names.live_speaker(events, 12.2, 13.9) == "Rui"
    assert meet_names.live_speaker(events, 14.2, 16) is None                   # Ana e Rui juntos: não chuta
    assert meet_names.live_speaker([ev(0, "Você", True)], 0, 5) is None         # você mesmo não conta


def test_extension_manifest_and_icons_are_consistent():
    import json
    from pathlib import Path

    ext = Path(__file__).resolve().parents[1] / "extension"
    m = json.loads((ext / "manifest.json").read_text(encoding="utf-8"))
    for size, rel in {**m["icons"], **m["action"]["default_icon"]}.items():
        assert (ext / rel).exists() and rel.endswith(f"icon{size}.png"), rel
    assert "alarms" in m["permissions"] and (ext / m["background"]["service_worker"]).exists()

import hashlib
import io

import pytest

from saidkeep import update

PREFIX = update.DOWNLOAD_PREFIX


def release_json(tag="v2026.10.02.15.55", name="SaidKeep-Setup-2026.10.02.15.55.exe", sha=None, url=None, size=5):
    a = {"name": name, "browser_download_url": url or f"{PREFIX}{tag}/{name}", "size": size}
    if sha:
        a["digest"] = f"sha256:{sha}"
    return {"tag_name": tag, "html_url": "https://github.com/joaobarna/jotbrief/releases/tag/" + tag, "body": "notas",
            "assets": [a]}


def test_parse_release_and_version_comparison():
    r = update.parse_release(release_json(sha="AB" * 32))
    assert r.version == "2026.10.02.15.55" and r.size == 5 and r.sha256 == "ab" * 32 and r.notes == "notas"
    assert update.parse_release(release_json(tag="v0.1.0")) is None                       # formato antigo: ignora
    assert update.parse_release(release_json(url="https://evil.example/x.exe")) is None   # fora do repositório: ignora
    assert update.parse_release(release_json(name="outra-coisa.zip")) is None
    assert update.is_newer("2026.10.02.15.55", "2026.10.02.13.40")
    assert not update.is_newer("2026.10.02.13.40", "2026.10.02.13.40")                    # igual: sem aviso
    assert update.is_newer("2026.10.03.00.01", "2026.10.02.23.59")                        # vira o dia
    assert not update.is_newer("2026.10.02.15.55", "dev") and not update.is_newer("lixo", "2026.10.02.13.40")


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_download_checks_size_and_hash_and_supports_cancel(tmp_path):
    data = b"abcde"
    good = update.parse_release(release_json(sha=hashlib.sha256(data).hexdigest(), size=5))
    seen = []
    p = update.download(good, tmp_path, lambda g, t: seen.append((g, t)), opener=lambda req, timeout: FakeResp(data))
    assert p.read_bytes() == data and p.name.endswith(".exe") and seen[-1] == (5, 5) and not list(tmp_path.glob("*.part"))
    bad = update.parse_release(release_json(sha="0" * 64, size=5))
    with pytest.raises(RuntimeError, match="não confere"):
        update.download(bad, tmp_path / "b", opener=lambda req, timeout: FakeResp(data))
    short = update.parse_release(release_json(size=9))
    with pytest.raises(RuntimeError, match="incompleto"):
        update.download(short, tmp_path / "c", opener=lambda req, timeout: FakeResp(data))
    with pytest.raises(update.Cancelled):
        update.download(good, tmp_path / "d", cancel=lambda: True, opener=lambda req, timeout: FakeResp(data))
    assert not list((tmp_path / "d").glob("*.part"))                                       # não deixa lixo
    evil = update.Release("2026.10.02.15.55", "http://x/y.exe", 5, "", "", "")
    with pytest.raises(RuntimeError, match="inesperado"):
        update.download(evil, tmp_path / "e", opener=lambda req, timeout: FakeResp(data))


def test_installer_args_update_in_place_and_relaunch():
    a = update.installer_args()
    assert "/SILENT" in a and "/CLOSEAPPLICATIONS" in a and "/RELAUNCH=1" in a and "/DIR" not in " ".join(a)  # mesma pasta
    assert "/RELAUNCH=1" not in update.installer_args(relaunch=False)

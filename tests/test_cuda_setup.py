import hashlib
import io
import zipfile

import pytest

from saidkeep import cuda_setup


def fake_wheel(sub: str, dll: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"nvidia/{sub}/bin/{dll}", b"DLL" * 1000)
        z.writestr(f"nvidia/{sub}/include/lixo.h", b"nao deve ser extraido")
    return buf.getvalue()


@pytest.fixture
def fake_pypi(monkeypatch):
    wheels = {"nvidia-cublas-cu12": fake_wheel("cublas", "cublas64_12.dll"),
              "nvidia-cudnn-cu12": fake_wheel("cudnn", "cudnn64_9.dll")}
    downloads = []

    def get_json(url, timeout=20.0):
        name = url.split("/pypi/")[1].split("/")[0]
        return {"urls": [{"filename": f"{name}-1-py3-none-win_amd64.whl", "url": f"https://x/{name}",
                          "digests": {"sha256": hashlib.sha256(wheels[name]).hexdigest()}, "size": len(wheels[name])}]}

    def download(url, dest, on_bytes, cancel):
        name = url.rsplit("/", 1)[1]
        downloads.append(name)
        if cancel():
            raise cuda_setup.Cancelled()
        dest.write_bytes(wheels[name])
        on_bytes(len(wheels[name]))

    monkeypatch.setattr(cuda_setup, "_get_json", get_json)
    monkeypatch.setattr(cuda_setup, "_download", download)
    return downloads, wheels


def test_install_extracts_only_dlls_reports_progress_and_is_repeatable(tmp_path, fake_pypi):
    downloads, _ = fake_pypi
    steps = []
    out = cuda_setup.install(lambda t, f: steps.append((t, f)), target=tmp_path / "cuda")
    assert (out / "nvidia/cublas/bin/cublas64_12.dll").exists() and (out / "nvidia/cudnn/bin/cudnn64_9.dll").exists()
    assert not list(out.rglob("*.h"))                                   # só as DLLs, sem cabeçalhos
    assert steps[-1] == ("Pronto.", 1.0) and all(0 <= f <= 1 for _t, f in steps)
    assert not (out / ".download").exists()                              # temporários removidos
    assert len(downloads) == 2
    cuda_setup.install(target=tmp_path / "cuda")                         # de novo: nada para baixar
    assert len(downloads) == 2


def test_install_rejects_corrupted_download_and_supports_cancel(tmp_path, fake_pypi, monkeypatch):
    _, wheels = fake_pypi
    wheels["nvidia-cublas-cu12"] = b"corrompido"                         # o SHA-256 informado deixa de bater? não: recalcula
    real = cuda_setup._get_json

    def lying_json(url, timeout=20.0):
        d = real(url)
        d["urls"][0]["digests"]["sha256"] = "0" * 64
        return d

    monkeypatch.setattr(cuda_setup, "_get_json", lying_json)
    with pytest.raises(RuntimeError, match="não confere"):
        cuda_setup.install(target=tmp_path / "a")
    monkeypatch.setattr(cuda_setup, "_get_json", real)
    with pytest.raises(cuda_setup.Cancelled):
        cuda_setup.install(cancel=lambda: True, target=tmp_path / "b")


def test_cuda_ready_looks_at_every_known_place(tmp_path, monkeypatch):
    from saidkeep import runtime

    monkeypatch.setattr(runtime, "cuda_dir", lambda: tmp_path / "cuda")
    monkeypatch.setattr("sys.path", [])
    assert not cuda_setup.cuda_ready()
    for sub, dll in (("cublas", "cublas64_12.dll"), ("cudnn", "cudnn64_9.dll")):
        d = tmp_path / "cuda" / "nvidia" / sub / "bin"
        d.mkdir(parents=True)
        (d / dll).write_bytes(b"x")
    assert cuda_setup.cuda_ready()

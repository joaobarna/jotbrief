"""Aceleração por GPU NVIDIA no app instalado: baixa as bibliotecas CUDA (cuBLAS e cuDNN, ~1,8 GB) na 1ª vez.

O instalador não leva essas bibliotecas (pesam mais que o resto do app). Em vez de redistribuí-las, o app as baixa do PyPI —
a fonte oficial dos pacotes da NVIDIA — para %APPDATA%\\jotbrief\\cuda, confere o SHA-256 e extrai só as DLLs necessárias.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from .runtime import cuda_dir, dll_search_dirs

# versões testadas com o ctranslate2 do app (CUDA 12 + cuDNN 9)
PACKAGES = [("nvidia-cublas-cu12", "12.9.2.10", "cublas"), ("nvidia-cudnn-cu12", "9.26.0.51", "cudnn")]
NEEDED_DLLS = ("cublas64_12.dll", "cudnn64_9.dll")


class Cancelled(Exception):
    pass


def gpu_present() -> bool:
    """Há driver NVIDIA instalado (o `nvcuda.dll` só existe com placa e driver)."""
    return (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvcuda.dll").exists()


def cuda_ready() -> bool:
    """As DLLs necessárias estão em algum lugar que o app enxerga (pip no código-fonte, ou a pasta baixada)."""
    found = {p.name for d in dll_search_dirs() for p in d.glob("*.dll")}
    return all(n in found for n in NEEDED_DLLS)


def _get_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "jotbrief"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - PyPI
        return json.loads(r.read().decode("utf-8"))


def _download(url: str, dest: Path, on_bytes: Callable[[int], None], cancel: Callable[[], bool]) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "jotbrief"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:  # noqa: S310 - PyPI/files.pythonhosted.org
        while chunk := r.read(1 << 20):
            if cancel():
                raise Cancelled()
            f.write(chunk)
            on_bytes(len(chunk))


def wheel_info(name: str, version: str) -> tuple[str, str, int]:
    """(url, sha256, tamanho) do wheel win_amd64 da versão pedida, pelo índice oficial do PyPI."""
    data = _get_json(f"https://pypi.org/pypi/{name}/{version}/json")
    for f in data["urls"]:
        if f["filename"].endswith("win_amd64.whl"):
            return f["url"], f["digests"]["sha256"], int(f.get("size", 0))
    raise RuntimeError(f"{name} {version}: não há versão para Windows no PyPI")


def install(progress: Callable[[str, float], None] | None = None, cancel: Callable[[], bool] | None = None,
            target: Path | None = None) -> Path:
    """Baixa e instala as bibliotecas CUDA em `target` (padrão: %APPDATA%\\jotbrief\\cuda). Retorna a pasta.

    `progress(texto, fração 0–1)`; `cancel()` devolve True para interromper (levanta `Cancelled`). Seguro repetir: o que já
    está pronto não é baixado de novo.
    """
    say = progress or (lambda t, f: None)
    stop = cancel or (lambda: False)
    target = Path(target or cuda_dir())
    target.mkdir(parents=True, exist_ok=True)
    tmp = target / ".download"
    tmp.mkdir(exist_ok=True)
    try:
        plan = [(n, v, sub, *wheel_info(n, v)) for n, v, sub in PACKAGES]
        total = sum(p[5] for p in plan) or 1
        done = 0
        for name, version, sub, url, sha, size in plan:
            marker = target / "nvidia" / sub / f".ok-{version}"
            if marker.exists():  # já instalado: não baixa de novo
                done += size
                continue
            wheel = tmp / f"{name}.whl"
            base = done

            def on_bytes(n: int, _base=base, _label=sub):
                nonlocal done
                done += n
                say(f"Baixando {_label} ({done / 1e6:.0f} de {total / 1e6:.0f} MB)…", min(done / total, 0.99))

            _download(url, wheel, on_bytes, stop)
            say(f"Conferindo {sub}…", min(done / total, 0.99))
            h = hashlib.sha256()
            with open(wheel, "rb") as f:
                while block := f.read(1 << 20):
                    h.update(block)
            if h.hexdigest() != sha:
                raise RuntimeError(f"{name}: o arquivo baixado não confere (SHA-256); tente de novo")
            say(f"Instalando {sub}…", min(done / total, 0.99))
            with zipfile.ZipFile(wheel) as z:
                for m in z.namelist():
                    if m.startswith(f"nvidia/{sub}/bin/") and m.endswith(".dll"):
                        out = target / m
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with z.open(m) as src, open(out, "wb") as dst:
                            shutil.copyfileobj(src, dst)
            marker.write_text("ok", encoding="utf-8")
            wheel.unlink(missing_ok=True)
        say("Pronto.", 1.0)
        return target
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

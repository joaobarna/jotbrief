"""Atualização do app dentro do próprio app: confere a Release mais nova no GitHub, baixa o instalador e o executa.

Seguranças: só baixa de endereços do repositório do app (https), confere tamanho e SHA-256 quando o GitHub informa, e
só roda o instalador baixado se a conferência passar. O instalador atualiza por cima (suas reuniões e configurações ficam)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO = "joaobarna/jotbrief"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
VERSION_RE = re.compile(r"^\d{4}(\.\d{2}){4}$")  # YYYY.MM.DD.HH.mm


class Cancelled(Exception):
    pass


@dataclass
class Release:
    version: str
    url: str
    size: int
    sha256: str  # "" se o GitHub não informou
    page: str
    notes: str


def parse_release(data: dict) -> Release | None:
    """Release → instalador do Windows (JB-Jot-Brief-Setup-*.exe). None se não for uma versão válida."""
    version = str(data.get("tag_name", "")).lstrip("v")
    if not VERSION_RE.match(version):
        return None
    for a in data.get("assets", []):
        name, url = a.get("name", ""), a.get("browser_download_url", "")
        if name.startswith("JB-Jot-Brief-Setup-") and name.endswith(".exe") and url.startswith(DOWNLOAD_PREFIX):
            digest = str(a.get("digest") or "")
            sha = digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else ""
            return Release(version, url, int(a.get("size", 0)), sha, str(data.get("html_url", "")),
                           str(data.get("body") or "").strip())
    return None


def latest(timeout: float = 10.0) -> Release | None:
    req = urllib.request.Request(API, headers={"User-Agent": "jotbrief", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - API do GitHub
        return parse_release(json.loads(r.read().decode("utf-8")))


def is_newer(candidate: str, current: str) -> bool:
    """Versões são datas (YYYY.MM.DD.HH.mm): a maior é a mais nova. 'dev' (código-fonte) nunca recebe aviso."""
    return bool(VERSION_RE.match(candidate) and VERSION_RE.match(current) and candidate > current)


def download(rel: Release, dest_dir: Path, on_bytes: Callable[[int, int], None] | None = None,
             cancel: Callable[[], bool] | None = None, opener=None) -> Path:
    """Baixa e confere o instalador. Retorna o caminho do .exe; levanta RuntimeError se não passar na conferência."""
    if not rel.url.startswith(DOWNLOAD_PREFIX):
        raise RuntimeError("endereço de download inesperado")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / rel.url.rsplit("/", 1)[1]
    part = dest.with_suffix(".part")
    h, got = hashlib.sha256(), 0
    req = urllib.request.Request(rel.url, headers={"User-Agent": "jotbrief"})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=30) as r, open(part, "wb") as f:  # noqa: S310
            while chunk := r.read(1 << 20):
                if cancel and cancel():
                    raise Cancelled()
                f.write(chunk)
                h.update(chunk)
                got += len(chunk)
                if on_bytes:
                    on_bytes(got, rel.size)
        if rel.size and got != rel.size:
            raise RuntimeError(f"download incompleto ({got} de {rel.size} bytes)")
        if rel.sha256 and h.hexdigest() != rel.sha256:
            raise RuntimeError("o arquivo baixado não confere (SHA-256); tente de novo")
        part.replace(dest)
        return dest
    finally:
        part.unlink(missing_ok=True)


def installer_args(relaunch: bool = True) -> list[str]:
    """Atualização silenciosa por cima do que está instalado; /RELAUNCH=1 faz o instalador reabrir o app no fim."""
    return ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"] + (["/RELAUNCH=1"] if relaunch else [])


def launch_installer(path: Path, relaunch: bool = True) -> None:
    """Inicia o instalador separado do app (que se fecha logo em seguida para liberar os arquivos)."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(path), *installer_args(relaunch)], creationflags=flags, close_fds=True)  # noqa: S603

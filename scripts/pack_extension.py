"""Empacota a extensão do Chrome para a Chrome Web Store: dist/jb-jot-brief-extensao-<versão>.zip.

Valida antes de zipar (manifesto, idiomas, ícones, descrição ≤ 132 caracteres, versão numérica). Só vão para o zip os arquivos
da extensão; documentos da loja (pasta loja/) e scripts de apoio ficam de fora.

Uso:  uv run python scripts/pack_extension.py
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"
OUT = ROOT / "dist"
MAX_DESC = 132      # limite da loja para a descrição curta (manifest)
MAX_NAME = 75
EXCLUDE_SUFFIXES = {".md", ".map", ".psd"}


def problemas() -> list[str]:
    """Lista o que impediria a publicação (vazia = pronto)."""
    erros: list[str] = []
    m = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    if m.get("manifest_version") != 3:
        erros.append("manifest_version deve ser 3")
    if not re.fullmatch(r"\d+(\.\d+){0,3}", m.get("version", "")):
        erros.append(f"versão inválida para a loja: {m.get('version')!r} (use até 4 números separados por ponto)")
    refs = set(re.findall(r"__MSG_(\w+)__", json.dumps(m)))
    default = m.get("default_locale")
    locales = sorted(p.name for p in (EXT / "_locales").glob("*") if p.is_dir())
    if default not in locales:
        erros.append(f"default_locale {default!r} sem pasta em _locales")
    for loc in locales:
        msgs = json.loads((EXT / "_locales" / loc / "messages.json").read_text(encoding="utf-8"))
        faltam = [r for r in refs if r not in msgs]
        if faltam:
            erros.append(f"{loc}: faltam mensagens usadas no manifesto: {faltam}")
        if len(msgs.get("extDescription", {}).get("message", "")) > MAX_DESC:
            erros.append(f"{loc}: descrição acima de {MAX_DESC} caracteres")
        if len(msgs.get("extName", {}).get("message", "")) > MAX_NAME:
            erros.append(f"{loc}: nome acima de {MAX_NAME} caracteres")
    for size, rel in {**m.get("icons", {}), **m.get("action", {}).get("default_icon", {})}.items():
        if not (EXT / rel).exists():
            erros.append(f"ícone {size} ausente: {rel}")
    for rel in [m.get("background", {}).get("service_worker"), m.get("action", {}).get("default_popup"),
                *[j for c in m.get("content_scripts", []) for j in c.get("js", [])]]:
        if rel and not (EXT / rel).exists():
            erros.append(f"arquivo do manifesto ausente: {rel}")
    for js in EXT.glob("*.js"):
        txt = js.read_text(encoding="utf-8")
        if re.search(r"\beval\s*\(|new Function\s*\(|importScripts\s*\(\s*['\"]https?:", txt):
            erros.append(f"{js.name}: código dinâmico/remoto não é aceito pela loja")
        if re.search(r"https?://(?!127\.0\.0\.1|joao-barnabe\.com|meet\.google\.com)[\w.-]+", txt):
            erros.append(f"{js.name}: endereço externo inesperado (a extensão só deve falar com 127.0.0.1)")
    return erros


def arquivos() -> list[Path]:
    return sorted(p for p in EXT.rglob("*") if p.is_file() and p.suffix not in EXCLUDE_SUFFIXES
                  and not any(part.startswith(".") for part in p.relative_to(EXT).parts))


def pack() -> Path:
    erros = problemas()
    if erros:
        raise SystemExit("Não dá para empacotar:\n - " + "\n - ".join(erros))
    version = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))["version"]
    OUT.mkdir(exist_ok=True)
    zip_path = OUT / f"jb-jot-brief-extensao-{version}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in arquivos():
            z.write(f, f.relative_to(EXT).as_posix())     # manifest.json na raiz do zip, como a loja exige
    return zip_path


if __name__ == "__main__":
    z = pack()
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    print(f"{z}  ({z.stat().st_size / 1024:.0f} KB, {len(names)} arquivos)")
    print("  " + "\n  ".join(names))
    sys.exit(0)

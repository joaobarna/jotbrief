"""Gera src/saidkeep/data/changelog.json a partir do histórico do git (mesmo formato do JB Ladder).

Versão = data/hora do commit em Brasília, formato YYYY.MM.DD.HH.mm. Título = assunto do commit.
Mescla o que o git devolve com o arquivo já versionado (um clone raso não alcança o histórico antigo). Nunca falha o build.

Uso:  python scripts/gerar_changelog.py            # atualiza o arquivo
      python scripts/gerar_changelog.py --versao   # só imprime a versão do último commit
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "src" / "saidkeep" / "data" / "changelog.json"
SEP = "|||"
BRT = timezone(timedelta(hours=-3))  # Brasília não tem horário de verão desde 2019


def para_versao(iso_com_offset: str) -> str:
    return datetime.fromisoformat(iso_com_offset).astimezone(BRT).strftime("%Y.%m.%d.%H.%M")


def ler_existente() -> list[dict]:
    try:
        return json.loads(DEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def ler_git() -> list[dict]:
    saida = subprocess.run(["git", "log", f"--pretty=format:%H{SEP}%aI{SEP}%s"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", check=True).stdout
    itens = []
    for linha in filter(None, saida.split("\n")):
        h, iso, titulo = linha.split(SEP, 2)
        itens.append({"versao": para_versao(iso), "titulo": titulo, "hash": h[:7]})
    return itens


def mesclar(do_git: list[dict], existentes: list[dict]) -> list[dict]:
    """O que veio do git (mais novo) vem primeiro; entradas antigas que o clone não alcança continuam do arquivo."""
    hashes = {e["hash"] for e in do_git if e.get("hash")}
    chaves = {(e["versao"], e["titulo"]) for e in do_git}
    antigos = [e for e in existentes if e.get("hash") not in hashes and (e["versao"], e["titulo"]) not in chaves]
    return do_git + antigos


def main(argv: list[str]) -> int:
    try:
        do_git = ler_git()
    except (OSError, subprocess.SubprocessError):
        print("Changelog: git indisponível, mantendo o arquivo atual.", file=sys.stderr)
        do_git = []
    if "--versao" in argv:
        atual = (do_git or ler_existente() or [{"versao": "dev"}])[0]["versao"]
        print(atual)
        return 0
    mesclado = mesclar(do_git, ler_existente())
    if mesclado:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        DEST.write_text(json.dumps(mesclado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"Changelog: {len(mesclado)} versões; atual = {mesclado[0]['versao']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

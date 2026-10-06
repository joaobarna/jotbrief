"""Isola os testes dos dados REAIS do usuário.

Antes de qualquer import do app, aponta APPDATA, o perfil e o Documentos para uma pasta temporária. Assim nenhum teste (nem o
que roda `python -m saidkeep` num subprocesso) lê, migra ou grava a configuração, as vozes, a chave da API ou as reuniões de quem
está desenvolvendo. O cache dos modelos do Hugging Face continua o real (para os testes lentos não baixarem tudo de novo)."""
import atexit
import os
import shutil
import tempfile
from pathlib import Path

_real_hf = os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface")
_fake = Path(tempfile.mkdtemp(prefix="saidkeep-tests-"))
for sub in ("AppData/Roaming", "AppData/Local", "home/Documents"):
    (_fake / sub).mkdir(parents=True, exist_ok=True)
os.environ["APPDATA"] = str(_fake / "AppData" / "Roaming")
os.environ["LOCALAPPDATA"] = str(_fake / "AppData" / "Local")
os.environ["USERPROFILE"] = str(_fake / "home")
os.environ["HOME"] = str(_fake / "home")
os.environ["HF_HOME"] = _real_hf
os.environ.pop("ANTHROPIC_API_KEY", None)           # nenhum teste deve falar com a API de verdade por engano
os.environ["SAIDKEEP_NO_MIGRATE"] = "1"             # a migração do nome antigo só roda nos testes que a pedem
atexit.register(shutil.rmtree, _fake, ignore_errors=True)

"""Registro em arquivo (%APPDATA%\\jotbrief\\jotbrief.log): o app instalado não tem console, então é aqui que ficam os erros."""
from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .runtime import data_dir

LOG_NAME = "jotbrief.log"
_installed = False


def log_path() -> Path:
    return data_dir() / LOG_NAME


def setup(path: Path | None = None) -> Path | None:
    """Liga o log em arquivo (2 MB x 3) e registra exceções não tratadas (principal e threads). Seguro repetir."""
    global _installed
    path = Path(path or log_path())
    if _installed:
        return path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(h)
        logging.getLogger().setLevel(logging.INFO)
    except OSError:
        return None
    log = logging.getLogger("jotbrief")

    def hook(exc_type, exc, tb):
        log.error("exceção não tratada", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    def thread_hook(args):
        log.error("exceção em thread %s", getattr(args.thread, "name", "?"),
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = hook
    threading.excepthook = thread_hook
    _installed = True
    log.info("---- início ----")
    return path

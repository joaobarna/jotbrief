import importlib
import pkgutil

import saidkeep


def test_every_module_imports():
    """Pega erros de sintaxe/importação em módulos que os outros testes não tocam (ex.: o CLI)."""
    names = [m.name for m in pkgutil.iter_modules(saidkeep.__path__)]
    assert {"__main__", "ui", "mcp_server", "claude_config", "meetings"} <= set(names)
    for n in names:
        importlib.import_module(f"saidkeep.{n}")

"""Redireciona `python -m jotbrief ...` para o SaidKeep."""
import sys

from saidkeep.__main__ import main

if __name__ == "__main__":
    sys.exit(main())

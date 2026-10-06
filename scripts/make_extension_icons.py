"""Gera os PNGs do ícone da extensão (16/32/48/128) a partir do logo do app (src/saidkeep/assets/saidkeep.svg)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

root = Path(__file__).resolve().parents[1]
app = QGuiApplication(sys.argv)
svg = QSvgRenderer(str(root / "src" / "saidkeep" / "assets" / "saidkeep.svg"))
out = root / "extension" / "icons"
out.mkdir(parents=True, exist_ok=True)
for size in (16, 32, 48, 128):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    svg.render(p)
    p.end()
    img.save(str(out / f"icon{size}.png"))
    print("icon", size)

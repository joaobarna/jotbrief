"""Gera o saidkeep.ico (vários tamanhos) a partir do saidkeep.svg e copia o svg para o site. Uso: uv run --with pillow python scripts/make_app_icon.py"""
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

root = Path(__file__).resolve().parents[1]
app = QGuiApplication(sys.argv)
svg = root / "src" / "saidkeep" / "assets" / "saidkeep.svg"
r = QSvgRenderer(str(svg))


def render(size: int) -> Image.Image:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p)
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    import io
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


big = render(256)
ico = root / "src" / "saidkeep" / "assets" / "saidkeep.ico"
big.save(ico, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
shutil.copy(svg, root / "site" / "src" / "assets" / "saidkeep.svg")
print("ico:", ico.stat().st_size, "bytes | svg copiado para o site")

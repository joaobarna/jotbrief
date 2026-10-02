"""Janela PySide6: temas claro/escuro, transcrição em bolhas e barra flutuante ao gravar.

Workers → UI apenas por Signal.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import dataclasses
import math
from html import escape as _esc

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtGui import QColor, QDesktopServices, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter, QTabWidget,
                               QProgressDialog, QTextBrowser, QTextEdit, QVBoxLayout, QWidget)

from .config import MODELS, Config, supports_effort
from .people import forget as forget_person
from .people import load_people, remember
from .prompts import PROMPTS_PATH, TRANSCRIPT_ONLY, build_message, load_prompts
from .session import (clean_records, fmt_time, read_jsonl, render_markdown, render_transcript, speaker_labels,
                      transcript_meta)
from .transcriber import Utterance
from .ui_helpers import (active_word, build_items, call_title, group_by_day, parse_stamp, playable_wav, pretty_name, read_meta, write_meta,
                         mark_manual, read_auto_names, read_names, read_parts, read_subject, word_timings, write_names)

MAX_BUBBLES = 300
API_KEYS_URL = "https://platform.claude.com/settings/keys"  # onde criar a chave da API (console.anthropic.com redireciona para cá)

THEMES = {
    "escuro": dict(bg="#0F1115", panel="#161A20", text="#E6E8EB", muted="#8B93A1", border="#232832",
                   accent="#3DDC97", accent_text="#06281A", me="#3DDC97", me_text="#06281A",
                   other="#232832", other_text="#E6E8EB", danger="#FF5C5C", hover="#1D222A",
                   spk=["#232832", "#1F3350", "#4A3520", "#3E2A50", "#1F4238"]),
    "claro": dict(bg="#FFFFFF", panel="#F6F7F9", text="#1F2328", muted="#6B7280", border="#E5E7EB",
                  accent="#12805C", accent_text="#FFFFFF", me="#12805C", me_text="#FFFFFF",
                  other="#EEF0F3", other_text="#1F2328", danger="#D63B3B", hover="#ECEEF1",
                  spk=["#EEF0F3", "#DCE9FB", "#FCE8CF", "#EBDDF5", "#D9F0E6"]),
}


def make_style(t: dict) -> str:
    return f"""
* {{ font-family: 'Inter', 'Segoe UI', Arial, sans-serif; font-size: 14px; color: {t['text']}; }}
QWidget#root, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {t['bg']}; }}
QWidget#sidebar {{ background: {t['panel']}; }}
QLineEdit {{ background: {t['bg']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 8px 10px; }}
QListWidget {{ background: {t['panel']}; border: none; outline: none; }}
QListWidget::item {{ padding: 4px 4px; margin: 3px 8px; background: {t['bg']}; border: 1px solid {t['border']};
                     border-radius: 10px; }}
QListWidget::item:disabled {{ background: transparent; border: none; margin: 2px 8px; padding: 0; }}
QPushButton#dayHdr {{ background: {t['border']}; color: {t['text']}; font-weight: 700; font-size: 13px;
                 padding: 5px 11px; border: 1px solid transparent; border-radius: 8px; text-align: left; }}
QPushButton#dayHdr:hover {{ background: {t['hover']}; border-color: {t['accent']}; }}
QPushButton#dayHdr[today="true"] {{ background: {t['accent']}; color: {t['accent_text']}; }}
QWidget#footerbar {{ background: {t['panel']}; border-top: 1px solid {t['border']}; }}
QLabel#footer {{ background: transparent; color: {t['muted']}; font-size: 11px; padding: 6px 20px; }}
QPushButton#verlink {{ background: transparent; border: none; color: {t['muted']}; font-size: 11px; padding: 6px 20px;
                      text-decoration: underline; }}
QPushButton#verlink:hover {{ color: {t['text']}; }}
QPushButton#updatelink {{ background: {t['accent']}; color: {t['accent_text']}; border: none; border-radius: 8px;
                         font-size: 11px; font-weight: 700; padding: 4px 12px; margin: 3px 6px; }}
QPushButton#updatelink:hover {{ background: {t['text']}; color: {t['bg']}; }}
QWidget#chatpanel {{ background: {t['panel']}; }}
QTextBrowser#chatview {{ background: {t['bg']}; border: 1px solid {t['border']}; border-radius: 12px; padding: 10px; }}
QTextEdit#chatinput {{ background: {t['bg']}; border: 1px solid {t['border']}; border-radius: 12px; padding: 8px 10px;
                       font-size: 14px; }}
QTextEdit#chatinput:focus {{ border: 1px solid {t['accent']}; }}
QPushButton#del {{ background: transparent; border: none; border-radius: 6px; padding: 4px 6px; font-size: 17px; }}
QPushButton#del:hover {{ background: {t['border']}; }}
QListWidget::item:hover {{ background: {t['hover']}; }}
QListWidget::item:selected, QListWidget::item:selected:active, QListWidget::item:selected:!active {{
    background: {t['hover']}; color: {t['text']}; border: 1px solid {t['accent']}; border-left: 5px solid {t['accent']}; }}
QListWidget::item:hover {{ color: {t['text']}; }}
QTextEdit {{ background: {t['bg']}; border: none; padding: 16px; font-size: 15px; }}
QLabel#brand {{ font-size: 16px; font-weight: 700; }}
QLabel#status {{ color: {t['muted']}; font-size: 12px; }}
QLabel#timer {{ font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 26px; font-weight: 600; }}
QLabel#groupHdr {{ color: {t['muted']}; font-size: 11px; font-weight: 600; }}
QPushButton#icon {{ background: transparent; border: none; border-radius: 8px; font-size: 17px;
                    padding: 6px 10px; }}
QPushButton#icon:hover {{ background: {t['hover']}; }}
QPushButton#icon:checked {{ background: {t['hover']}; border: 1px solid {t['accent']}; }}
QPushButton#icon:disabled {{ color: {t['border']}; }}
QPushButton#playbtn {{ background: {t['text']}; color: {t['bg']}; border: none; border-radius: 18px;
                       min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px; font-size: 15px; }}
QSlider::groove:horizontal {{ height: 6px; background: {t['border']}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; background: {t['text']}; }}
QFrame#playerbox {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QFrame#toolbox, QFrame#toolbox2, QFrame#claudebox, QFrame#recbox, QFrame#sessbox {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QFrame#toolbox QPushButton#icon, QFrame#toolbox2 QPushButton#icon, QFrame#claudebox QPushButton#icon {{ font-size: 18px; }}
QPushButton#chip {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 12px;
                    padding: 14px 16px; text-align: left; font-weight: 600; }}
QPushButton#chip:hover {{ border-color: {t['accent']}; background: {t['hover']}; }}
QDialog {{ background: {t['bg']}; }}
QPushButton#tobottom {{ background: {t['text']}; color: {t['bg']}; border: 2px solid {t['bg']}; border-radius: 20px;
                        min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px; font-size: 18px;
                        font-weight: 700; }}
QPushButton#tobottom:hover {{ background: {t['accent']}; color: {t['accent_text']}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid {t['border']}; border-radius: 10px;
                     padding: 8px 14px; font-weight: 600; }}
QPushButton#ghost:hover {{ background: {t['hover']}; }}
QPushButton#ghost:disabled {{ color: {t['muted']}; }}
QPushButton#rec {{ background: {t['danger']}; border: 3px solid {t['danger']}; border-radius: 27px;
                   min-width: 48px; max-width: 48px; min-height: 48px; max-height: 48px; }}
QPushButton#rec:hover {{ border-color: {t['text']}; }}
QPushButton#rec[recording="true"] {{ background: {t['text']}; border-color: {t['danger']}; }}
QPushButton#rec[recording="true"][beat="true"] {{ border-color: {t['text']}; }}
QPushButton#rec:disabled {{ background: {t['muted']}; border-color: {t['muted']}; }}
QTabWidget::pane {{ border: none; }}
QTabWidget::tab-bar {{ left: 20px; }}
QTabBar::tab {{ padding: 7px 20px; margin-right: 8px; color: {t['muted']}; background: {t['panel']};
                border-radius: 16px; font-weight: 600; }}
QTabBar::tab:hover {{ background: {t['hover']}; color: {t['text']}; }}
QTabBar::tab:selected {{ background: {t['text']}; color: {t['bg']}; }}
QLabel#bubble {{ border-radius: 14px; padding: 9px 13px; font-size: 15px; border: 2px solid transparent; }}
QLabel#bubble[active="true"] {{ border: 2px solid {t['accent']}; }}
QLabel#sepLabel {{ color: {t['muted']}; font-weight: 700; font-size: 12px; }}
QFrame#sepline {{ background: {t['border']}; }}
QComboBox#lang {{ background: transparent; border: none; border-radius: 8px; padding: 8px 10px;
                  min-width: 96px; font-weight: 600; }}
QComboBox#lang:hover {{ background: {t['hover']}; }}
QComboBox#lang:disabled {{ color: {t['muted']}; }}
QPushButton#flat {{ background: transparent; border: none; border-radius: 8px; padding: 8px 12px; font-weight: 600; }}
QPushButton#flat:hover {{ background: {t['hover']}; }}
QPushButton#flat:disabled {{ color: {t['muted']}; }}
QFrame#vsep {{ background: {t['border']}; border: none; }}
QComboBox#lang QAbstractItemView {{ background: {t['bg']}; color: {t['text']};
                                     selection-background-color: {t['hover']}; selection-color: {t['text']}; }}
QLabel#bubble[who="mic"] {{ background: {t['me']}; color: {t['me_text']}; }}
QLabel#bubble[who="loop"] {{ background: {t['other']}; color: {t['other_text']}; }}
{"".join(f'QLabel#bubble[who="loop"][spk="{i}"] {{ background: {c}; color: {t["other_text"]}; }}' + chr(10) for i, c in enumerate(t["spk"]) if i)}
QLabel#bubble[partial="true"] {{ background: transparent; border: 1px dashed {t['muted']}; color: {t['muted']}; }}
QPushButton#namechip {{ background: transparent; border: 1px solid {t['border']}; border-radius: 9px;
                       padding: 1px 9px; color: {t['text']}; font-size: 11px; font-weight: 600; min-height: 16px; }}
QPushButton#namechip[auto="true"] {{ border-style: dashed; }}
QPushButton#namechip:hover {{ background: {t['border']}; }}
QPushButton#namechip:disabled {{ border-color: transparent; color: {t['muted']}; }}
QLabel#bubbleTime {{ color: {t['muted']}; font-size: 11px; }}
QLabel#note {{ color: {t['muted']}; font-size: 12px; }}
QFrame#miniFrame {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 14px; }}
QLabel#miniLast {{ color: {t['muted']}; }}
QPushButton#miniBtn {{ background: {t['danger']}; color: #FFFFFF; border: none; border-radius: 8px;
                       padding: 7px 14px; font-weight: 600; }}
QPushButton#miniGhost {{ background: transparent; border: 1px solid {t['border']}; border-radius: 8px;
                         padding: 7px 12px; }}
QSplitter::handle {{ background: {t['border']}; width: 3px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


class Bridge(QObject):
    utt = Signal(object)
    status = Signal(str)
    finished = Signal(object)
    started = Signal()
    subject_done = Signal(object, str)  # (pasta, erro ou "")
    speakers_done = Signal(object, int, str)  # (pasta, nº de pessoas, erro)
    reprocess_done = Signal(object, object, str)  # (pasta, resumo, erro)
    claude_ready = Signal(str, str, str, str, bool)  # (título, transcrição, pedido, resumo, abrir no app?)
    chat_delta = Signal(str, str)  # (pasta, texto novo da resposta do Claude)
    chat_done = Signal(str, str)   # (pasta, erro ou "")
    chat_usage = Signal(str, object)  # (pasta, tokens usados na resposta)
    fx_ready = Signal(object)  # cotação do dólar atualizada ({'rate', 'at', 'source'})
    cuda_progress = Signal(str, float)  # (texto, 0–1) do download das bibliotecas da GPU
    cuda_done = Signal(str)  # erro ("" = deu certo, "cancelado" = você cancelou)
    update_found = Signal(object, bool)  # (Release ou None, foi pedido por você?)
    update_progress = Signal(int, int)  # (bytes baixados, total)
    update_done = Signal(str, str)  # (caminho do instalador, erro ou "cancelado")


CLAUDE_ORANGE = "#D97757"  # laranja da marca Claude
LOGO = Path(__file__).parent / "assets" / "jotbrief.svg"


def app_icon() -> QIcon:
    return QIcon(str(LOGO))


def claude_icon(size: int = 64, kind: str = "web") -> QIcon:
    """Estrela de raios laranja (logo do Claude, desenhada). kind='web': com um globo; kind='app': dentro de uma janela."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    lens = [0.46, 0.34, 0.44, 0.30, 0.47, 0.35, 0.43, 0.31, 0.46, 0.33, 0.45, 0.32]
    if kind == "app":  # janela de aplicativo: moldura + barra de título, estrela menor embaixo
        frame = QPen(QColor("#6B7280"), size * 0.06)
        frame.setJoinStyle(Qt.RoundJoin)
        p.setPen(frame)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(size * 0.07, size * 0.10, size * 0.86, size * 0.80), size * 0.12, size * 0.12)
        p.drawLine(QPointF(size * 0.07, size * 0.30), QPointF(size * 0.93, size * 0.30))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#6B7280"))
        for k in range(3):
            p.drawEllipse(QPointF(size * (0.18 + 0.09 * k), size * 0.20), size * 0.024, size * 0.024)
        cx, cy, sc = size * 0.50, size * 0.62, 0.52
    else:
        cx, cy, sc = size * 0.46, size * 0.46, 0.92
    pen = QPen(QColor(CLAUDE_ORANGE), size * 0.12 * sc)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    for i, ln in enumerate(lens):
        a_ = math.radians(i * 30 - 90)
        p.drawLine(QPointF(cx + math.cos(a_) * size * 0.07 * sc, cy + math.sin(a_) * size * 0.07 * sc),
                   QPointF(cx + math.cos(a_) * size * ln * sc, cy + math.sin(a_) * size * ln * sc))
    if kind == "app":  # selo de prancheta: este botão é MANUAL (abre o projeto e você cola com Ctrl+V)
        bc, br = QPointF(size * 0.77, size * 0.77), size * 0.21
        p.setPen(QPen(QColor("#B45309"), size * 0.05))
        p.setBrush(QColor("#FEF3C7"))
        p.drawEllipse(bc, br, br)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#B45309"), size * 0.045))
        p.drawRoundedRect(QRectF(bc.x() - br * 0.45, bc.y() - br * 0.45, br * 0.9, br * 1.05), size * 0.02, size * 0.02)
        p.setBrush(QColor("#B45309"))
        p.drawRect(QRectF(bc.x() - br * 0.22, bc.y() - br * 0.58, br * 0.44, br * 0.28))
    if kind == "web":  # globo no canto inferior direito
        gc, gr = QPointF(size * 0.77, size * 0.77), size * 0.19
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#2F6FEB"), size * 0.06))
        p.drawEllipse(gc, gr, gr)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#2F6FEB"), size * 0.04))
        p.drawEllipse(gc, gr * 0.45, gr)
        p.drawLine(QPointF(gc.x() - gr, gc.y()), QPointF(gc.x() + gr, gc.y()))
    p.end()
    icon = QIcon()
    icon.addPixmap(pm, QIcon.Normal)
    faded = QPixmap(pm.size())
    faded.fill(Qt.transparent)
    q = QPainter(faded)
    q.setOpacity(0.85)  # desabilitado continua laranja (o padrão do Qt vira cinza)
    q.drawPixmap(0, 0, pm)
    q.end()
    icon.addPixmap(faded, QIcon.Disabled)
    return icon


def copy_icon(color: str, size: int = 64) -> QIcon:
    """Dois retângulos sobrepostos, traço firme (o glifo ⧉ da fonte é fraco)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), size * 0.075)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    s = size
    p.drawRoundedRect(QRectF(s * 0.34, s * 0.14, s * 0.50, s * 0.56), s * 0.08, s * 0.08)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.end()
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(s * 0.16, s * 0.30, s * 0.50, s * 0.56), s * 0.08, s * 0.08)
    p.end()
    return QIcon(pm)


def rec_icon(recording: bool, red: str, size: int = 64) -> QIcon:
    """Idle: disco branco. Gravando: quadrado vermelho de parar."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    if recording:
        p.setBrush(QColor(red))
        p.drawRoundedRect(QRectF(size * 0.28, size * 0.28, size * 0.44, size * 0.44), size * 0.07, size * 0.07)
    else:
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(size * 0.26, size * 0.26, size * 0.48, size * 0.48))
    p.end()
    return QIcon(pm)


def _discard(w: QWidget) -> None:
    """Remove um widget da tela na hora (some e sai da árvore) e libera a memória depois."""
    w.hide()
    w.setParent(None)
    w.deleteLater()


class _Opened(Exception):
    """Sinal interno: o link já foi aberto (pula o plano B)."""


def _repolish(w: QWidget):
    w.style().unpolish(w)
    w.style().polish(w)


def _clear_layout(lay) -> None:
    """Esvazia um layout (widgets ficam vivos) e descarta os sub-layouts."""
    while lay.count():
        item = lay.takeAt(0)
        sub = item.layout()
        if sub is not None:
            _clear_layout(sub)
            sub.deleteLater()


class FlowBar(QWidget):
    """Barra de boxes em linhas FIXAS (cada grupo é uma linha); se uma linha não couber, ela quebra em mais linhas."""

    def __init__(self, rows: list[list[QWidget]], margins=(20, 12, 20, 4), spacing=8):
        super().__init__()
        self.groups = [list(r) for r in rows]
        self.spacing = spacing
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(*margins)
        self.root.setSpacing(spacing)
        self._sig = None
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._arrange()

    def _items(self) -> list[QWidget]:
        return [w for g in self.groups for w in g]

    def _avail(self) -> int:
        m = self.root.contentsMargins()
        return self.width() - m.left() - m.right()

    def _pack(self, items: list[QWidget]) -> list[list[QWidget]]:
        """Distribui os boxes de um grupo em linhas que caibam na largura (esquerda → direita)."""
        if self.width() <= 0:
            return [items]
        rows, cur, used = [], [], 0
        for w in items:
            wd = w.sizeHint().width()
            if cur and used + self.spacing + wd > self._avail():
                rows.append(cur)
                cur, used = [], 0
            cur.append(w)
            used += wd + (self.spacing if len(cur) > 1 else 0)
        if cur:
            rows.append(cur)
        return rows

    def _arrange(self):
        rows = [r for g in self.groups for r in self._pack(g)]
        sig = tuple(len(r) for r in rows)
        if sig == self._sig:
            return
        self._sig = sig
        _clear_layout(self.root)
        for row in rows:
            h = QHBoxLayout()
            h.setSpacing(self.spacing)
            for w in row:
                h.addWidget(w)
            h.addStretch(1)
            self.root.addLayout(h)
        self.updateGeometry()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._arrange()

    def minimumSizeHint(self) -> QSize:
        # deixa a janela encolher: o mínimo é o maior box, não a soma de todos
        m = self.root.contentsMargins()
        widest = max((w.sizeHint().width() for w in self._items()), default=0)
        return QSize(widest + m.left() + m.right(), self.sizeHint().height())


class PlayerBox(QFrame):
    """Player em box: largo = 1 linha; médio = controles + volume em cima e barra embaixo; estreito = tudo empilhado."""

    def __init__(self, g1: QWidget, g2: QWidget, g3: QWidget):
        super().__init__(objectName="playerbox")
        self.g1, self.g2, self.g3 = g1, g2, g3
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(10, 8, 12, 8)
        self.root.setSpacing(6)
        self._mode = None
        self._arrange(0)

    def _arrange(self, mode: int):
        if mode == self._mode:
            return
        self._mode = mode
        _clear_layout(self.root)
        if mode == 0:
            h = QHBoxLayout()
            h.setSpacing(8)
            h.addWidget(self.g1)
            h.addWidget(self.g2, 1)
            h.addWidget(self.g3)
            self.root.addLayout(h)
        elif mode == 1:
            top = QHBoxLayout()
            top.addWidget(self.g1)
            top.addStretch(1)
            top.addWidget(self.g3)
            self.root.addLayout(top)
            self.root.addWidget(self.g2)
        else:
            self.root.addWidget(self.g1)
            self.root.addWidget(self.g2)
            self.root.addWidget(self.g3)
        self.updateGeometry()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        both = self.g1.sizeHint().width() + self.g3.sizeHint().width()
        if self.width() >= both + 260 + 40:
            self._arrange(0)
        elif self.width() >= both + 40:
            self._arrange(1)
        else:
            self._arrange(2)

    def minimumSizeHint(self) -> QSize:
        return QSize(max(self.g1.sizeHint().width(), self.g3.sizeHint().width(), 160) + 24, self.sizeHint().height())


class MeetingList(QListWidget):
    """Lista de reuniões que avisa quando muda de largura (para recalcular a altura das linhas)."""
    resized = Signal()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.resized.emit()


class MeetingRow(QWidget):
    """Linha da lista: título + contagem, com botão de excluir ao lado."""
    delete_clicked = Signal(str)

    def __init__(self, title: str, sub: str, path: str, deletable: bool = True):
        super().__init__()
        self.title, self.sub = title, sub
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 2, 2)
        self.lbl = QLabel()
        self.lbl.setTextFormat(Qt.RichText)
        self.lbl.setText(self._html(title, sub))
        self.lbl.setWordWrap(True)
        self.lbl.setStyleSheet("background: transparent;")
        self.lbl.setAttribute(Qt.WA_TransparentForMouseEvents)  # o clique seleciona a reunião
        btn = QPushButton("🗑", objectName="del")
        btn.setToolTip("Excluir reunião (vai para a Lixeira)")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.delete_clicked.emit(path))
        lay.addWidget(self.lbl, 1)
        if deletable:
            lay.addWidget(btn, 0, Qt.AlignTop)
        else:
            btn.deleteLater()
        self.setAttribute(Qt.WA_TranslucentBackground)

    @staticmethod
    def _html(title: str, sub: str) -> str:
        """'2026-10-02 | 10:30 | Assunto' → data e hora em negrito; contagem/tarefas numa linha cinza."""
        import re
        m = re.match(r"^(\d{4}-\d{2}-\d{2}) \| (\d{2}:\d{2}) \| (.*)$", title, re.S)
        head = (f"<b style='font-size:15px'>{_esc(m.group(1))} | {_esc(m.group(2))}</b> | {_esc(m.group(3))}"
                if m else _esc(title))
        return head + "<br><span style='color:#6B7280; font-size:12px'>" + _esc(sub).replace("\n", "<br>") + "</span>"

    def height_hint(self, width: int) -> QSize:
        fm = QFontMetrics(self.lbl.font())
        w = max(width, 120)
        lines = self.sub.count("\n") + 1  # contagem de falas + (às vezes) a tarefa em andamento
        h = fm.boundingRect(0, 0, w, 2000, Qt.TextWordWrap, self.title).height() + fm.height() * lines + 28
        return QSize(0, h)


def _speaker_index(speaker: str | None) -> str:
    """'Pessoa 3' → '2' (índice da cor da bolha); sem identificação → '0'."""
    try:
        return str((int(str(speaker).split()[-1]) - 1) % 5)
    except (ValueError, IndexError):
        return "0"


class BubbleList(QScrollArea):
    """Lista de bolhas estilo chat ('Eu' à direita, 'Reunião' à esquerda) que acompanha o áudio."""
    seek_requested = Signal(float)
    rename_requested = Signal(str)  # rótulo original: 'Pessoa 1', 'Eu' ou 'Reunião'
    play_part = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.host = QWidget()
        self.lay = QVBoxLayout(self.host)
        self.lay.setContentsMargins(20, 16, 20, 16)
        self.lay.setSpacing(10)
        self.lay.addStretch()
        self.setWidget(self.host)
        self.partials: dict[str, QWidget] = {}
        self.count = 0
        self.entries: list[dict] = []   # falas finais (para acompanhar o áudio)
        self.current: dict | None = None
        self.word_bg, self.word_fg = "#FFFFFF", "#1F2328"
        self.names: dict[str, str] = {}  # nomes dados às pessoas da reunião atual
        self.auto_names: set[str] = set()  # rótulos cujo nome veio do reconhecimento de voz
        # botão flutuante "rolar para o final": aparece quando você não está no fim da conversa
        self.btn_bottom = QPushButton("↓", self, objectName="tobottom")
        self.btn_bottom.setToolTip("Rolar para o final")
        self.btn_bottom.setCursor(Qt.PointingHandCursor)
        self.btn_bottom.clicked.connect(self.scroll_to_end)
        self.btn_bottom.hide()
        self.stick = True  # "seguir o final": enquanto você está no fim, cada fala nova rola a lista sozinha
        bar = self.verticalScrollBar()
        bar.valueChanged.connect(self._on_value)
        bar.rangeChanged.connect(self._on_range)

    def scroll_to_end(self):
        """Vai para o final e passa a acompanhar as falas novas."""
        self.stick = True
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())
        QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))  # de novo, depois do layout terminar
        self._update_bottom_btn()

    def _on_range(self, *_):
        if self.stick:  # o conteúdo cresceu: continua no fim
            bar = self.verticalScrollBar()
            bar.setValue(bar.maximum())
        self._update_bottom_btn()

    def _on_value(self, v: int):
        bar = self.verticalScrollBar()
        self.stick = v >= bar.maximum() - 40  # subiu → para de seguir; voltou ao fim → volta a seguir
        self._update_bottom_btn()

    def _update_bottom_btn(self, *_):
        bar = self.verticalScrollBar()
        show = bar.maximum() > 0 and bar.value() < bar.maximum() - 40
        self.btn_bottom.setVisible(show)
        if show:
            self.btn_bottom.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        sb = self.verticalScrollBar().width() if self.verticalScrollBar().isVisible() else 0
        self.btn_bottom.move(self.width() - self.btn_bottom.width() - 20 - sb,
                             self.height() - self.btn_bottom.height() - 16)

    def clear(self):
        while self.lay.count() > 1:
            w = self.lay.takeAt(0).widget()
            if w:
                _discard(w)
        self.partials.clear()
        self.entries.clear()
        self.current = None
        self.count = 0
        self.stick = True

    def _row(self, source: str, text: str, t0: float, partial: bool, speaker: str | None = None) -> QWidget:
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        col = QVBoxLayout()
        col.setSpacing(2)
        lbl = QLabel(text, objectName="bubble")
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(560)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setProperty("who", source)
        lbl.setProperty("partial", "true" if partial else "false")
        lbl.setProperty("spk", _speaker_index(speaker))
        orig = "Eu" if source == "mic" else (speaker or "Reunião")
        who = self.names.get(orig, orig)
        tm = QLabel(fmt_time(t0), objectName="bubbleTime")
        tm.setCursor(Qt.PointingHandCursor)
        tm.setToolTip("Ouvir a partir daqui")
        tm.mousePressEvent = lambda _e, t=t0: self.seek_requested.emit(t)
        meta = QHBoxLayout()  # [nome] 00:00:00 — o nome é um botão: clique para renomear
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(6)
        chip = QPushButton(who, objectName="namechip")
        is_auto = orig in self.auto_names
        chip.setProperty("auto", "true" if is_auto else "false")
        chip.setToolTip("Reconhecido pela voz. Clique para corrigir" if is_auto
                        else f"Clique para renomear \"{orig}\"")
        chip.setCursor(Qt.PointingHandCursor)
        chip.setEnabled(not partial)
        chip.clicked.connect(lambda _c=False, o=orig: self.rename_requested.emit(o))
        if source == "mic":
            meta.addStretch()
            meta.addWidget(chip)
            meta.addWidget(tm)
        else:
            meta.addWidget(chip)
            meta.addWidget(tm)
            meta.addStretch()
        col.addWidget(lbl)
        col.addLayout(meta)
        if source == "mic":
            rl.addStretch()
            rl.addLayout(col)
        else:
            rl.addLayout(col)
            rl.addStretch()
        row.lbl = lbl
        return row

    def _append(self, w: QWidget):
        self.lay.insertWidget(self.lay.count() - 1, w)
        self.count += 1
        if self.count > MAX_BUBBLES:
            old = self.lay.takeAt(0).widget()
            if old:
                if self.entries and self.entries[0]["row"] is old:
                    gone = self.entries.pop(0)
                    if self.current is gone:
                        self.current = None
                _discard(old)
            self.count -= 1

    def add_final(self, source: str, text: str, t0: float, rec: dict | None = None):
        self.drop_partial(source)
        row = self._row(source, text, t0, False, (rec or {}).get("speaker"))
        rec = rec or {"t0": t0, "t1": t0, "source": source, "text": text}
        self.entries.append({"rec": rec, "row": row, "label": row.lbl, "text": text,
                             "timings": word_timings(rec), "word": -2})
        self._append(row)

    def add_separator(self, label: str, start: float | None = None, end: float | None = None):
        """Separador entre partes da reunião; com botão de ouvir só aquela parte."""
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 12, 0, 6)
        l1, l2 = QFrame(objectName="sepline"), QFrame(objectName="sepline")
        for ln in (l1, l2):
            ln.setFixedHeight(1)
        hl.addWidget(l1, 1)
        hl.addWidget(QLabel(label, objectName="sepLabel"))
        if start is not None and end is not None:
            btn = QPushButton("▶ Ouvir parte", objectName="ghost")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda: self.play_part.emit(start, end))
            hl.addWidget(btn)
        hl.addWidget(l2, 1)
        self._append(row)

    def set_partial(self, source: str, text: str, t0: float):
        self.drop_partial(source)
        w = self._row(source, text, t0, True)
        self.partials[source] = w
        self._append(w)

    def drop_partial(self, source: str):
        w = self.partials.pop(source, None)
        if w is not None:
            self.lay.removeWidget(w)
            _discard(w)
            self.count -= 1

    def note(self, text: str):
        self.lay.insertWidget(self.lay.count() - 1, QLabel(text, objectName="note"))

    # ---- acompanhar o áudio (estilo letra de música) ----
    def follow(self, sec: float):
        cur = None
        for e in self.entries:
            r = e["rec"]
            if r["t0"] - 0.15 <= sec <= max(r["t1"], r["t0"]) + 0.35:
                cur = e
        if cur is not self.current:
            if self.current is not None:
                self._deactivate(self.current)
            self.current = cur
            if cur is not None:
                cur["label"].setProperty("active", True)
                _repolish(cur["label"])
                cur["word"] = -2
                self.ensureWidgetVisible(cur["row"], 0, 140)
        if cur is not None:
            idx = active_word(cur["timings"], sec)
            if idx != cur["word"]:
                cur["word"] = idx
                self._render_words(cur, idx)

    def _render_words(self, e: dict, idx: int):
        parts = []
        for i, (_a, _b, w) in enumerate(e["timings"]):
            if i == idx:
                parts.append(f'<span style="background-color:{self.word_bg}; color:{self.word_fg};">'
                             f'&nbsp;{_esc(w)}&nbsp;</span>')
            else:
                parts.append(_esc(w))
        e["label"].setTextFormat(Qt.RichText)
        e["label"].setText(" ".join(parts))

    def _deactivate(self, e: dict):
        e["label"].setProperty("active", False)
        _repolish(e["label"])
        e["label"].setTextFormat(Qt.PlainText)
        e["label"].setText(e["text"])
        e["word"] = -2

    def unfollow(self):
        if self.current is not None:
            self._deactivate(self.current)
            self.current = None


class MiniBar(QWidget):
    """Barra flutuante mostrada durante a gravação."""
    stop_clicked = Signal()
    expand_clicked = Signal()

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(420, 130)
        self._drag = None
        frame = QFrame(objectName="miniFrame")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addWidget(frame)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(16, 12, 16, 12)
        top = QHBoxLayout()
        self.dot = QLabel("●")
        self.timer = QLabel("00:00:00", objectName="timer")
        top.addWidget(self.dot)
        top.addWidget(self.timer)
        top.addStretch()
        b_exp = QPushButton("⤢", objectName="miniGhost")
        b_exp.setToolTip("Expandir")
        b_stop = QPushButton("■  Parar", objectName="miniBtn")
        b_exp.clicked.connect(self.expand_clicked)
        b_stop.clicked.connect(self.stop_clicked)
        top.addWidget(b_exp)
        top.addWidget(b_stop)
        self.last = QLabel("Aguardando fala...", objectName="miniLast")
        self._last_text = "Aguardando fala..."
        fl.addLayout(top)
        fl.addWidget(self.last)

    def set_last(self, text: str):
        self._last_text = text
        fm = QFontMetrics(self.last.font())
        self.last.setText(fm.elidedText(text, Qt.ElideRight, self.width() - 60))

    def set_time(self, s: str):
        self.timer.setText(s)

    def mousePressEvent(self, e):
        self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None


class PromptDialog(QDialog):
    """Lista de pedidos prontos (como os atalhos do Claude): o escolhido vira a 1ª coisa do chat."""

    def __init__(self, prompts: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("O que você quer gerar?")
        self.setModal(True)
        self.choice: dict | None = None
        self.setStyleSheet(parent.styleSheet() if parent else "")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        lay.addWidget(QLabel("O que você quer gerar com esta reunião?", objectName="brand"))
        grid = QGridLayout()
        grid.setSpacing(10)
        items = list(prompts) + [TRANSCRIPT_ONLY]
        for i, pr in enumerate(items):
            b = QPushButton(f"{pr['icone']}   {pr['nome']}", objectName="chip")
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(pr["pedido"] or "Leva só a transcrição, sem um pedido")
            b.clicked.connect(lambda _c=False, x=pr: self._pick(x))
            grid.addWidget(b, i // 2, i % 2)
        lay.addLayout(grid)
        row = QHBoxLayout()
        edit = QPushButton("Editar opções…", objectName="ghost")
        edit.setToolTip(f"Abre {PROMPTS_PATH} para acrescentar ou mudar os pedidos")
        edit.clicked.connect(lambda: (PROMPTS_PATH.exists() or load_prompts(), os.startfile(PROMPTS_PATH)))
        cancel = QPushButton("Cancelar", objectName="ghost")
        cancel.clicked.connect(self.reject)
        row.addWidget(edit)
        row.addStretch()
        row.addWidget(cancel)
        lay.addLayout(row)
        self.setMinimumWidth(620)

    def _pick(self, pr: dict):
        self.choice = pr
        self.accept()


def _people_combo(people: list[str], current: str = "") -> QComboBox:
    """Lista dos nomes já usados, mas editável: escolha um existente ou digite um novo."""
    box = QComboBox()
    box.setEditable(True)
    box.setInsertPolicy(QComboBox.NoInsert)
    box.addItems(people)
    box.setCurrentIndex(-1)
    box.setEditText(current)
    box.lineEdit().setPlaceholderText("Escolha da lista ou digite um novo nome")
    return box


class PersonDialog(QDialog):
    """Nome de uma pessoa: escolha entre os que você já usou ou digite um novo."""

    def __init__(self, label: str, current: str, people: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quem é esta pessoa?")
        self.setModal(True)
        self.setStyleSheet(parent.styleSheet() if parent else "")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(QLabel(f"Nome para “{label}”", objectName="brand"))
        hint = QLabel("Escolha alguém da lista (pessoas que você já nomeou) ou digite um novo nome. "
                      "Vazio volta ao rótulo original.", objectName="note")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.combo = _people_combo(people, current)
        lay.addWidget(self.combo)
        row = QHBoxLayout()
        self.btn_forget = QPushButton("Esquecer este nome", objectName="ghost")
        self.btn_forget.setToolTip("Tira o nome da lista e apaga a voz aprendida dele (não muda as reuniões "
                                   "que já usam o nome)")
        self.btn_forget.clicked.connect(self._forget)
        cancel = QPushButton("Cancelar", objectName="ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salvar", objectName="playbtn")
        save.setStyleSheet("QPushButton#playbtn { min-width: 90px; max-width: 90px; border-radius: 12px; }")
        save.clicked.connect(self.accept)
        row.addWidget(self.btn_forget)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)
        self.setMinimumWidth(420)
        self.combo.setFocus()

    def _forget(self):
        name = self.combo.currentText().strip()
        i = self.combo.findText(name, Qt.MatchFixedString)
        if name and i >= 0:
            forget_person(name)
            try:
                from .voices import forget_voice
                forget_voice(name)
            except Exception:  # noqa: BLE001 - o cadastro de vozes é opcional
                pass
            self.combo.removeItem(i)
            self.combo.setEditText("")

    def name(self) -> str:
        return self.combo.currentText()


class NamesDialog(QDialog):
    """Um campo por pessoa da reunião: 'Pessoa 1' → nome (da lista de nomes já usados ou um novo)."""

    def __init__(self, labels: list[str], current: dict[str, str], parent=None, people: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Dar nome às pessoas")
        self.setModal(True)
        self.setStyleSheet(parent.styleSheet() if parent else "")
        self.labels = labels
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        lay.addWidget(QLabel("Quem é cada pessoa?", objectName="brand"))
        hint = QLabel("Escolha alguém que você já nomeou ou digite um novo nome. O nome aparece na tela e na "
                      "transcrição copiada para o Claude. Vazio mantém o rótulo automático.", objectName="note")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        form = QFormLayout()
        form.setSpacing(8)
        self.edits: dict[str, QComboBox] = {}
        for lb in labels:
            e = _people_combo(people or [], current.get(lb, ""))
            self.edits[lb] = e
            form.addRow(QLabel(lb), e)
        lay.addLayout(form)
        row = QHBoxLayout()
        cancel = QPushButton("Cancelar", objectName="ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salvar", objectName="playbtn")
        save.setStyleSheet("QPushButton#playbtn { min-width: 90px; max-width: 90px; border-radius: 12px; }")
        save.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)
        self.setMinimumWidth(420)
        first = next(iter(self.edits.values()))
        first.setFocus()

    def result_names(self) -> dict[str, str]:
        return {lb: e.currentText() for lb, e in self.edits.items()}


class ReprocessDialog(QDialog):
    """Opções ao reprocessar: idioma, identificar falantes e quantas pessoas."""

    def __init__(self, language: str, has_voice_models: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reprocessar reunião")
        self.setModal(True)
        self.setStyleSheet(parent.styleSheet() if parent else "")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        lay.addWidget(QLabel("Transcrever o áudio de novo", objectName="brand"))
        hint = QLabel("Refaz a transcrição a partir do áudio gravado, com o idioma escolhido e os filtros atuais "
                      "(descarta legendas-fantasma, outros alfabetos e ecos). Sua transcrição atual fica salva "
                      "em um arquivo de backup na pasta da reunião. Os nomes que você deu às pessoas são mantidos.",
                      objectName="note")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        form = QFormLayout()
        form.setSpacing(8)
        self.lang = QComboBox()
        for label, code in (("Português", "pt"), ("English", "en"), ("Automático (pt/en)", "auto")):
            self.lang.addItem(label, code)
        self.lang.setCurrentIndex(max(self.lang.findData(language), 0))
        form.addRow(QLabel("Idioma"), self.lang)
        self.ident = QCheckBox("Identificar falantes depois")
        self.ident.setChecked(has_voice_models)
        form.addRow(QLabel(""), self.ident)
        self.people = QComboBox()
        self.people.addItems(["Automático", "1 pessoa", "2 pessoas", "3 pessoas", "4 pessoas", "5 pessoas", "6 pessoas"])
        form.addRow(QLabel("Pessoas"), self.people)
        self.people.setEnabled(self.ident.isChecked())
        self.ident.toggled.connect(self.people.setEnabled)
        lay.addLayout(form)
        row = QHBoxLayout()
        cancel = QPushButton("Cancelar", objectName="ghost")
        cancel.clicked.connect(self.reject)
        go = QPushButton("Reprocessar", objectName="playbtn")
        go.setStyleSheet("QPushButton#playbtn { min-width: 120px; max-width: 120px; border-radius: 12px; }")
        go.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(go)
        lay.addLayout(row)
        self.setMinimumWidth(420)

    def values(self) -> tuple[str, bool, int]:
        return self.lang.currentData(), self.ident.isChecked(), self.people.currentIndex()


class _ChatInput(QTextEdit):
    """Caixa de pergunta: Enter envia, Shift+Enter quebra a linha."""
    submit = Signal()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.submit.emit()
            return
        super().keyPressEvent(e)


class ApiKeyDialog(QDialog):
    """Cola a chave da API do Claude; confere na Anthropic antes de guardar (só neste computador)."""

    def __init__(self, parent=None, has_key: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Chave da API do Claude")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        intro = QLabel("O chat e o assunto das reuniões usam a API da Anthropic, com a sua chave.<br>"
                       f'Crie uma em <a href="{API_KEYS_URL}">platform.claude.com/settings/keys</a> (botão “Create Key”) e cole abaixo. '
                       "Ela fica só neste computador (%APPDATA%\\jotbrief) e nunca é enviada a ninguém além da Anthropic.")
        intro.setTextFormat(Qt.RichText)
        intro.setOpenExternalLinks(True)  # abre no navegador padrão
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setPlaceholderText("sk-ant-… (já há uma chave guardada; cole outra para trocar)" if has_key else "sk-ant-…")
        lay.addWidget(self.edit)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancelar", objectName="ghost")
        self.ok = QPushButton("Testar e salvar", objectName="ghost")
        cancel.clicked.connect(self.reject)
        self.ok.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self.model = Config.load().claude_model

    def _save(self):
        from .chat import test_key
        from .config import save_api_key
        key = self.edit.text().strip()
        if len(key) < 20 or any(c.isspace() for c in key):
            self.msg.setText("A chave parece incompleta: cole a chave inteira, sem espaços.")
            return
        self.ok.setEnabled(False)
        self.msg.setText("Conferindo na Anthropic…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            QApplication.processEvents()
            err = test_key(key, self.model)
        finally:
            QApplication.restoreOverrideCursor()
        self.ok.setEnabled(True)
        if err:
            self.msg.setText(err)
            return
        save_api_key(key)
        self.accept()


class VersionsDialog(QDialog):
    """Histórico de versões (mesmo formato do JB Ladder): 'YYYY.MM.DD.HH.mm' = data e hora do commit, em Brasília."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from .versao import atual, entradas
        self.setWindowTitle("Versões")
        self.resize(560, 460)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Versão atual: {atual()}", objectName="brand"))
        note = QLabel("A versão é a data e a hora (Brasília) da última alteração publicada: ano.mês.dia.hora.minuto.", objectName="note")
        note.setWordWrap(True)
        lay.addWidget(note)
        view = QTextBrowser()
        items = entradas()
        view.setHtml("".join(f"<p><b>{_esc(e['versao'])}</b><br>{_esc(e['titulo'])}</p>" for e in items)
                     or "<p>O histórico não está disponível nesta versão.</p>")
        lay.addWidget(view, 1)
        row = QHBoxLayout()
        check = QPushButton("Verificar atualizações", objectName="ghost")
        check.clicked.connect(lambda: parent.check_update(manual=True) if hasattr(parent, "check_update") else None)
        close = QPushButton("Fechar", objectName="ghost")
        close.clicked.connect(self.accept)
        row.addWidget(check)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)


class ChatPanel(QWidget):
    """Coluna do chat com o Claude: botões prontos (resumo detalhado…) + conversa livre sobre a reunião."""
    ask = Signal(str, str)   # (texto mostrado, pedido enviado ao Claude)
    stop_requested = Signal()
    clear_requested = Signal()

    def __init__(self):
        super().__init__()
        from .chat import EFFORTS, QUICK
        self.setObjectName("chatpanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 12, 12, 10)
        lay.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("Claude", objectName="brand")
        self.sub = QLabel("sobre esta reunião", objectName="note")
        self.btn_key = QPushButton("🔑", objectName="icon")
        self.btn_key.setToolTip("Chave da API do Claude (necessária para o chat e o assunto das reuniões)")
        self.btn_key.setCursor(Qt.PointingHandCursor)
        self.btn_clear = QPushButton("🗑", objectName="icon")
        self.btn_clear.setToolTip("Limpar a conversa desta reunião")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_requested)
        head.addWidget(title)
        head.addWidget(self.sub, 1)
        head.addWidget(self.btn_key)
        head.addWidget(self.btn_clear)
        lay.addLayout(head)
        info = QHBoxLayout()
        self.model_box = QComboBox()
        self.model_box.setToolTip("Modelo do Claude usado no app (chat e assunto das reuniões)")
        for label, value in MODELS:
            self.model_box.addItem(label, value)
        self.effort = QComboBox()
        self.effort.setToolTip("Esforço do Claude: mais alto pensa mais, responde mais devagar e gasta mais tokens")
        for label, value in EFFORTS:
            self.effort.addItem(label, value)
        info.addWidget(self.model_box, 1)
        info.addWidget(QLabel("esforço", objectName="note"))
        info.addWidget(self.effort)
        lay.addLayout(info)
        self.usage_lbl = QLabel("", objectName="note")
        self.usage_lbl.setWordWrap(True)
        lay.addWidget(self.usage_lbl)

        grid = QGridLayout()
        grid.setSpacing(6)
        self.quick: list[QPushButton] = []
        for i, (label, prompt) in enumerate(QUICK):
            b = QPushButton(label, objectName="ghost")
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(prompt)
            b.clicked.connect(lambda _=False, l=label, p=prompt: self.ask.emit(l, p))
            if i == len(QUICK) - 1 and len(QUICK) % 2:  # número ímpar de botões: o último ocupa a linha toda
                grid.addWidget(b, i // 2, 0, 1, 2)
            else:
                grid.addWidget(b, i // 2, i % 2)
            self.quick.append(b)
        lay.addLayout(grid)

        self.view = QTextBrowser(objectName="chatview")
        self.view.setOpenExternalLinks(True)
        self.view.setPlaceholderText("Use um botão acima ou escreva uma pergunta sobre a reunião.\n\n"
                                     "Durante a gravação, o Claude lê a transcrição até agora.")
        lay.addWidget(self.view, 1)

        self.status = QLabel("", objectName="status")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        self.input = _ChatInput(objectName="chatinput")
        self.input.setPlaceholderText("Pergunte algo sobre a reunião…\nEnter envia · Shift+Enter quebra a linha")
        self.input.setFixedHeight(74)
        self.input.setAcceptRichText(False)
        self.input.submit.connect(self._send)
        self.btn_send = QPushButton("↑", objectName="playbtn")
        self.btn_send.setToolTip("Enviar")
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self._send_or_stop)
        row.addWidget(self.input, 1)
        row.addWidget(self.btn_send, 0, Qt.AlignBottom)
        lay.addLayout(row)
        self._busy = False
        self._messages: list[dict] = []
        self._render = QTimer(self)
        self._render.setSingleShot(True)
        self._render.timeout.connect(self._paint)

    # ---- entrada ----
    def _send(self):
        text = self.input.toPlainText().strip()
        if text and not self._busy:
            self.input.clear()
            self.ask.emit(text, text)

    def _send_or_stop(self):
        if self._busy:
            self.stop_requested.emit()
        else:
            self._send()

    def set_busy(self, busy: bool, note: str = ""):
        self._busy = busy
        self.btn_send.setText("■" if busy else "↑")
        self.btn_send.setToolTip("Parar a resposta" if busy else "Enviar")
        for b in self.quick:
            b.setEnabled(not busy)
        self.status.setText(note)

    # ---- conversa ----
    def set_messages(self, messages: list[dict]):
        self._messages = messages
        self._paint()
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def refresh(self):
        """Redesenha (com limite de frequência, para o texto que chega aos poucos)."""
        if not self._render.isActive():
            self._render.start(120)

    def _paint(self):
        bar = self.view.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 24
        parts = []
        for m in self._messages:
            if m["role"] == "user":
                parts.append("**Você:** " + (m.get("shown") or m["content"]).replace("\n", "  \n"))
            else:
                parts.append("**Claude:**\n\n" + m["content"])
        self.view.setMarkdown("\n\n---\n\n".join(parts))
        if at_end:
            bar.setValue(bar.maximum())


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("JB - Jot Brief")
        self.setWindowIcon(app_icon())
        self.resize(1120, 700)
        self.setMinimumSize(460, 380)
        self.cfg = Config.load()
        self.session = None
        self.folder: Path | None = None
        self.elapsed = 0
        self._expanded: set[str] | None = None  # dias abertos na lista; None = ainda não decidiu (abre só o último dia)
        self.draft = False  # "Nova reunião" clicada: mostra a linha na lista até a gravação começar
        self.busy: dict[tuple, str] = {}  # (pasta, tarefa) -> "identificando falantes…": aparece na lista

        self.b = Bridge()
        self._meet_srv = self._start_meet_bridge()
        self.b.utt.connect(self.on_utt)
        self.b.status.connect(lambda m: self.lbl.setText(m))
        self.b.finished.connect(self.on_finished)
        self.b.started.connect(self.on_started)
        self.b.subject_done.connect(self.on_subject)
        self.b.speakers_done.connect(self.on_speakers)
        self.b.reprocess_done.connect(self.on_reprocessed)
        self.b.claude_ready.connect(self.on_claude_ready)
        self.b.chat_delta.connect(self.on_chat_delta)
        self.b.chat_done.connect(self.on_chat_done)
        self.b.chat_usage.connect(self.on_chat_usage)
        from . import fx
        self.fx = fx.cached()  # última cotação guardada; a atualização vem em segundo plano
        self.b.fx_ready.connect(self.on_fx)
        self.b.cuda_progress.connect(self._on_cuda_progress)
        self.b.cuda_done.connect(self._on_cuda_done)
        self.b.update_found.connect(self.on_update_found)
        self.b.update_progress.connect(self._on_update_progress)
        self.b.update_done.connect(self._on_update_done)
        if self.cfg.update_check:
            QTimer.singleShot(6000, self.check_update)
        QTimer.singleShot(800, self._first_run_key)
        QTimer.singleShot(1500, self._offer_cuda)
        threading.Thread(target=lambda: self.b.fx_ready.emit(fx.refresh()), daemon=True).start()
        self.chats: dict[str, list] = {}  # pasta -> mensagens do chat (também salvas em chat.json)
        self._chat_busy = False
        self._chat_stop = threading.Event()

        self.mini = MiniBar()
        self.mini.stop_clicked.connect(self.toggle)
        self.mini.expand_clicked.connect(self.expand)

        self._vol_save = QTimer(self)
        self._vol_save.setSingleShot(True)
        self._vol_save.timeout.connect(self.cfg.save)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self.on_tick)

        # sidebar
        self.search = QLineEdit(placeholderText="Buscar reuniões")
        self.search.textChanged.connect(lambda _: self.refresh_list(keep=True))
        self.listw = MeetingList()
        self.listw.currentItemChanged.connect(self.on_pick)
        self._row_timer = QTimer(self)
        self._row_timer.setSingleShot(True)
        self._row_timer.timeout.connect(self.relayout_rows)
        self.listw.resized.connect(lambda: self._row_timer.start(40))
        self.listw.setWordWrap(True)
        self.listw.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.listw.setTextElideMode(Qt.ElideNone)
        side = QWidget(objectName="sidebar")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 14, 10, 10)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(QSize(34, 34)))
        name = QLabel("JB - Jot Brief", objectName="brand")
        brand.addWidget(logo)
        brand.addWidget(name)
        brand.addStretch()
        sl.addLayout(brand)
        sl.addSpacing(6)
        sl.addWidget(self.search)
        sl.addWidget(self.listw)

        # barra de ações (ícones)
        def icon(txt, tip, fn):
            b = QPushButton(txt, objectName="icon")
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            return b

        self.btn_folder = icon("📁", "Abrir pasta", self.open_folder)
        self.btn_copy = icon("", "Copiar transcrição", self.copy_transcript)
        self.btn_copy.setIconSize(QSize(22, 22))
        self.btn_speakers = icon("👥", "Identificar falantes (separa as vozes da reunião: Pessoa 1, 2…)", self.identify_speakers)
        self.btn_reprocess = icon("🔄", "Reprocessar: transcreve o áudio de novo com o idioma e os filtros atuais",
                                  self.reprocess)
        self.btn_names = icon("✏", "Dar nome às pessoas (Pessoa 1 → nome). O nome vale na tela e na exportação",
                              self.edit_names)
        self.btn_claude = icon("", "Levar para o Claude no NAVEGADOR (abre uma conversa nova no projeto)",
                               lambda: self.to_claude(False))
        self.btn_claude.setIcon(claude_icon(kind="web"))
        self.btn_claude.setIconSize(QSize(24, 24))
        self.btn_claude_app = icon("", "MANUAL: abre o projeto no app Claude do Windows e copia o texto. Clique em “Nova sessão” e cole (Ctrl+V)",
                                   lambda: self.to_claude(True))
        self.btn_claude_app.setIcon(claude_icon(kind="app"))
        self.btn_claude_app.setIconSize(QSize(24, 24))
        self.btn_proj = icon("⚙", "Definir projeto do Claude", self.set_project)
        self.btn_theme = icon("◐", "Alternar tema claro/escuro", self.toggle_theme)
        self.btn_chat = icon("💬", "Chat com o Claude sobre a reunião (mostra/oculta a coluna)", lambda: None)
        self.btn_chat.setCheckable(True)
        self.btn_chat.setChecked(self.cfg.chat_open)
        self.btn_chat.toggled.connect(self.toggle_chat)
        self.btn_float = icon("🎈", "Modo balão: ao gravar, vira uma barra flutuante no topo da tela", lambda: None)
        self.btn_float.setCheckable(True)
        self.btn_float.setChecked(self.cfg.floating)
        self.btn_float.toggled.connect(self.toggle_float)
        for w in (self.btn_folder, self.btn_copy, self.btn_claude, self.btn_claude_app, self.btn_speakers, self.btn_names,
                  self.btn_reprocess):
            w.setEnabled(False)

        self.timer_lbl = QLabel("00:00:00", objectName="timer")
        self.rec = QPushButton("", objectName="rec")
        self.rec.setIconSize(QSize(34, 34))
        self.rec.setToolTip("Gravar (continua a reunião selecionada)")
        self.rec.setCursor(Qt.PointingHandCursor)
        self.rec.clicked.connect(self.toggle)
        self.pulse = QTimer(self)  # pulso: alterna a borda do botão enquanto grava
        self.pulse.timeout.connect(self._beat)

        self.btn_new = QPushButton("＋  Nova reunião", objectName="flat")
        self.btn_new.setToolTip("Começar uma reunião nova (a próxima gravação não continua a selecionada)")
        self.btn_new.setCursor(Qt.PointingHandCursor)
        self.btn_new.clicked.connect(self.new_meeting)
        self.target_lbl = QLabel("", objectName="note")
        self.target_lbl.setWordWrap(True)
        self.target_lbl.setContentsMargins(20, 0, 20, 2)

        # esquerda: gravar + tempo, nova reunião + idioma | direita: ações e tema (quebra de linha se apertar)
        recbox = QFrame(objectName="recbox")  # gravar + tempo, num box cinza
        rbl = QHBoxLayout(recbox)
        rbl.setContentsMargins(8, 6, 16, 6)
        rbl.setSpacing(10)
        rbl.addWidget(self.rec)
        rbl.addWidget(self.timer_lbl)
        self.lang = QComboBox(objectName="lang")
        self.lang.setToolTip("Idioma da call (o Whisper transcreve neste idioma)")
        for label, code in (("Português", "pt"), ("English", "en"), ("Automático", "auto")):
            self.lang.addItem(label, code)
        self.lang.setCurrentIndex(max(self.lang.findData(self.cfg.language), 0))
        self.lang.currentIndexChanged.connect(self.on_lang)
        sessbox = QFrame(objectName="sessbox")  # nova reunião + idioma, num box cinza
        sbl = QHBoxLayout(sessbox)
        sbl.setContentsMargins(6, 4, 6, 4)
        sbl.setSpacing(4)
        sbl.addWidget(self.btn_new)
        vsep = QFrame(objectName="vsep")
        vsep.setFixedSize(1, 24)
        sbl.addWidget(vsep)
        sbl.addWidget(self.lang)
        claudebox = QFrame(objectName="claudebox")  # botões do Claude juntos: navegador, app e projeto (configuração)
        cbl = QHBoxLayout(claudebox)
        cbl.setContentsMargins(6, 4, 6, 4)
        cbl.setSpacing(2)
        for w in (self.btn_claude, self.btn_proj, self.btn_claude_app):  # navegador, pasta (projeto) e, por último, o app
            cbl.addWidget(w)
        def tool_box(*widgets):  # cada grupo de ações num box cinza próprio
            f = QFrame(objectName="toolbox")
            lay = QHBoxLayout(f)
            lay.setContentsMargins(6, 4, 6, 4)
            lay.setSpacing(2)
            for w in widgets:
                lay.addWidget(w)
            return f
        people_box = tool_box(self.btn_speakers, self.btn_names)  # falantes + nomes juntos
        reprocess_box = tool_box(self.btn_reprocess)
        folder_box = tool_box(self.btn_folder)
        copy_box = tool_box(self.btn_copy)
        chat_box = tool_box(self.btn_chat)
        box2 = QFrame(objectName="toolbox2")  # balão + tema, destacados num box separado
        bl2 = QHBoxLayout(box2)
        bl2.setContentsMargins(6, 4, 6, 4)
        bl2.setSpacing(2)
        bl2.addWidget(self.btn_float)
        bl2.addWidget(self.btn_theme)
        bar = FlowBar([[recbox, sessbox], [claudebox, people_box, reprocess_box, folder_box, copy_box, chat_box, box2]])  # linha 1: gravar; linha 2: Claude primeiro

        # player de áudio: play/pause, ±10 s, barra de posição
        self._stop_at = None  # ms; ao tocar só uma parte, pausa aqui
        self.audio_out = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_out)
        self.player.positionChanged.connect(self.on_pos)
        self.player.durationChanged.connect(self.on_duration)
        self.player.playbackStateChanged.connect(self.on_play_state)
        self.btn_back = QPushButton("⏪ 10", objectName="ghost")
        self.btn_play = QPushButton("▶", objectName="playbtn")
        self.btn_fwd = QPushButton("10 ⏩", objectName="ghost")
        self.btn_back.setToolTip("Voltar 10 segundos")
        self.btn_fwd.setToolTip("Avançar 10 segundos")
        self.btn_play.setToolTip("Ouvir / pausar")
        self.btn_back.clicked.connect(lambda: self.skip(-10))
        self.btn_fwd.clicked.connect(lambda: self.skip(10))
        self.btn_play.clicked.connect(self.toggle_play)
        self.seek_bar = QSlider(Qt.Horizontal)
        self.seek_bar.sliderMoved.connect(self.seek_manual)
        self.play_time = QLabel("00:00 / 00:00", objectName="note")
        # volume: mudo + barra 0–100 %
        self.btn_mute = QPushButton("🔊", objectName="icon")
        self.btn_mute.setToolTip("Silenciar / ativar som")
        self.btn_mute.clicked.connect(self.toggle_mute)
        self.vol_bar = QSlider(Qt.Horizontal)
        self.vol_bar.setRange(0, 100)
        self.vol_bar.setFixedWidth(80)
        self.vol_bar.setToolTip("Volume")
        self.vol_bar.setValue(int(self.cfg.volume))
        self.audio_out.setVolume(self.cfg.volume / 100)
        self.vol_bar.valueChanged.connect(self.set_volume)
        self.vol_lbl = QLabel(f"{self.cfg.volume}%", objectName="note")
        self.vol_lbl.setFixedWidth(34)
        g1, g2, g3 = QWidget(), QWidget(), QWidget()
        h1 = QHBoxLayout(g1)
        h1.setContentsMargins(0, 0, 0, 0)
        for w in (self.btn_back, self.btn_play, self.btn_fwd):
            h1.addWidget(w)
        h2 = QHBoxLayout(g2)
        h2.setContentsMargins(0, 0, 0, 0)
        h2.addWidget(self.seek_bar, 1)
        h2.addWidget(self.play_time)
        h3 = QHBoxLayout(g3)
        h3.setContentsMargins(0, 0, 0, 0)
        h3.addWidget(self.btn_mute)
        h3.addWidget(self.vol_bar)
        h3.addWidget(self.vol_lbl)
        self.player_row = QWidget()  # contêiner com margens; o box fica dentro
        outer = QHBoxLayout(self.player_row)
        outer.setContentsMargins(20, 2, 20, 8)
        outer.addWidget(PlayerBox(g1, g2, g3))
        self.player_row.hide()

        self.bubbles = BubbleList()
        self.bubbles.seek_requested.connect(self.seek_to)
        self.bubbles.play_part.connect(self.play_range)
        self.bubbles.rename_requested.connect(self.rename_person)
        self.lbl = QLabel("", objectName="status")
        self.lbl.setWordWrap(True)
        self.lbl.setContentsMargins(20, 0, 20, 8)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(bar)
        rl.addWidget(self.target_lbl)
        rl.addWidget(self.player_row)
        rl.addWidget(self.bubbles)
        rl.addWidget(self.lbl)
        lgpd = QLabel("Aviso LGPD: gravar e transcrever reuniões exige o consentimento dos participantes. "
                      "Avise-os antes de iniciar.", objectName="footer")
        lgpd.setWordWrap(True)
        from .versao import atual
        ver = QPushButton(f"Versão {atual()}", objectName="verlink")
        ver.setCursor(Qt.PointingHandCursor)
        ver.setToolTip("Ver o histórico de versões")
        ver.clicked.connect(lambda: VersionsDialog(self).exec())
        self.btn_update = QPushButton("", objectName="updatelink")
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setToolTip("Baixa e instala a versão nova (o app fecha e reabre sozinho)")
        self.btn_update.clicked.connect(self.start_update)
        self.btn_update.hide()
        self.pending_update = None
        foot = QWidget(objectName="footerbar")
        foot.setAttribute(Qt.WA_StyledBackground, True)
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(lgpd, 1)
        fl.addWidget(self.btn_update, 0)
        fl.addWidget(ver, 0)

        self.chat = ChatPanel()
        self.chat.ask.connect(self.chat_ask)
        self.chat.stop_requested.connect(self._chat_stop.set)
        self.chat.clear_requested.connect(self.chat_clear)
        self.chat.btn_key.clicked.connect(self.ask_api_key)
        self.chat.effort.currentIndexChanged.connect(self.on_chat_effort)
        self.chat.model_box.currentIndexChanged.connect(self.on_chat_model)
        self.chat.setMinimumWidth(300)
        self.chat.setVisible(self.cfg.chat_open)
        split = QSplitter()
        split.addWidget(side)
        split.addWidget(right)
        split.addWidget(self.chat)
        split.setStretchFactor(1, 1)
        split.setSizes([340, 780, 380])
        side.setMinimumWidth(110)
        right.setMinimumWidth(340)
        split.setCollapsible(0, True)
        split.setCollapsible(1, False)
        split.setCollapsible(2, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(split, 1)
        lay.addWidget(foot)  # rodapé separado, na largura toda da janela

        self.apply_theme()
        self.refresh_list()
        self.update_target()

    # ---- tema ----
    def apply_theme(self):
        css = make_style(THEMES.get(self.cfg.theme, THEMES["escuro"]))
        self.setStyleSheet(css)
        self.mini.setStyleSheet(css)
        t = THEMES.get(self.cfg.theme, THEMES["escuro"])
        self.mini.dot.setStyleSheet(f"color: {t['danger']};")
        self.btn_copy.setIcon(copy_icon(t["text"]))
        self.bubbles.word_bg, self.bubbles.word_fg = t["bg"], t["text"]
        self._update_rec_icon()

    def _update_rec_icon(self):
        t = THEMES.get(self.cfg.theme, THEMES["escuro"])
        self.rec.setIcon(rec_icon(bool(self.rec.property("recording")), t["danger"]))

    def on_lang(self, _i: int):
        self.cfg.language = self.lang.currentData()
        self.cfg.save()

    def toggle_theme(self):
        self.cfg.theme = "claro" if self.cfg.theme == "escuro" else "escuro"
        self.cfg.save()
        self.apply_theme()

    # ---- lista de reuniões ----
    def _root(self) -> Path:
        return Path(self.cfg.output_dir).resolve()

    def refresh_list(self, select: Path | None = None, keep: bool = False):
        current = select or (self.folder if keep else None)
        q = self.search.text().strip().lower()
        root = self._root()
        dirs = [d for d in root.glob("*") if (d / "transcricao.jsonl").exists()] if root.exists() else []
        if self.session is not None and self.session.dir is not None:
            current = current or self.session.dir  # durante a gravação a reunião nova já aparece, selecionada
        if q:
            dirs = [d for d in dirs if q in call_title(d.name, read_subject(d) or "").lower()
                    or q in self._peek(d)]
        self.listw.blockSignals(True)
        self.listw.clear()
        target = None
        if self.draft and self.session is None and not q:  # "Nova reunião" no topo, antes mesmo de gravar
            it = QListWidgetItem()
            it.setData(Qt.UserRole, "")
            self.listw.addItem(it)
            row = MeetingRow("Nova reunião", "aguardando a gravação…", "", deletable=False)
            self.listw.setItemWidget(it, row)
            it.setSizeHint(row.height_hint(max(self.listw.viewport().width() - 75, 100)))
            target = it
        groups = group_by_day(dirs)
        if self._expanded is None and groups:
            self._expanded = {self._day_key(groups[0][0])}  # no início só o último dia com transcrição fica aberto
        for label, items in groups:
            key = self._day_key(label)
            if current and current in items and self._expanded is not None:
                self._expanded.add(key)  # a reunião selecionada/gravando nunca fica escondida
            is_open = bool(q) or key in (self._expanded or set())  # busca mostra tudo que casou
            hdr = QListWidgetItem()
            hdr.setFlags(Qt.NoItemFlags)
            self.listw.addItem(hdr)
            day = QPushButton(f"{'▾' if is_open else '▸'}  {label.upper()}   ({len(items)})", objectName="dayHdr")
            day.setProperty("today", label.lower().startswith("hoje"))
            day.setCursor(Qt.PointingHandCursor)
            day.setToolTip("Recolher" if is_open else "Expandir")
            day.clicked.connect(lambda _=False, k=key: self._toggle_day(k))
            self.listw.setItemWidget(hdr, day)
            hdr.setSizeHint(QSize(0, 38))
            if not is_open:
                continue
            for d in items:
                n = sum(1 for _ in open(d / "transcricao.jsonl", encoding="utf-8"))
                title = call_title(d.name, read_subject(d) or "")
                it = QListWidgetItem()
                it.setToolTip(title)
                it.setData(Qt.UserRole, str(d))
                self.listw.addItem(it)
                sub = f"{n} {'fala' if n == 1 else 'falas'}"
                if self.session is not None and self.session.dir == d:
                    sub = "● gravando… · " + sub
                work = ", ".join(v for (f, _k), v in self.busy.items() if f == d)
                if work:
                    sub += f"\n⏳ {work}"
                row = MeetingRow(title, sub, str(d))
                row.delete_clicked.connect(self.delete_meeting)
                self.listw.setItemWidget(it, row)
                it.setSizeHint(row.height_hint(max(self.listw.viewport().width() - 75, 100)))  # depois do widget
                if current and d == current and not (self.draft and self.session is None):
                    target = it
        if target:
            self.listw.setCurrentItem(target)
        self.listw.blockSignals(False)
        if select and target:
            self.on_pick(target)

    @staticmethod
    def _day_key(label: str) -> str:
        """'Hoje · 2026-10-02' → '2026-10-02' (a chave não muda quando 'Hoje' vira 'Ontem')."""
        return label.rsplit("· ", 1)[-1].strip()

    def _toggle_day(self, key: str):
        opened = self._expanded if self._expanded is not None else set()
        opened.symmetric_difference_update({key})
        self._expanded = opened
        QTimer.singleShot(0, lambda: self.refresh_list(keep=True))

    def relayout_rows(self):
        """Recalcula a altura de cada reunião da lista conforme a largura atual."""
        w = max(self.listw.viewport().width() - 75, 100)
        for i in range(self.listw.count()):
            it = self.listw.item(i)
            row = self.listw.itemWidget(it)
            if isinstance(row, MeetingRow):
                it.setSizeHint(row.height_hint(w))

    def _start_meet_bridge(self):
        """Recebe da extensão do Chrome quem está falando no Meet e guarda com o tempo da gravação."""
        from . import meet_bridge, meet_names

        last: dict[tuple, bool] = {}  # (pasta, nome) -> último estado guardado: a extensão repete o estado a cada 2 s
        self._meet_events: list[dict] = []  # eventos da gravação em curso, para nomear as falas ao vivo
        self._meet_dir = None

        lock = threading.Lock()

        def sink(name: str, on: bool) -> bool:
            s = self.session
            if s is None or s.dir is None:
                return False
            with lock:  # o servidor atende vários avisos ao mesmo tempo
                key = (str(s.dir), meet_names.clean_name(name))
                if last.get(key) == on:
                    return True  # nada mudou
                last[key] = on
                t = s.now()
                if self._meet_dir != s.dir:
                    self._meet_dir, self._meet_events = s.dir, []
                self._meet_events.append({"t": t, "name": meet_names.clean_name(name), "on": on})
                meet_names.append_event(s.dir, t, name, on)
            return True

        return meet_bridge.start(sink, lambda: self.session is not None)

    def _live_speaker(self, t0: float, t1: float) -> str | None:
        from .meet_names import live_speaker
        s = self.session
        if s is None or s.dir != self._meet_dir:
            return None
        return live_speaker(list(self._meet_events), t0, t1)

    # ---- chat com o Claude ----
    def toggle_chat(self, on: bool):
        self.cfg.chat_open = on
        self.cfg.save()
        self.chat.setVisible(on)
        if on and not self.isMaximized() and self.width() < 1150:
            self.resize(self.width() + 380, self.height())  # abre a coluna sem espremer o resto
        self._show_chat()

    def _chat_dir(self) -> Path | None:
        return self.session.dir if self.session is not None and self.session.dir else self.folder

    def _show_chat(self):
        """Mostra no painel a conversa da reunião atual (a que está gravando ou a selecionada)."""
        d = self._chat_dir()
        if d is None:
            self.chat.sub.setText("escolha ou grave uma reunião")
            self.chat.set_messages([])
            self._update_chat_info()
            return
        self.chat.sub.setText(call_title(d.name, read_subject(d) or ""))
        from .chat import load_chat
        self.chat.set_messages(self.chats.setdefault(str(d), load_chat(d)))
        self._update_chat_info()

    def chat_ask(self, shown: str, prompt: str):
        from .chat import build_system, stream_reply
        d = self._chat_dir()
        if d is None or self._chat_busy:
            self.chat.status.setText("Escolha uma reunião ou comece a gravar para conversar com o Claude.")
            return
        recs = clean_records(read_jsonl(d / "transcricao.jsonl")) if (d / "transcricao.jsonl").exists() else []
        if not recs:
            self.chat.status.setText("Ainda não há transcrição desta reunião.")
            return
        names = read_names(d)
        title = call_title(d.name, read_subject(d) or "")
        system = build_system(title, transcript_meta(recs, names),
                              render_transcript(recs, d.name, read_parts(d), names), self.session is not None)
        msgs = self.chats.setdefault(str(d), [])
        history = [dict(m) for m in msgs] + [{"role": "user", "content": prompt}]
        msgs.append({"role": "user", "content": prompt, "shown": shown})
        msgs.append({"role": "assistant", "content": ""})
        self._chat_busy = True
        self._chat_stop.clear()
        self.chat.set_messages(msgs)
        self.chat.set_busy(True, "Claude está lendo a transcrição e respondendo…")
        key = str(d)

        def work():
            try:
                _text, usage = stream_reply(self.cfg, system, history, lambda t: self.b.chat_delta.emit(key, t),
                                            self._chat_stop)
                self.b.chat_usage.emit(key, usage)
                self.b.chat_done.emit(key, "")
            except Exception as e:  # noqa: BLE001
                from .chat import friendly_error
                self.b.chat_done.emit(key, friendly_error(e))
        threading.Thread(target=work, daemon=True).start()

    def on_chat_delta(self, folder: str, text: str):
        msgs = self.chats.get(folder)
        if not msgs or msgs[-1]["role"] != "assistant":
            return
        msgs[-1]["content"] += text
        d = self._chat_dir()
        if d is not None and str(d) == folder:
            self.chat.refresh()

    def on_chat_usage(self, folder: str, usage: dict):
        msgs = self.chats.get(folder)
        if msgs and msgs[-1]["role"] == "assistant" and usage:
            msgs[-1]["usage"] = {**usage, "model": self.cfg.claude_model, "effort": self.cfg.chat_effort}

    def _update_chat_info(self):
        """Modelo, esforço e consumo (última resposta + total da reunião) no topo do painel."""
        from .chat import fmt_usage, sum_usage, total_cost
        model = self.cfg.claude_model
        i = self.chat.model_box.findData(model)
        if i < 0:  # modelo escolhido à mão no config.toml: aparece na lista também
            self.chat.model_box.addItem(model, model)
            i = self.chat.model_box.findData(model)
        j = self.chat.effort.findData(self.cfg.chat_effort)
        for box, idx in ((self.chat.model_box, i), (self.chat.effort, max(j, 0))):
            box.blockSignals(True)
            box.setCurrentIndex(idx)
            box.blockSignals(False)
        ok = supports_effort(model)
        self.chat.effort.setEnabled(ok)
        self.chat.effort.setToolTip("Esforço do Claude: mais alto pensa mais, responde mais devagar e gasta mais tokens"
                                    if ok else "Este modelo não tem o ajuste de esforço")
        d = self._chat_dir()
        msgs = self.chats.get(str(d), []) if d is not None else []
        last = next((m["usage"] for m in reversed(msgs) if m.get("usage")), None)
        if not last:
            self.chat.usage_lbl.setText("Consumo: nada nesta reunião ainda." + self._fx_line())
            return
        last_model = last.get("model", model)
        brl = self._brl()
        self.chat.usage_lbl.setText(
            fmt_usage(last_model, last, "Última resposta", None, brl) + f"  [{last_model.replace('claude-', '')}"
            + (f", esforço {last['effort']}" if last.get("effort") and supports_effort(last_model) else "") + "]\n"
            + fmt_usage(model, sum_usage(msgs), "Total da reunião", total_cost(msgs), self._brl()) + self._fx_line())

    def ask_api_key(self):
        if ApiKeyDialog(self, bool(os.environ.get("ANTHROPIC_API_KEY"))).exec() == QDialog.Accepted:
            self.chat.status.setText("Chave salva e conferida.")
            self.lbl.setText("Chave da API salva. O chat e o assunto das reuniões já podem usar o Claude.")

    def _first_run_key(self):
        """App instalado sem chave: pede logo na abertura (dá para fechar e usar o app sem o chat)."""
        from .runtime import is_frozen
        if is_frozen() and not os.environ.get("ANTHROPIC_API_KEY"):
            self.ask_api_key()

    # ---- atualização do app ----
    def check_update(self, manual: bool = False):
        """Pergunta ao GitHub qual é a versão mais nova (em segundo plano; sem internet, só ignora)."""
        def work():
            from . import update
            try:
                self.b.update_found.emit(update.latest(), manual)
            except Exception:  # noqa: BLE001
                self.b.update_found.emit(None, manual)
        threading.Thread(target=work, daemon=True).start()

    def on_update_found(self, rel, manual: bool):
        from . import update
        from .versao import atual
        if rel is not None and update.is_newer(rel.version, atual()):
            self.pending_update = rel
            self.btn_update.setText(f"⬆ Atualizar para {rel.version}")
            self.btn_update.show()
            if manual:
                self.lbl.setText(f"Há uma versão nova: {rel.version}. Use o botão “Atualizar” no rodapé.")
        elif manual:
            QMessageBox.information(self, "Atualizações",
                                    f"Você já está na versão mais recente ({atual()})." if rel is not None
                                    else "Não deu para consultar as atualizações agora (sem internet?).")

    def start_update(self):
        from . import update
        from .runtime import is_frozen
        rel = self.pending_update
        if rel is None:
            return
        if self.session is not None:
            QMessageBox.information(self, "Atualizar", "Pare a gravação antes de atualizar o app.")
            return
        if not is_frozen():  # código-fonte: não há instalador a executar
            QDesktopServices.openUrl(QUrl(rel.page))
            return
        box = QMessageBox(QMessageBox.Question, "Atualizar o app",
                          f"Atualizar para a versão {rel.version}?\n\nO app baixa o instalador ({rel.size / 1e6:.0f} MB), fecha, "
                          "atualiza e reabre sozinho. Suas reuniões e configurações ficam como estão.", QMessageBox.NoButton, self)
        yes = box.addButton("Atualizar agora", QMessageBox.AcceptRole)
        box.addButton("Depois", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not yes:
            return
        self._update_cancel = threading.Event()
        self._update_dlg = QProgressDialog("Baixando o instalador…", "Cancelar", 0, 100, self)
        self._update_dlg.setWindowTitle("Atualizando")
        self._update_dlg.setMinimumDuration(0)
        self._update_dlg.setAutoClose(False)
        self._update_dlg.canceled.connect(self._update_cancel.set)
        self._update_dlg.show()

        def work():
            import tempfile
            try:
                path = update.download(rel, Path(tempfile.gettempdir()) / "jotbrief-update",
                                       self.b.update_progress.emit, self._update_cancel.is_set)
                self.b.update_done.emit(str(path), "")
            except update.Cancelled:
                self.b.update_done.emit("", "cancelado")
            except Exception as e:  # noqa: BLE001
                self.b.update_done.emit("", str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_update_progress(self, got: int, total: int):
        dlg = getattr(self, "_update_dlg", None)
        if dlg is not None and total:
            dlg.setValue(min(int(got * 100 / total), 99))
            dlg.setLabelText(f"Baixando o instalador… {got / 1e6:.0f} de {total / 1e6:.0f} MB")

    def _on_update_done(self, path: str, err: str):
        from . import update
        dlg = getattr(self, "_update_dlg", None)
        if dlg is not None:
            dlg.close()
            self._update_dlg = None
        if err == "cancelado":
            self.lbl.setText("Atualização cancelada.")
        elif err:
            QMessageBox.warning(self, "Atualizar", f"Não deu para atualizar: {err}")
        else:
            self.lbl.setText("Instalando a versão nova… o app vai fechar e reabrir.")
            update.launch_installer(Path(path))
            QTimer.singleShot(400, QApplication.quit)

    # ---- aceleração por GPU (app instalado) ----
    def _offer_cuda(self):
        """App instalado + placa NVIDIA + sem as bibliotecas CUDA: oferece baixar (~1,3 GB, uma vez) para transcrever bem mais rápido."""
        from . import cuda_setup
        from .runtime import is_frozen
        if not is_frozen() or self.cfg.cuda_offer == "never" or not cuda_setup.gpu_present() or cuda_setup.cuda_ready():
            return
        box = QMessageBox(QMessageBox.Question, "Aceleração por placa NVIDIA",
                          "Seu computador tem uma placa NVIDIA. Para transcrever muito mais rápido, o app precisa baixar "
                          "bibliotecas da NVIDIA (cerca de 1,3 GB, uma única vez, direto do PyPI).\n\n"
                          "Sem isso o app funciona, só que mais devagar (usa o processador).", QMessageBox.NoButton, self)
        yes = box.addButton("Baixar agora", QMessageBox.AcceptRole)
        box.addButton("Depois", QMessageBox.RejectRole)
        never = box.addButton("Não perguntar mais", QMessageBox.DestructiveRole)
        box.exec()
        if box.clickedButton() is never:
            self.cfg.cuda_offer = "never"
            self.cfg.save()
        elif box.clickedButton() is yes:
            self._cuda_cancel = threading.Event()
            self._cuda_dlg = QProgressDialog("Preparando…", "Cancelar", 0, 100, self)
            self._cuda_dlg.setWindowTitle("Baixando a aceleração por GPU")
            self._cuda_dlg.setMinimumDuration(0)
            self._cuda_dlg.setAutoClose(False)
            self._cuda_dlg.canceled.connect(self._cuda_cancel.set)
            self._cuda_dlg.show()

            def work():
                from . import cuda_setup as cs
                try:
                    cs.install(self.b.cuda_progress.emit, self._cuda_cancel.is_set)
                    self.b.cuda_done.emit("")
                except cs.Cancelled:
                    self.b.cuda_done.emit("cancelado")
                except Exception as e:  # noqa: BLE001
                    self.b.cuda_done.emit(str(e))
            threading.Thread(target=work, daemon=True).start()

    def _on_cuda_progress(self, text: str, frac: float):
        dlg = getattr(self, "_cuda_dlg", None)
        if dlg is not None:
            dlg.setLabelText(text)
            dlg.setValue(int(frac * 100))

    def _on_cuda_done(self, err: str):
        dlg = getattr(self, "_cuda_dlg", None)
        if dlg is not None:
            dlg.close()
            self._cuda_dlg = None
        if not err:
            self.lbl.setText("Aceleração por GPU instalada. A próxima gravação já usa a placa NVIDIA.")
        elif err == "cancelado":
            self.lbl.setText("Download cancelado. O app segue usando o processador (pergunto de novo na próxima abertura).")
        else:
            QMessageBox.warning(self, "Aceleração por GPU", f"Não deu para baixar: {err}\n\nO app segue usando o processador.")

    def _brl(self) -> float | None:
        return float(self.fx["rate"]) if getattr(self, "fx", None) else None

    def _fx_line(self) -> str:
        """Linha da cotação usada na conversão: 'Dólar: R$ 5,2322 (AwesomeAPI, hoje 10:56)'."""
        fx = getattr(self, "fx", None)
        if not fx:
            return "\nSem cotação do dólar (sem internet): custo só em US$."
        from datetime import datetime
        when = datetime.fromtimestamp(float(fx.get("at", 0)))
        day = "hoje" if when.date() == datetime.now().date() else when.strftime("%d/%m")
        return f"\nDólar: R$ {float(fx['rate']):.4f} ({fx.get('source', '?')}, {day} {when:%H:%M})".replace(".", ",", 1)

    def on_fx(self, data):
        if data:
            self.fx = data
            self._update_chat_info()

    def on_chat_model(self, _i: int):
        self.cfg.claude_model = self.chat.model_box.currentData()
        self.cfg.save()
        self._update_chat_info()

    def on_chat_effort(self, _i: int):
        self.cfg.chat_effort = self.chat.effort.currentData()
        self.cfg.save()
        self._update_chat_info()

    def on_chat_done(self, folder: str, err: str):
        from .chat import save_chat
        msgs = self.chats.get(folder) or []
        if msgs and msgs[-1]["role"] == "assistant" and not msgs[-1]["content"].strip():
            if err:
                msgs[-1]["content"] = f"⚠ Não deu para responder: {err}" + (
                    "\n\nClique no 🔑 (topo desta coluna) para colar a chave." if "ANTHROPIC_API_KEY" in err else "")
            else:
                msgs.pop()  # parou antes de qualquer texto: tira a resposta vazia
                if msgs and msgs[-1]["role"] == "user":
                    msgs.pop()
        elif err and msgs:
            msgs[-1]["content"] += f"\n\n⚠ A resposta foi interrompida: {err}"
        self._chat_busy = False
        self.chat.set_busy(False)
        try:
            save_chat(Path(folder), [m for m in msgs if not m["content"].startswith("⚠ Não deu")])
        except OSError:
            pass
        d = self._chat_dir()
        if d is not None and str(d) == folder:
            self.chat.set_messages(msgs)
        self._update_chat_info()

    def chat_clear(self):
        d = self._chat_dir()
        if d is None or self._chat_busy:
            return
        self.chats[str(d)] = []
        (d / "chat.json").unlink(missing_ok=True)
        self._show_chat()

    def _fetch_guests(self, folder: Path, duration: float):
        """Busca na agenda os convidados da reunião (uma vez por reunião) e guarda em meta.json como sugestão de nomes."""
        url = self.cfg.calendar_ics_url.strip()
        start = parse_stamp(folder.name)
        if not url or not start or "convidados" in read_meta(folder) or self.session is not None:
            return

        def work():
            try:
                from .agenda import attendees_for, fetch_ics
                guests = attendees_for(fetch_ics(url), start, duration or 1800.0)
                write_meta(folder, convidados=guests)
                if guests:
                    self.b.status.emit(f"Convidados da agenda: {', '.join(guests[:6])}"
                                       + ("…" if len(guests) > 6 else "") + " (aparecem na lista de nomes).")
            except Exception:  # noqa: BLE001 - agenda fora do ar não pode atrapalhar; tenta de novo na próxima vez
                pass
        threading.Thread(target=work, daemon=True).start()

    def _name_choices(self, folder: Path) -> list[str]:
        """Nomes para escolher: convidados da agenda primeiro, depois as pessoas já cadastradas."""
        seen, out = set(), []
        for n in list(read_meta(folder).get("convidados") or []) + load_people(self._root()):
            if n.strip() and n.lower() not in seen:
                seen.add(n.lower())
                out.append(n)
        return out

    def _learn_voice(self, folder: Path, label: str, name: str):
        """Guarda a voz de quem você acabou de nomear, para reconhecer sozinho nas próximas reuniões."""
        from .voices import learnable_label
        if not name.strip() or not learnable_label(label):
            return

        def work():
            try:
                from .voices import learn_from_meeting
                secs = learn_from_meeting(folder, label, " ".join(name.split()))
                if secs > 0:
                    self.b.status.emit(f"Voz de “{name.strip()}” aprendida ({secs:.0f} s de fala): "
                                       "será reconhecida nas próximas reuniões.")
            except Exception:  # noqa: BLE001 - aprender a voz nunca pode atrapalhar o nome
                pass
        threading.Thread(target=work, daemon=True).start()

    def rename_person(self, label: str):
        """Renomeia uma pessoa direto pela bolha (botão ✏ ao lado do nome)."""
        if not self.folder:
            return
        if self.session is not None:
            self.lbl.setText("Pare a gravação para renomear as pessoas.")
            return
        folder = self.folder
        current = read_names(folder)
        dlg = PersonDialog(label, current.get(label, ""), self._name_choices(folder), self)
        if dlg.exec() != QDialog.Accepted:
            return
        name = dlg.name()
        current[label] = name
        write_names(folder, current)
        mark_manual(folder, [label])
        remember(name)
        self._learn_voice(folder, label, name)
        recs = read_jsonl(folder / "transcricao.jsonl")
        names = read_names(folder)
        (folder / "transcricao.md").write_text(
            render_markdown(recs, f"Transcrição {folder.name}", folder.name, read_parts(folder), names),
            encoding="utf-8")
        bar = self.bubbles.verticalScrollBar()
        pos = bar.value()
        self.load_folder(folder)
        QTimer.singleShot(80, lambda: bar.setValue(pos))  # continua onde você estava
        self.lbl.setText(f"\"{label}\" agora é \"{names.get(label, label)}\".")

    def reprocess(self):
        """Transcreve o áudio da reunião selecionada de novo (em segundo plano)."""
        if not self.folder or self.session is not None:
            return
        if not (self.folder / "audio.wav").exists():
            self.lbl.setText("Esta reunião não tem áudio para reprocessar.")
            return
        from . import speakers as _sp
        dlg = ReprocessDialog(self.cfg.language, _sp.has_model(), self)
        if dlg.exec() != QDialog.Accepted:
            return
        lang, ident, people = dlg.values()
        cfg = dataclasses.replace(self.cfg, language=lang, num_speakers=people)
        folder = self.folder
        self.btn_reprocess.setEnabled(False)
        self.rec.setEnabled(False)
        self.lbl.setText("Reprocessando…")
        self._busy(folder, "reprocess", "reprocessando a transcrição…")

        def work():
            from .reprocess import reprocess
            try:
                res = reprocess(folder, cfg, progress=self.b.status.emit, identify=ident)
                self.b.reprocess_done.emit(folder, res, "")
            except Exception as e:  # noqa: BLE001
                self.b.reprocess_done.emit(folder, {}, str(e))
        threading.Thread(target=work, daemon=True).start()

    def on_reprocessed(self, folder: Path, res: dict, err: str):
        self._busy(folder, "reprocess", None)
        self.btn_reprocess.setEnabled(self.folder is not None)
        self.rec.setEnabled(self.session is None)
        if err:
            self.lbl.setText(f"Não deu para reprocessar: {err}")
            return
        extra = f", {res.get('pessoas')} pessoa(s) identificada(s)" if res.get("pessoas") else ""
        if res.get("erro_falantes"):
            extra = f" (falantes não identificados: {res['erro_falantes']})"
        self.lbl.setText(f"Reprocessado: {res.get('falas', 0)} falas{extra}. Backup: {res.get('backup', '')}")
        self.refresh_list(select=None, keep=True)
        if self.folder == folder and self.session is None:
            self.load_folder(folder)

    def edit_names(self):
        """Dá nome às pessoas da reunião; vale na tela, na transcrição copiada e no arquivo .md."""
        if not self.folder or self.session is not None:
            return
        folder = self.folder
        recs = read_jsonl(folder / "transcricao.jsonl")
        labels = speaker_labels(recs)
        if not labels:
            return
        dlg = NamesDialog(labels, read_names(folder), self, self._name_choices(folder))
        if dlg.exec() != QDialog.Accepted:
            return
        before = read_names(folder)
        new = dlg.result_names()
        write_names(folder, new)
        mark_manual(folder, list(new))
        for _label, _nm in new.items():
            remember(_nm)
            if _nm.strip() and _nm.strip() != before.get(_label):
                self._learn_voice(folder, _label, _nm)
        names = read_names(folder)
        (folder / "transcricao.md").write_text(
            render_markdown(recs, f"Transcrição {folder.name}", folder.name, read_parts(folder), names),
            encoding="utf-8")
        self.load_folder(folder)
        self.lbl.setText("Nomes salvos: valem na tela e na transcrição copiada.")

    def delete_meeting(self, path: str):
        folder = Path(path)
        if self.session is not None and self.session.dir is not None and self.session.dir.resolve() == folder.resolve():
            QMessageBox.information(self, "Gravando", "Pare a gravação antes de excluir esta reunião.")
            return
        title = call_title(folder.name, read_subject(folder) or "")
        box = QMessageBox(QMessageBox.Warning, "Excluir reunião",
                          f"Excluir a reunião\\n{title}?\\n\\nA pasta inteira (áudio e transcrição) "
                          "vai para a Lixeira do Windows.", QMessageBox.NoButton, self)
        yes = box.addButton("Excluir", QMessageBox.DestructiveRole)
        box.addButton("Cancelar", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not yes:
            return
        try:
            from .session import release_logs
            release_logs(folder)  # app.log aberto impede a Lixeira de mover a pasta
            from send2trash import send2trash
            send2trash(str(folder))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Não foi possível excluir", str(e))
            return
        if self.folder == folder:
            self.new_meeting()
        self.refresh_list(keep=True)
        self.lbl.setText("Reunião enviada para a Lixeira.")

    @staticmethod
    def _peek(d: Path) -> str:
        try:
            return (d / "transcricao.jsonl").read_text(encoding="utf-8").lower()
        except OSError:
            return ""

    def on_pick(self, item, _prev=None):
        if item is None or self.session is not None or item.data(Qt.UserRole) is None:
            return
        if item.data(Qt.UserRole) == "":
            return  # linha "Nova reunião"
        self.load_folder(Path(item.data(Qt.UserRole)))
        if self.draft:  # escolheu outra reunião: a linha "Nova reunião" some
            self.draft = False
            QTimer.singleShot(0, lambda: self.refresh_list(keep=True))

    def load_folder(self, folder: Path):
        self.folder = folder
        self.setup_player(folder)
        self.bubbles.clear()
        self.bubbles.names = read_names(folder)
        self.bubbles.auto_names = set(read_auto_names(folder))
        recs = clean_records(read_jsonl(folder / "transcricao.jsonl"))
        try:
            import soundfile as sf
            dur = sf.info(str(folder / "audio.wav")).duration
        except Exception:  # noqa: BLE001 - sem áudio
            dur = 0.0
        items = build_items(recs, read_parts(folder), dur)
        if len(items) > MAX_BUBBLES:
            self.bubbles.note(f"Mostrando os últimos {MAX_BUBBLES} de {len(items)} itens "
                              "(a transcrição completa está no arquivo).")
            items = items[-MAX_BUBBLES:]
        for it in items:
            if it[0] == "sep":
                self.bubbles.add_separator(it[2], it[3], it[4])
            else:
                r = it[1]
                self.bubbles.add_final(r["source"], r["text"], r["t0"], r)
        QTimer.singleShot(50, lambda: self.bubbles.verticalScrollBar().setValue(0))
        self._fetch_guests(folder, dur)
        self._show_chat()
        for w in (self.btn_folder, self.btn_copy, self.btn_claude, self.btn_claude_app, self.btn_speakers, self.btn_names,
                  self.btn_reprocess):
            w.setEnabled(True)
        self.lbl.setText(str(folder))
        self.timer_lbl.setText("00:00:00")
        self.update_target()

    # ---- player ----
    @staticmethod
    def _mmss(ms: int) -> str:
        s = max(int(ms // 1000), 0)
        return f"{s // 3600:d}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"

    def setup_player(self, folder: Path):
        self.stop_player()
        try:
            wav = playable_wav(folder)
        except Exception as e:  # noqa: BLE001
            wav = None
            self.lbl.setText(f"Áudio indisponível: {e}")
        if wav is None:
            return
        self.player.setSource(QUrl.fromLocalFile(str(wav)))
        self.seek_bar.setValue(0)
        self.play_time.setText("00:00 / 00:00")
        self.player_row.show()

    def stop_player(self):
        self._stop_at = None
        self.bubbles.unfollow()
        self.player.stop()
        self.player.setSource(QUrl())
        self.player_row.hide()

    def toggle_play(self):
        if self.session is not None:
            return  # não toca enquanto grava (o som entraria na gravação)
        self._stop_at = None
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def play_range(self, start: float, end: float):
        """Ouve só uma parte da reunião (do início ao fim dela)."""
        if self.session is None and self.player_row.isVisible():
            self._stop_at = int(end * 1000)
            self.player.setPosition(int(start * 1000))
            self.player.play()

    def seek_manual(self, ms: int):
        self._stop_at = None
        self.player.setPosition(ms)

    def skip(self, seconds: int):
        if self.session is None:
            self._stop_at = None
            self.player.setPosition(max(0, min(self.player.position() + seconds * 1000, self.player.duration())))

    def seek_to(self, seconds: float):
        if self.session is None and self.player_row.isVisible():
            self._stop_at = None
            self.player.setPosition(int(max(seconds - 1, 0) * 1000))
            self.player.play()

    def set_volume(self, v: int):
        self.audio_out.setVolume(v / 100)
        self.vol_lbl.setText(f"{v}%")
        self.btn_mute.setText("🔇" if v == 0 else "🔉" if v < 50 else "🔊")
        self.cfg.volume = v
        self._vol_save.start(600)  # salva a config só depois de parar de mexer

    def toggle_mute(self):
        if self.vol_bar.value() > 0:
            self._last_vol = self.vol_bar.value()
            self.vol_bar.setValue(0)
        else:
            self.vol_bar.setValue(getattr(self, "_last_vol", 100) or 100)

    def on_duration(self, ms: int):
        self.seek_bar.setRange(0, ms)
        self.play_time.setText(f"{self._mmss(self.player.position())} / {self._mmss(ms)}")

    def on_pos(self, ms: int):
        if not self.seek_bar.isSliderDown():
            self.seek_bar.setValue(ms)
        self.play_time.setText(f"{self._mmss(ms)} / {self._mmss(self.player.duration())}")
        if self._stop_at is not None and ms >= self._stop_at:
            self._stop_at = None
            self.player.pause()
        self.bubbles.follow(ms / 1000)

    def on_play_state(self, state):
        self.btn_play.setText("⏸" if state == QMediaPlayer.PlayingState else "▶")

    def _busy(self, folder: Path, kind: str, text: str | None):
        """Marca/desmarca uma tarefa em segundo plano da reunião: aparece na lista e abaixo dos botões."""
        if text:
            self.busy[(folder, kind)] = text
        else:
            self.busy.pop((folder, kind), None)
        self.refresh_list(keep=True)
        self.update_target(recording=self.session is not None)

    def update_target(self, recording: bool = False):
        d = self.session.dir if (recording and self.session) else self.folder
        if d is None:
            self.target_lbl.setText("Nova reunião — a próxima gravação cria uma reunião nova.")
            return
        title = call_title(d.name, read_subject(d) or "")
        work = ", ".join(v for (f, _k), v in self.busy.items() if f == d)
        self.target_lbl.setText(("Gravando em: " if recording else "Gravar continua em: ") + title
                                + (f"   ·   ⏳ {work}" if work else ""))

    def new_meeting(self):
        """Deixa nenhuma reunião selecionada: a próxima gravação cria uma nova."""
        if self.session is not None:
            return
        self.folder = None
        self.bubbles.names = {}
        self.bubbles.auto_names = set()
        self.stop_player()
        self.listw.blockSignals(True)
        self.listw.clearSelection()
        self.listw.setCurrentItem(None)
        self.listw.blockSignals(False)
        self.bubbles.clear()
        for w in (self.btn_folder, self.btn_copy, self.btn_claude, self.btn_claude_app, self.btn_speakers, self.btn_names,
                  self.btn_reprocess):
            w.setEnabled(False)
        self.timer_lbl.setText("00:00:00")
        self.lbl.setText("")
        self.update_target()
        self.draft = True
        self.refresh_list()
        self._show_chat()

    # ---- ações ----
    def open_folder(self):
        if self.folder:
            os.startfile(self.folder)  # noqa: S606 (Windows)

    def _full_text(self) -> tuple[str, str]:
        """(uma fala por linha com data e hora, 'Duração | Participantes')."""
        recs = read_jsonl(self.folder / "transcricao.jsonl")
        names = read_names(self.folder)
        return (render_transcript(recs, self.folder.name, read_parts(self.folder), names),
                transcript_meta(recs, names))

    def copy_transcript(self):
        if self.folder:
            text, meta = self._full_text()
            title = call_title(self.folder.name, read_subject(self.folder) or "")
            QApplication.clipboard().setText(build_message("", title, text, meta))
            self.lbl.setText("Transcrição copiada para a área de transferência.")

    def to_claude(self, desktop: bool = False):
        """Garante o assunto da call e abre uma conversa nova no projeto (navegador ou app Claude do Windows)."""
        if not self.folder:
            return
        if self.cfg.ask_in_app:  # modo antigo: escolhe o pedido aqui no app
            dlg = PromptDialog(load_prompts(), self)
            if dlg.exec() != QDialog.Accepted or dlg.choice is None:
                return
            pedido = dlg.choice["pedido"]
        else:  # padrão: a skill jb-transcricao, no Claude, pergunta o que gerar
            from .skill import skill_request
            pedido = skill_request(self.cfg.skill_name)
        folder = self.folder
        text, meta = self._full_text()
        self.btn_claude.setEnabled(False)
        self.btn_claude_app.setEnabled(False)
        self.lbl.setText("Gerando o assunto da call...")

        def work():
            from .summarize import generate_subject
            try:
                subject = generate_subject(folder, self.cfg)
                err = ""
            except Exception as e:  # noqa: BLE001
                subject, err = "Sem assunto", str(e)
            self.b.subject_done.emit(folder, err)
            self.b.claude_ready.emit(call_title(folder.name, subject), text, pedido, meta, desktop)
        threading.Thread(target=work, daemon=True).start()

    def on_claude_ready(self, title: str, text: str, pedido: str, meta: str, desktop: bool = False):
        """Abre uma conversa NOVA no projeto, já com o pedido (e a transcrição, se couber) na caixa."""
        import os

        from .claude_link import plan_launch, write_redirect_page
        compact = not self.cfg.ask_in_app  # modo skill: só chama a skill e indica a transcrição
        plan = plan_launch(pedido, title, text, meta, self.cfg.claude_project_url, desktop=desktop, compact=compact)
        # cópia de segurança: o texto completo se tudo foi no link; senão, só a transcrição para colar
        QApplication.clipboard().setText(build_message(pedido, title, text, meta, compact) if plan.full
                                         else plan.clipboard)
        from .auto_send import auto_send, foreground_title
        title_before = foreground_title()
        try:
            if desktop:  # app do Windows: o sistema entrega o link claude:// inteiro ao app (testado até 12 mil caracteres)
                os.startfile(plan.url)  # noqa: S606
                raise _Opened
            page = write_redirect_page(plan.url)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(page)))

            def _cleanup(path=page):
                try:
                    os.remove(path)
                except OSError:
                    pass
            QTimer.singleShot(120_000, _cleanup)  # a página guarda o texto da reunião: não deixa no disco
        except _Opened:
            pass
        except OSError:
            QDesktopServices.openUrl(QUrl(plan.url))
        self.btn_claude.setEnabled(True)
        self.btn_claude_app.setEnabled(self.folder is not None)
        where = "no app Claude" if desktop else "no navegador"
        if self.cfg.auto_send and not desktop:  # navegador: espera a página carregar e envia sozinho
            def _send():
                auto_send(paste_first=not plan.full, initial_title=title_before, on_status=self.b.status.emit)
            threading.Thread(target=_send, name="auto-send", daemon=True).start()
        if plan.mode == "project":  # app do Windows: não aceita texto junto com o projeto
            self.lbl.setText("Projeto aberto no app Claude. Clique em “Nova sessão”, cole com Ctrl+V (o texto completo "
                             "já está copiado) e envie (↑). O app não consegue abrir a conversa pronta dentro do "
                             "projeto; o botão do navegador consegue.")
            return
        self.lbl.setText(f"Conversa aberta {where}, no projeto, já com o pedido e a transcrição. "
                         + ("Enviando sozinho em instantes… " if (self.cfg.auto_send and not desktop)
                            else "Clique em enviar (↑). ") + "O nome da conversa e os botões de copiar vêm da skill."
                         if plan.full else
                         f"Conversa aberta {where}, no projeto, com o pedido. A transcrição é longa: cole com Ctrl+V na "
                         "caixa e clique em enviar (↑). O nome da conversa e os botões de copiar vêm da skill.")

    def on_subject(self, folder: Path, err: str):
        self._busy(folder, "subject", None)
        if err:
            self.lbl.setText(f"Assunto não gerado ({err}); usando “Sem assunto”.")
        self.refresh_list(select=None, keep=True)

    def identify_speakers(self, folder: Path | None = None, quiet: bool = False):
        """Separa as vozes do canal da reunião (Pessoa 1, 2…). Baixa o modelo de voz na 1ª vez."""
        folder = folder or self.folder
        if not folder or (self.session is not None and self.session.dir == folder):
            return
        cfg = self.cfg
        if not quiet:
            choices = ["Automático", "1 pessoa", "2 pessoas", "3 pessoas", "4 pessoas", "5 pessoas", "6 pessoas"]
            pick, ok = QInputDialog.getItem(
                self, "Identificar falantes",
                "Quantas pessoas falam na reunião (sem contar você)?\n"
                "Informar o número costuma separar melhor vozes parecidas.",
                choices, 0, False)
            if not ok:
                return
            n_people = choices.index(pick)  # 0 = automático
            cfg = dataclasses.replace(self.cfg, num_speakers=n_people)
            self.btn_speakers.setEnabled(False)
            self.lbl.setText("Identificando falantes...")

        self._busy(folder, "identify", "identificando falantes…")

        def work():
            from .jobs import run_identify
            try:  # processo separado: a separação de vozes congelava a janela por ~1 min
                n = run_identify(folder, cfg.num_speakers, None if quiet else self.b.status.emit)
                self.b.speakers_done.emit(folder, n, "")
            except Exception as e:  # noqa: BLE001
                self.b.speakers_done.emit(folder, 0, str(e))
        threading.Thread(target=work, daemon=True).start()

    def on_speakers(self, folder: Path, n: int, err: str):
        self._busy(folder, "identify", None)
        self.btn_speakers.setEnabled(self.folder is not None)
        if err:
            self.lbl.setText(f"Não deu para identificar os falantes: {err}")
            return
        names = read_names(folder)
        known = [names[a] for a in read_auto_names(folder) if a in names]
        msg = f"{n} pessoa(s) identificada(s) na reunião." if n else "Nenhuma voz da reunião para identificar."
        if known:
            msg += f" Reconhecida(s) pela voz: {', '.join(known)}."
        self.lbl.setText(msg)
        if self.folder == folder and self.session is None:
            self.load_folder(folder)

    def _auto_subject(self, folder: Path):
        """Após parar a gravação: gera o assunto em segundo plano (silencioso se não houver chave)."""
        self._busy(folder, "subject", "gerando o assunto…")

        def work():
            from .summarize import generate_subject
            try:
                generate_subject(folder, self.cfg)
                self.b.subject_done.emit(folder, "")
            except Exception as e:  # noqa: BLE001 - sem rede: o assunto é gerado ao levar p/ o Claude
                if "ANTHROPIC_API_KEY" in str(e):  # avisa só quando falta a chave
                    self.b.subject_done.emit(folder, str(e))
        threading.Thread(target=work, daemon=True).start()

    def set_project(self):
        url, ok = QInputDialog.getText(
            self, "Projeto do Claude", "Cole a URL do projeto (ex.: https://claude.ai/project/...):",
            text=self.cfg.claude_project_url)
        if ok and url.strip().startswith("https://claude.ai/"):
            self.cfg.claude_project_url = url.strip()
            self.cfg.save()
            self.lbl.setText("Projeto salvo.")
        elif ok:
            QMessageBox.warning(self, "URL inválida", "A URL deve começar com https://claude.ai/")

    # ---- gravação ----
    def toggle(self):
        if self.session is None:
            self.stop_player()
            resume = self.folder  # reunião selecionada → continua nela; nenhuma → cria nova
            if resume is None:
                self.bubbles.clear()
                self.listw.clearSelection()
            self.rec.setEnabled(False)
            self.btn_new.setEnabled(False)
            self.lbl.setText("Carregando modelo...")
            threading.Thread(target=self._start, args=(resume,), daemon=True).start()
        else:
            self.rec.setEnabled(False)
            self.lbl.setText("Finalizando...")
            threading.Thread(target=self._stop, daemon=True).start()

    def _start(self, resume: Path | None = None):
        from .session import Session
        try:
            s = Session(self.cfg, self.b.utt.emit, self.b.status.emit)
            s.prepare()
            s.start(resume)
            self.session = s
            s.speaker_hint = self._live_speaker
        except Exception as e:  # noqa: BLE001
            self.session = None
            self.b.status.emit(f"Erro: {e}")
        self.b.started.emit()

    def on_started(self):
        self.rec.setEnabled(True)
        if not self.session:
            self.btn_new.setEnabled(True)
            self.lang.setEnabled(True)
            return
        self.draft = False
        self.refresh_list(keep=True)
        self._show_chat()
        self.elapsed = int(self.session.offset)
        self.timer_lbl.setText(fmt_time(self.elapsed))
        self.mini.set_time(fmt_time(self.elapsed))
        self.update_target(recording=True)
        parts = read_parts(self.session.dir)
        if len(parts) > 1:  # retomou: separador da nova parte (sem botão de ouvir enquanto grava)
            self.bubbles.add_separator(f"Parte {len(parts)} · {parts[-1]['at']}")
        self.lang.setEnabled(False)
        self.bubbles.names = read_names(self.session.dir)
        self.bubbles.auto_names = set(read_auto_names(self.session.dir))
        self.bubbles.scroll_to_end()
        self.mini.set_last("Aguardando fala...")
        self.tick.start(1000)
        self.rec.setProperty("recording", True)
        self._update_rec_icon()
        self.rec.setToolTip("Parar gravação")
        _repolish(self.rec)
        self.pulse.start(700)
        self.lbl.setText("Gravando...")
        if self.cfg.floating:
            self.enter_float()

    def enter_float(self):
        """Modo balão: esconde a janela e mostra a barra flutuante."""
        self.mini.show()
        self.hide()

    def toggle_float(self, on: bool):
        """Botão 🎈: liga/desliga o modo balão (vale na hora, se estiver gravando, e nas próximas gravações)."""
        self.cfg.floating = on
        self.cfg.save()
        if self.session is not None:
            self.enter_float() if on else self.expand()

    def _set_float_button(self, on: bool):
        self.btn_float.blockSignals(True)
        self.btn_float.setChecked(on)
        self.btn_float.blockSignals(False)

    def _beat(self):
        self.rec.setProperty("beat", not self.rec.property("beat"))
        _repolish(self.rec)

    def on_tick(self):
        self.elapsed += 1
        s = fmt_time(self.elapsed)
        self.timer_lbl.setText(s)
        self.mini.set_time(s)

    def expand(self):
        """Volta ao app normal (a preferência de modo balão é desligada)."""
        if self.cfg.floating and self.session is not None:
            self.cfg.floating = False
            self.cfg.save()
        self._set_float_button(self.cfg.floating)
        self.mini.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def _stop(self):
        s, self.session = self.session, None
        self.b.finished.emit(s.stop())

    def on_finished(self, folder: Path):
        self.tick.stop()
        self.pulse.stop()
        self.rec.setProperty("beat", False)
        self.rec.setProperty("recording", False)
        self._update_rec_icon()
        self.rec.setToolTip("Gravar (continua a reunião selecionada)")
        _repolish(self.rec)
        self.rec.setEnabled(True)
        self.btn_new.setEnabled(True)
        self.lang.setEnabled(True)
        self.expand()
        self.refresh_list(select=folder)
        if self.folder == folder:
            self.load_folder(folder)
        self._auto_subject(folder)
        from . import speakers as _sp
        if _sp.has_model():
            self.identify_speakers(folder, quiet=True)

    # ---- transcrição ao vivo ----
    def on_utt(self, u: Utterance):
        if u.final:
            rec = {"t0": u.t0, "t1": u.t1, "source": u.source, "text": u.text, "words": u.words}
            if u.speaker:
                rec["speaker"] = u.speaker
            self.bubbles.add_final(u.source, u.text, u.t0, rec)
        else:
            self.bubbles.set_partial(u.source, u.text, u.t0)
        self.mini.set_last(("Eu: " if u.source == "mic" else "Reunião: ") + u.text)


def main():
    try:  # barra de tarefas do Windows: agrupa sob o ícone do JB em vez do Python
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JB.JotBrief")
    except Exception:  # noqa: BLE001
        pass
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    w = Window()
    w.show()
    sys.exit(app.exec())

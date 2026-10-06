"""Envio automático no navegador: depois de abrir a conversa no Claude, espera a página carregar e aperta Enter.

Travas para não apertar tecla na janela errada:
- só age quando a janela em PRIMEIRO PLANO tem "Claude" no título e esse título MUDOU depois de abrir o link
  (evita enviar numa aba do Claude que já estava aberta);
- exige o título estável por alguns segundos (a caixa de mensagem já foi preenchida pelo link);
- se você trocar de janela antes da hora, não envia nada.
Em calls longas (transcrição na área de transferência) cola com Ctrl+V antes do Enter.
"""
from __future__ import annotations

import ctypes
import time
from typing import Callable

VK_RETURN, VK_CONTROL, VK_V = 0x0D, 0x11, 0x56
KEYEVENTF_KEYUP = 0x0002


def foreground_title() -> str:
    """Título da janela em primeiro plano ('' se não der para ler)."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value
    except (AttributeError, OSError):
        return ""


def _tap(*vks: int) -> None:
    user32 = ctypes.windll.user32
    for vk in vks:
        user32.keybd_event(vk, 0, 0, 0)
    for vk in reversed(vks):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def press_enter() -> None:
    _tap(VK_RETURN)


def press_ctrl_v() -> None:
    _tap(VK_CONTROL, VK_V)


def _is_claude_page(title: str) -> bool:
    t = title.lower()
    return "claude" in t and "abrindo o claude" not in t


def wait_for_claude_page(initial_title: str, timeout: float = 40.0, settle: float = 3.5, poll: float = 0.4,
                         title_fn: Callable[[], str] = foreground_title, sleep: Callable[[float], None] = time.sleep,
                         clock: Callable[[], float] = time.monotonic) -> bool:
    """True quando a janela em primeiro plano virou a página do Claude (nova) e ficou estável por `settle` s."""
    deadline = clock() + timeout
    seen_since: float | None = None
    changed = False
    while clock() < deadline:
        t = title_fn()
        if t != initial_title:
            changed = True
        if changed and _is_claude_page(t):
            seen_since = seen_since if seen_since is not None else clock()
            if clock() - seen_since >= settle:
                return True
        else:
            seen_since = None
        sleep(poll)
    return False


def auto_send(paste_first: bool, initial_title: str, on_status: Callable[[str], None] = lambda m: None,
              title_fn: Callable[[], str] = foreground_title) -> bool:
    """Espera a página e envia. Retorna True se apertou Enter."""
    if not wait_for_claude_page(initial_title, title_fn=title_fn):
        on_status("Não consegui enviar sozinho (a página do Claude não ficou em primeiro plano). Clique em enviar (↑).")
        return False
    if paste_first:
        press_ctrl_v()  # a transcrição longa está na área de transferência
        time.sleep(1.2)
    if not _is_claude_page(title_fn()):  # mudou de janela nesse meio-tempo: não envia
        on_status("Envio automático cancelado (a janela do Claude saiu do primeiro plano).")
        return False
    press_enter()
    on_status("Enviado automaticamente. Acompanhe a conversa no Claude.")
    return True

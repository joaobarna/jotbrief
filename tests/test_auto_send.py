from jotbrief import auto_send as a


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def run(titles, timeout=40.0, settle=3.5):
    clk, it = Clock(), iter(titles)
    last = {"v": titles[-1]}

    def title():
        try:
            last["v"] = next(it)
        except StopIteration:
            pass
        return last["v"]

    return a.wait_for_claude_page("Reunião conserto - Claude - Google Chrome", timeout, settle, 0.4, title, clk.sleep, clk.now)


def test_does_not_fire_on_an_already_open_claude_tab():
    # o título nunca mudou: era outra aba do Claude que já estava aberta
    assert run(["Reunião conserto - Claude - Google Chrome"] * 200, timeout=20) is False


def test_waits_for_the_new_page_then_settles():
    seq = ["Reunião conserto - Claude - Google Chrome", "Abrindo o Claude… - Google Chrome"] + \
          ["Nova sessão - Claude - Google Chrome"] * 40
    assert run(seq) is True


def test_redirect_page_title_alone_is_not_enough():
    assert run(["Abrindo o Claude… - Google Chrome"] * 200, timeout=20) is False


def test_abort_when_user_switches_window():
    seq = ["Nova sessão - Claude - Google Chrome"] * 3 + ["Bloco de Notas"] * 200
    assert run(seq, timeout=20) is False


def test_auto_send_presses_enter_only_after_checks(monkeypatch):
    pressed, msgs = [], []
    monkeypatch.setattr(a, "press_enter", lambda: pressed.append("enter"))
    monkeypatch.setattr(a, "press_ctrl_v", lambda: pressed.append("paste"))
    monkeypatch.setattr(a.time, "sleep", lambda s: None)
    monkeypatch.setattr(a, "wait_for_claude_page", lambda *x, **k: True)
    assert a.auto_send(True, "x", msgs.append, title_fn=lambda: "Nova sessão - Claude") is True
    assert pressed == ["paste", "enter"]                                       # transcrição longa: cola e envia
    pressed.clear()
    assert a.auto_send(False, "x", msgs.append, title_fn=lambda: "Bloco de Notas") is False and pressed == []

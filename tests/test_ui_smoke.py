"""Abre a janela e todos os diálogos (sem mostrar na tela) para pegar erros de importação/construção."""
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_window_and_dialogs_construct(app, tmp_path):
    from jotbrief import ui
    from jotbrief.prompts import load_prompts

    w = ui.Window()
    for name in ("btn_claude_app", "btn_reprocess", "btn_speakers", "btn_names", "btn_claude", "btn_folder", "btn_copy", "rec"):
        assert hasattr(w, name), name
    folder = tmp_path / "2026-09-29_1600"
    folder.mkdir()
    recs = [{"t0": 1.0, "t1": 2.0, "source": "loop", "speaker": "Pessoa 1", "text": "oi"},
            {"t0": 3.0, "t1": 4.0, "source": "mic", "text": "olá"}]
    (folder / "transcricao.jsonl").write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    w.load_folder(folder)
    assert len(w.bubbles.entries) == 2
    assert ui.ReprocessDialog("auto", True, w).values() == ("auto", True, 0)
    assert ui.NamesDialog(["Pessoa 1", "Eu"], {}, w).result_names() == {"Pessoa 1": "", "Eu": ""}
    nd = ui.NamesDialog(["Pessoa 1"], {"Pessoa 1": "Gestor"}, w, ["Carlos", "Gestor"])
    assert nd.result_names() == {"Pessoa 1": "Gestor"} and nd.edits["Pessoa 1"].count() == 2
    pd = ui.PersonDialog("Pessoa 2", "", ["Carlos", "Ana"], w)
    assert pd.name() == "" and pd.combo.count() == 2
    pd.combo.setEditText("Novo Nome")
    assert pd.name() == "Novo Nome"
    assert ui.PromptDialog(load_prompts(), w).choice is None
    box = w.findChild(QtWidgets.QFrame, "claudebox")      # os 3 botões do Claude ficam juntos num box
    lay = box.layout()                                     # ordem no box: navegador, projeto (pasta), app (manual)
    assert [lay.itemAt(i).widget() for i in range(lay.count())] == [w.btn_claude, w.btn_proj, w.btn_claude_app]
    w.close()


def test_new_meeting_row_and_busy_marker(app, tmp_path):
    from pathlib import Path

    from jotbrief import ui

    w = ui.Window()
    w.cfg.output_dir = tmp_path
    w._expanded = None  # a janela já abriu o dia de hoje da pasta real
    folder = tmp_path / "2026-09-29_1600"
    folder.mkdir()
    (folder / "transcricao.jsonl").write_text(json.dumps({"t0": 1.0, "t1": 2.0, "source": "loop", "text": "oi"}),
                                              encoding="utf-8")
    w.refresh_list()
    texts = lambda: [w.listw.itemWidget(w.listw.item(i)).lbl.text() for i in range(w.listw.count())  # noqa: E731
                     if isinstance(w.listw.itemWidget(w.listw.item(i)), ui.MeetingRow)]
    assert not any(t.startswith("Nova reunião") for t in texts())
    w.new_meeting()                                           # clicou em "Nova reunião": a linha aparece no topo
    assert texts()[0].startswith("Nova reunião") and w.listw.currentItem().data(ui.Qt.UserRole) == ""
    w.on_pick(w.listw.currentItem())                          # clicar nela não quebra nada
    w._busy(Path(folder), "identify", "identificando falantes…")
    assert any("⏳ identificando falantes…" in t for t in texts())
    w._busy(Path(folder), "identify", None)
    assert not any("⏳" in t for t in texts())
    w.close()


def test_chat_panel_streams_and_persists(app, tmp_path, monkeypatch):
    import time

    from jotbrief import chat, ui

    folder = tmp_path / "2026-09-29_1600"
    folder.mkdir()
    (folder / "transcricao.jsonl").write_text(
        json.dumps({"t0": 1.0, "t1": 2.0, "source": "loop", "speaker": "Pessoa 1", "text": "vamos fechar o orçamento"}),
        encoding="utf-8")
    seen = {}

    def fake_stream(cfg, system, messages, on_delta, stop=None):
        seen["system"], seen["messages"] = system, messages
        for piece in ("Resumo ", "pronto."):
            on_delta(piece)
        return "Resumo pronto.", {"in": 1200, "out": 300, "read": 5000, "write": 0}

    monkeypatch.setattr(chat, "stream_reply", fake_stream)
    w = ui.Window()
    w.load_folder(folder)
    w.chat.ask.emit("📝 Resumo detalhado", "faça o resumo")
    t0 = time.time()
    while w._chat_busy and time.time() - t0 < 5:
        app.processEvents()
    app.processEvents()
    msgs = w.chats[str(folder)]
    assert [m["role"] for m in msgs] == ["user", "assistant"] and msgs[1]["content"] == "Resumo pronto."
    assert "vamos fechar o orçamento" in seen["system"] and seen["messages"] == [{"role": "user", "content": "faça o resumo"}]
    assert chat.load_chat(folder)[1]["content"] == "Resumo pronto."          # salvo na pasta da reunião
    assert "Resumo pronto." in w.chat.view.toPlainText() and "Resumo detalhado" in w.chat.view.toPlainText()
    w.chat_clear()
    assert w.chats[str(folder)] == [] and not (folder / "chat.json").exists()
    w.close()


def test_day_groups_collapse_except_latest(app, tmp_path):
    from jotbrief import ui

    for name in ("2026-09-28_0900", "2026-09-29_1600", "2026-09-29_1700"):
        d = tmp_path / name
        d.mkdir()
        (d / "transcricao.jsonl").write_text(json.dumps({"t0": 1.0, "t1": 2.0, "source": "loop", "text": "oi"}),
                                             encoding="utf-8")
    w = ui.Window()
    w.cfg.output_dir = tmp_path
    w._expanded = None
    w.refresh_list()
    rows = lambda: sum(isinstance(w.listw.itemWidget(w.listw.item(i)), ui.MeetingRow)  # noqa: E731
                       for i in range(w.listw.count()))
    heads = lambda: [w.listw.itemWidget(w.listw.item(i)).text() for i in range(w.listw.count())  # noqa: E731
                     if isinstance(w.listw.itemWidget(w.listw.item(i)), QtWidgets.QPushButton)]
    assert rows() == 2 and heads()[0].startswith("▾") and heads()[1].startswith("▸")   # só o último dia aberto
    w._toggle_day("2026-09-28")
    app.processEvents()
    app.processEvents()
    assert rows() == 3 and all(h.startswith("▾") for h in heads())
    w._toggle_day("2026-09-29")
    app.processEvents()
    app.processEvents()
    assert rows() == 1 and heads()[0].startswith("▸")
    w.close()


def test_delete_blocked_for_meeting_being_recorded_even_with_relative_path(app, tmp_path, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace

    from jotbrief import ui

    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunioes" / "2026-10-02_1114").mkdir(parents=True)
    w = ui.Window()
    w.session = SimpleNamespace(dir=Path("reunioes") / "2026-10-02_1114")           # a sessão guarda o caminho relativo
    shown = []
    monkeypatch.setattr(ui.QMessageBox, "information", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr(ui.QMessageBox, "exec", lambda self: (_ for _ in ()).throw(AssertionError("não devia perguntar")))
    w.delete_meeting(str((tmp_path / "reunioes" / "2026-10-02_1114").resolve()))   # a lista usa o absoluto
    assert shown and "Pare a gravação" in shown[0]
    w.session = None
    w.close()


def test_cuda_offer_only_in_installed_app_with_nvidia_and_missing_libs(app, monkeypatch):
    import sys

    from jotbrief import cuda_setup, ui

    w = ui.Window()
    asked = []
    monkeypatch.setattr(ui.QMessageBox, "exec", lambda self: asked.append(self.text()))
    w._offer_cuda()
    assert asked == []                                        # código-fonte (não instalado): nunca pergunta
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(cuda_setup, "gpu_present", lambda: False)
    w._offer_cuda()
    assert asked == []                                        # sem placa NVIDIA
    monkeypatch.setattr(cuda_setup, "gpu_present", lambda: True)
    monkeypatch.setattr(cuda_setup, "cuda_ready", lambda: True)
    w._offer_cuda()
    assert asked == []                                        # já tem as bibliotecas
    monkeypatch.setattr(cuda_setup, "cuda_ready", lambda: False)
    w.cfg.cuda_offer = "never"
    w._offer_cuda()
    assert asked == []                                        # "não perguntar mais"
    w.cfg.cuda_offer = "ask"
    monkeypatch.setattr(ui.QMessageBox, "clickedButton", lambda self: None)
    w._offer_cuda()
    assert len(asked) == 1 and "1,3 GB" in asked[0]           # pergunta uma vez, com o tamanho
    w.close()


def test_api_key_dialog_rejects_bad_keys_without_calling_the_api(app, monkeypatch):
    from jotbrief import chat, ui

    called = []
    monkeypatch.setattr(chat, "test_key", lambda k, m: called.append(k) or "")
    d = ui.ApiKeyDialog(None, False)
    d.edit.setText("curta")
    d._save()
    assert "incompleta" in d.msg.text() and called == []
    monkeypatch.setattr(chat, "test_key", lambda k, m: "A Anthropic recusou esta chave (inválida ou revogada).")
    d.edit.setText("sk-ant-" + "z" * 30)
    d._save()
    assert "recusou" in d.msg.text() and d.result() != ui.QDialog.Accepted


def test_footer_shows_version_and_versions_dialog_lists_history(app):
    from jotbrief import ui, versao

    w = ui.Window()
    btn = w.findChild(QtWidgets.QPushButton, "verlink")
    assert btn is not None and btn.text() == f"Versão {versao.atual()}"
    d = ui.VersionsDialog(w)
    assert versao.atual() in d.findChild(QtWidgets.QLabel, "brand").text()
    assert versao.entradas()[0]["titulo"][:20] in d.findChild(QtWidgets.QTextBrowser).toPlainText()
    w.close()


def test_api_key_dialog_links_to_anthropic_keys_page(app):
    from jotbrief import ui

    d = ui.ApiKeyDialog(None, False)
    intro = d.findChildren(QtWidgets.QLabel)[0]
    assert ui.API_KEYS_URL == "https://platform.claude.com/settings/keys"
    assert ui.API_KEYS_URL in intro.text() and intro.openExternalLinks()

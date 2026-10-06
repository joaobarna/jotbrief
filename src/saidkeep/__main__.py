from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def _load_env():
    from .config import load_env
    load_env()


def cmd_run(args):
    from .config import Config
    from .session import Session, fmt_time

    cfg = Config.load()

    def on_utt(u):
        if u.final:
            who = {"mic": "Eu", "loop": "Reunião"}[u.source]
            print(f"[{fmt_time(u.t0)}] {who}: {u.text}", flush=True)

    s = Session(cfg, on_utt, lambda m: print(f"* {m}", flush=True))
    s.prepare()
    s.start()
    print("Gravando. Ctrl+C para parar.")
    try:
        while True:
            import time
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    folder = s.stop()
    print(f"Pasta: {folder}")


def cmd_devices(_):
    from .audio import default_devices, list_devices
    d = list_devices()
    for kind in ("mics", "loopbacks"):
        print(kind)
        for x in d[kind]:
            print(f"  [{x['index']}] {x['name']} ({int(x['defaultSampleRate'])} Hz)")
    mic, spk = default_devices()
    print(f"padrão: mic={mic['name']} | loopback={spk['name']}")


def cmd_setup(_):
    from .config import Config
    from .transcriber import Transcriber
    from .vad import SileroVad

    SileroVad()  # carrega o modelo de detecção de fala (ONNX)
    t = Transcriber(Config.load(), lambda u: None)
    t.load()
    print(f"Modelos prontos: {t.model_name}")


def cmd_selftest(_):
    """Autodiagnóstico (também para suporte): versões, GPU, bibliotecas CUDA, arquivos dos modelos e carga real dos modelos."""
    import os
    import platform
    import sys
    import traceback
    from pathlib import Path

    from . import cuda_setup, logs, runtime, versao
    from .config import Config

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    bad = 0

    def line(ok: bool, text: str):
        nonlocal bad
        bad += 0 if ok else 1
        print(("OK     " if ok else "FALHA  ") + text, flush=True)

    cfg = Config.load()
    print(f"SaidKeep {versao.atual()} | {'instalado' if runtime.is_frozen() else 'código-fonte'} | "
          f"Python {platform.python_version()} | {platform.platform()}")
    print(f"log: {logs.log_path()} | dados: {runtime.data_dir()} | pasta das reuniões: {Path(cfg.output_dir).resolve()}")
    line(Path(cfg.output_dir).is_absolute() or not runtime.is_frozen(),
         f"pasta das reuniões é absoluta ({cfg.output_dir})" if Path(cfg.output_dir).is_absolute()
         else f"pasta das reuniões é RELATIVA ({cfg.output_dir}): no app instalado deveria ser absoluta")
    try:
        import ctranslate2
        n = ctranslate2.get_cuda_device_count()
        print(f"ctranslate2 {ctranslate2.__version__} | placas CUDA: {n} | NVIDIA presente: {cuda_setup.gpu_present()}")
    except Exception as e:  # noqa: BLE001
        line(False, f"ctranslate2: {e}")
    line(cuda_setup.cuda_ready(), "bibliotecas CUDA (cuBLAS e cuDNN) encontradas: "
         + (", ".join(str(d) for d in runtime.dll_search_dirs()) or "nenhuma"))
    try:
        from .transcriber import resolve_device
        name, device, compute = resolve_device(cfg)
        print(f"modelo escolhido: {name} ({device}/{compute})")
        from faster_whisper.utils import download_model
        for model in {name, cfg.model_cpu}:
            try:
                path = Path(download_model(model, local_files_only=True))   # o mesmo método que o faster-whisper usa
                mb = path / "model.bin"
                ok = mb.exists()
                size = mb.stat().st_size // 1_048_576 if ok else 0
                if ok:
                    with open(mb, "rb") as f:   # abre e lê de verdade (é aqui que um antivírus seguraria o arquivo)
                        f.read(1 << 20)
                line(ok, f"arquivo do modelo {model}: {mb} ({size} MB, {'link' if mb.is_symlink() else 'arquivo'})")
            except Exception as e:  # noqa: BLE001
                line(False, f"arquivo do modelo {model}: {type(e).__name__}: {e}")
    except Exception:  # noqa: BLE001
        line(False, "escolha do modelo:\n" + traceback.format_exc())
    try:
        from .transcriber import Transcriber
        t = Transcriber(cfg, lambda u: None)
        t.load()
        line(True, f"Whisper carregado: {t.model_name}")
    except Exception:  # noqa: BLE001
        line(False, "Whisper não carregou:\n" + traceback.format_exc())
    try:
        from .vad import SileroVad
        SileroVad()
        line(True, "detector de fala (ONNX) carregado")
    except Exception:  # noqa: BLE001
        line(False, "detector de fala:\n" + traceback.format_exc())
    print("\nTudo certo." if not bad else f"\n{bad} problema(s) encontrado(s). Mande este texto para o suporte.")
    return 1 if bad else 0


def cmd_mcp(_):
    from .mcp_server import main as mcp_main
    mcp_main()


def cmd_mcp_config(_):
    """Mostra o trecho para o claude_desktop_config.json (não altera nada)."""
    import json

    from .claude_config import server_entry
    cfg = {"mcpServers": {"saidkeep": server_entry()}}
    print(json.dumps(cfg, indent=2, ensure_ascii=False))


def cmd_mcp_install(args):
    """Registra o servidor no Claude Desktop (com backup). Exige o Claude fechado."""
    from . import claude_config as cc

    if cc.claude_running() and not args.force:
        print("O Claude Desktop está aberto: ele reescreve a configuração e perderia a alteração.\n"
              "Feche-o por completo (ícone da bandeja → Sair) e rode este comando de novo.")
        return 1
    for path in ([Path(args.config)] if args.config else cc.config_paths()):
        backup = cc.install(path)
        print(f"Configurado: {path}\n  backup: {backup.name if backup else '(arquivo novo)'}\n"
              f"  verificado: {cc.is_installed(path)}")
    print("Agora abra o Claude Desktop e peça: \"liste minhas reuniões do SaidKeep\".")
    return 0


def cmd_check_key(_):
    """Testa a chave da API (chamada gratuita que só consulta o modelo); nunca mostra a chave."""
    import anthropic

    from .config import Config, env_candidates

    found = [str(p) for p in env_candidates() if p.exists()]
    print("Arquivos .env encontrados:", ", ".join(found) if found else "nenhum")
    print("ANTHROPIC_API_KEY:", "definida" if os.environ.get("ANTHROPIC_API_KEY") else "NÃO definida")
    model = Config.load().claude_model
    try:
        m = anthropic.Anthropic().models.retrieve(model)
    except anthropic.AuthenticationError:
        print("A chave foi recusada pela Anthropic (inválida, revogada ou sem crédito de acesso).")
        return 1
    except anthropic.APIConnectionError as e:
        print(f"Sem conexão com a API: {e}")
        return 1
    except (anthropic.AnthropicError, TypeError) as e:  # sem credencial configurada etc.
        if isinstance(e, TypeError) and "authentication" not in str(e).lower():
            raise
        print("Nenhuma credencial encontrada. Coloque ANTHROPIC_API_KEY=sua_chave no arquivo .env "
              "(veja o README) e rode este comando de novo.")
        return 1
    print(f"OK: chave válida; modelo {m.id} disponível.")
    return 0


def cmd_subjects(_):
    """Gera o assunto das reuniões salvas que ainda estão 'Sem assunto'."""
    from . import meetings
    from .config import Config
    from .summarize import generate_subject
    from .ui_helpers import read_subject

    cfg = Config.load()
    todo = [d for d in meetings.meeting_dirs(meetings.default_root(cfg)) if not read_subject(d)]
    if not todo:
        print("Todas as reuniões já têm assunto.")
        return 0
    for d in todo:
        try:
            print(f"{d.name}: {generate_subject(d, cfg)}")
        except Exception as e:  # noqa: BLE001
            print(f"{d.name}: não gerado ({e})")
            if "ANTHROPIC_API_KEY" in str(e):
                return 1  # sem chave: não adianta tentar as outras
    return 0


def cmd_learn_voices(_):
    """Aprende as vozes das pessoas que você já nomeou nas reuniões salvas (só nomes definidos por você)."""
    from . import meetings, voices
    from .config import Config
    from .ui_helpers import read_auto_names, read_names
    from .voices import learnable_label

    root = meetings.default_root(Config.load())
    total = 0
    for d in meetings.meeting_dirs(root):
        auto = set(read_auto_names(d))
        for label, name in read_names(d).items():
            if learnable_label(label) and label not in auto:
                secs = voices.learn_from_meeting(d, label, name)
                if secs > 0:
                    total += 1
                    print(f"{d.name}: {label} = {name} ({secs:.0f} s de fala)")
    known = voices.load_voices()
    print(f"{total} voz(es) aprendida(s). Cadastro: {', '.join(known) if known else 'vazio'}")
    print(f"Arquivo: {voices.VOICES_PATH}  (apague-o para esquecer todas as vozes)")
    return 0


def cmd_identify(args):
    """Separa as vozes de uma reunião (usado pelo app, em processo separado). Saída: linhas STATUS/RESULT/ERROR."""
    import dataclasses
    from pathlib import Path

    from . import speakers
    from .config import Config

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    cfg = Config.load()
    if args.people:
        cfg = dataclasses.replace(cfg, num_speakers=args.people)
    try:
        n = speakers.identify(Path(args.folder), cfg, progress=lambda m: print("STATUS " + str(m).replace("\n", " "), flush=True))
    except Exception as e:  # noqa: BLE001
        print("ERROR " + str(e).replace("\n", " "), flush=True)
        return 1
    print(f"RESULT {n}", flush=True)
    return 0


def cmd_skill(_):
    """Gera a skill do Claude 'jb-transcricao' (SKILL.md + painel.html + .zip) na pasta skills/ do projeto."""
    from pathlib import Path

    from .skill import SKILL_NAME, build_skill

    from .runtime import is_frozen, project_root, user_files_dir
    dest = (user_files_dir() if is_frozen() else project_root()) / "skills"
    z = build_skill(dest)
    print(f"Skill gerada em: {dest / SKILL_NAME}")
    print(f"Arquivo para enviar ao Claude: {z}")
    print("Instalar: Claude → Configurações → Capacidades (ou Personalizar) → Skills → Enviar skill → escolha o .zip.")
    return 0


def cmd_gui(_):
    from .ui import main as ui_main
    ui_main()


def main():
    try:  # o console do Windows (cp1252) não imprime setas e acentos de alguns textos
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    from .runtime import migrate_legacy
    migrated = migrate_legacy()  # antes de tudo: dados do nome antigo (jotbrief) passam para saidkeep
    _load_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from . import logs
    logs.setup()  # também em arquivo: o app instalado não tem console
    for m in migrated:
        logging.getLogger("saidkeep").info("dados migrados do nome antigo: %s", m)
    p = argparse.ArgumentParser(prog="saidkeep")
    from .versao import atual
    p.add_argument("--version", action="version", version=f"SaidKeep {atual()}")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="grava e transcreve (CLI)")
    r.set_defaults(fn=cmd_run)
    sub.add_parser("devices", help="lista dispositivos").set_defaults(fn=cmd_devices)
    sub.add_parser("setup", help="baixa/carrega os modelos").set_defaults(fn=cmd_setup)
    sub.add_parser("gui", help="abre a janela").set_defaults(fn=cmd_gui)
    sub.add_parser("mcp", help="servidor MCP (o Claude Desktop lê as reuniões)").set_defaults(fn=cmd_mcp)
    sub.add_parser("skill", help="gera a skill do Claude (jb-transcricao) e o painel HTML").set_defaults(fn=cmd_skill)
    sub.add_parser("mcp-config", help="mostra o trecho de configuração do Claude Desktop").set_defaults(fn=cmd_mcp_config)
    sub.add_parser("check-key", help="testa a ANTHROPIC_API_KEY").set_defaults(fn=cmd_check_key)
    sub.add_parser("subjects", help="gera o assunto das reuniões que estão 'Sem assunto'").set_defaults(fn=cmd_subjects)
    sub.add_parser("learn-voices", help="aprende as vozes das pessoas já nomeadas nas reuniões salvas") \
        .set_defaults(fn=cmd_learn_voices)
    sub.add_parser("selftest", help="autodiagnóstico: versões, GPU, modelos e o que falhar").set_defaults(fn=cmd_selftest)
    idf = sub.add_parser("identify", help="separa as vozes de uma reunião (usado pelo app)")
    idf.add_argument("folder")
    idf.add_argument("--people", type=int, default=0, help="nº de pessoas na call (0 = automático)")
    idf.set_defaults(fn=cmd_identify)
    mi = sub.add_parser("mcp-install", help="registra o servidor no Claude Desktop (feche o Claude antes)")
    mi.add_argument("--force", action="store_true", help="grava mesmo com o Claude aberto (a alteração pode se perder)")
    mi.add_argument("--config", help="caminho do claude_desktop_config.json (padrão: detectado)")
    mi.set_defaults(fn=cmd_mcp_install)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

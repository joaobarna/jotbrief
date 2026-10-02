from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

_APPDATA = Path(os.environ.get("APPDATA", Path.home()))
CONFIG_PATH = _APPDATA / "jotbrief" / "config.toml"
_OLD_CONFIG_PATH = _APPDATA / "meet-transcriber" / "config.toml"  # nome anterior do app


def env_candidates() -> list[Path]:
    """Onde procurar o .env: pasta atual, raiz do projeto e %APPDATA%\\jotbrief (na ordem)."""
    return [Path(".env"), Path(__file__).resolve().parents[2] / ".env",
            Path(os.environ.get("APPDATA", str(Path.home()))) / "jotbrief" / ".env"]


def load_env(candidates: list[Path] | None = None) -> list[str]:
    """Carrega KEY=valor dos .env encontrados (sem sobrescrever o que já está no ambiente).

    Retorna só os NOMES das variáveis carregadas (nunca os valores).
    """
    loaded: list[str] = []
    for env in candidates if candidates is not None else env_candidates():
        try:
            lines = env.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if k and v and k not in os.environ:
                os.environ[k] = v
                loaded.append(k)
    return loaded


def user_env_path() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "jotbrief" / ".env"


def save_api_key(key: str, path: Path | None = None) -> Path:
    """Guarda a chave da API em %APPDATA%\\jotbrief\\.env (só neste computador) e já a deixa valendo nesta execução."""
    key = key.strip()
    if len(key) < 20 or any(c.isspace() for c in key):
        raise ValueError("A chave parece incompleta: cole a chave inteira, sem espaços.")
    path = Path(path or user_env_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8-sig").splitlines()
                 if not ln.strip().startswith("ANTHROPIC_API_KEY")]
    except OSError:
        lines = []
    lines.append(f"ANTHROPIC_API_KEY={key}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["ANTHROPIC_API_KEY"] = key
    return path


# Modelos que dá para escolher no app (rótulo, id). Só o Haiku 4.5 não aceita o parâmetro de esforço.
MODELS = [
    ("Sonnet 5.5 · equilibrado", "claude-sonnet-5-5"),
    ("Opus 5.5 · mais capaz", "claude-opus-5-5"),
    ("Haiku 4.5 · mais barato", "claude-haiku-4-5"),
]


def supports_effort(model: str) -> bool:
    return not model.startswith("claude-haiku")


def _default_output_dir() -> Path:
    from .runtime import default_output_dir
    return default_output_dir()


@dataclass
class Config:
    language: str = "pt"
    device: str = "auto"  # auto | cuda | cpu
    model_gpu: str = "large-v3-turbo"
    model_cpu: str = "small"
    output_dir: Path = field(default_factory=lambda: _default_output_dir())
    claude_model: str = "claude-sonnet-5-5"
    skill_name: str = "jb-jot-brief-transcricao"  # nome da skill criada no Claude (vai no início da mensagem)
    auto_send: bool = True  # botão do navegador: aperta Enter sozinho depois de abrir a conversa no Claude
    ask_in_app: bool = False  # True: o botão do Claude pergunta o que gerar no app (senão, a skill pergunta no Claude)
    claude_project_url: str = "https://claude.ai/projects"
    calendar_ics_url: str = ""  # "endereço secreto em formato iCal" do Google Agenda: sugere os convidados como nomes
    diarization_threshold: float = 0.3  # separação de vozes: menor = separa mais pessoas (0.15 exagera)
    voice_match_threshold: float = 0.75  # semelhança de voz p/ reconhecer uma pessoa já nomeada (maior = mais rígido)
    voice_match_margin: float = 0.05  # vantagem mínima sobre a 2ª pessoa mais parecida
    num_speakers: int = 0  # nº de pessoas na call, se souber (0 = automático)
    speaker_threshold: float = 0.55  # similaridade de voz p/ ser a mesma pessoa (maior = separa mais)
    theme: str = "claro"
    volume: int = 100  # volume do player (0–100)
    floating: bool = False  # modo balão: ao gravar, a janela vira a barra flutuante
    chat_open: bool = True  # coluna do chat com o Claude (💬) visível
    update_check: bool = True  # ao abrir, confere em segundo plano se há versão nova (só avisa; atualizar é com um clique seu)
    cuda_offer: str = "ask"  # app instalado com placa NVIDIA: "ask" pergunta se baixa a aceleração por GPU; "never" não pergunta mais
    chat_effort: str = "medium"  # esforço do Claude no chat: low | medium | high | xhigh | max (mais esforço = mais lento e caro)
    silence_ms: int = 600
    max_segment_s: float = 15.0
    mic_device: int | None = None
    loopback_device: int | None = None

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if not CONFIG_PATH.exists() and _OLD_CONFIG_PATH.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_bytes(_OLD_CONFIG_PATH.read_bytes())
        if CONFIG_PATH.exists():
            data = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, Path(v) if k == "output_dir" else v)
        from .runtime import is_frozen, user_files_dir
        if is_frozen() and not Path(cfg.output_dir).is_absolute():
            # caminho relativo (herdado do uso pelo código-fonte) não faz sentido no app instalado: vai para Documentos
            cfg.output_dir = user_files_dir() / cfg.output_dir
        return cfg

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for k, v in asdict(self).items():
            if v is None:
                continue
            if isinstance(v, Path):
                v = v.as_posix()
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")  # TOML usa minúsculas
            else:
                lines.append(f'{k} = "{v}"' if isinstance(v, str) else f"{k} = {v}")
        CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

"""Gera o site estático em site/public/ (Cloudflare Pages publica essa pasta).

Uso (na raiz do projeto):  uv run --with markdown python site/build.py
Páginas: site/src/pages/{pt,en}/*.html (só o miolo) + o layout abaixo.
A documentação sai do DOCUMENTACAO.md (pt) e do DOCUMENTATION.en.md (en).
Português fica na raiz (/), inglês em /en/.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
SRC, OUT = HERE / "src", HERE / "public"
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
try:  # versão = a do último commit (YYYY.MM.DD.HH.mm), igual à do app e à da Release
    CFG["version"] = json.loads((HERE.parent / "src" / "jotbrief" / "data" / "changelog.json").read_text(encoding="utf-8"))[0]["versao"]
except (OSError, ValueError, IndexError, KeyError):
    pass

# bandeiras redondas (sem ids, para poder repetir na mesma página)
BR = ('<span class="flagwrap"><svg class="flag" viewBox="0 0 60 60" aria-hidden="true"><rect width="60" height="60" fill="#009C3B"/>'
      '<path d="M30 9 55 30 30 51 5 30Z" fill="#FFDF00"/><circle cx="30" cy="30" r="11" fill="#002776"/></svg></span>')
_H = 60 / 13
_STRIPES = "".join(f'<rect y="{i * _H:.3f}" width="60" height="{_H:.3f}" fill="#B22234"/>' for i in range(0, 13, 2))
US = ('<span class="flagwrap"><svg class="flag" viewBox="0 0 60 60" aria-hidden="true"><rect width="60" height="60" fill="#fff"/>'
      f'{_STRIPES}<rect width="26" height="{7 * _H:.3f}" fill="#3C3B6E"/></svg></span>')

LANGS = {
    "pt": {
        "html": "pt-BR", "og": "pt_BR", "flag": BR, "switch_label": "Idioma",
        "paths": {"home": "/", "projects": "/projetos/", "jb": "/jot-brief/", "docs": "/jot-brief/docs/"},
        "nav": {"home": "Sobre", "projects": "Projetos"}, "nav_label": "Principal", "crumb_label": "Você está em",
        "docs_label": "Documentação", "footer_email": "E-mail",
        "titles": {
            "home": ("João Barnabé", "CFO e Diretor Financeiro com mais de 8 anos em e-commerce de alto crescimento: Controladoria, Tesouraria, FP&A, 2 IPOs e integração de M&A."),
            "projects": ("Projetos · João Barnabé", "Projetos de João Barnabé: ferramentas para o dia a dia de finanças e gestão, abertas para quem quiser usar."),
            "jb": ("JB - Jot Brief · Transcrição de reuniões para Windows", "Transcreva reuniões do Meet, Teams e Zoom sem bot, veja quem falou e converse com o Claude. 100% local."),
            "docs": ("Documentação · JB - Jot Brief", "Tudo o que o JB - Jot Brief faz e como usar."),
            "404": ("Página não encontrada · João Barnabé", "Esta página não existe. This page does not exist."),
        },
        "docs_md": HERE.parent / "DOCUMENTACAO.md",
    },
    "en": {
        "html": "en", "og": "en_US", "flag": US, "switch_label": "Language",
        "paths": {"home": "/en/", "projects": "/en/projects/", "jb": "/en/jot-brief/", "docs": "/en/jot-brief/docs/"},
        "nav": {"home": "About", "projects": "Projects"}, "nav_label": "Main", "crumb_label": "You are here",
        "docs_label": "Documentation", "footer_email": "Email",
        "titles": {
            "home": ("João Barnabé", "CFO and Finance Director with 8+ years in high-growth e-commerce: Controllership, Treasury, FP&A, 2 IPOs and M&A integration."),
            "projects": ("Projects · João Barnabé", "João Barnabé's projects: tools for everyday finance and management work, open to anyone who wants to use them."),
            "jb": ("JB - Jot Brief · Meeting transcription for Windows", "Transcribe Meet, Teams and Zoom meetings without a bot, see who spoke and chat with Claude. 100% local."),
            "docs": ("Documentation · JB - Jot Brief", "Everything JB - Jot Brief does and how to use it."),
        },
        "docs_md": HERE.parent / "DOCUMENTATION.en.md",
    },
}
FRAGS = {"home": "index.html", "projects": {"pt": "projetos.html", "en": "projects.html"}, "jb": "jot-brief.html"}

LAYOUT = """<!doctype html>
<html lang="{html_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:locale" content="{og_locale}">
<meta property="og:url" content="{site_url}{path}">
<link rel="canonical" href="{site_url}{path}">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/assets/favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
{alternates}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Playfair+Display:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css?v=17">
<link rel="stylesheet" href="/assets/posicoes.css?v=17">
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="{home}">João Barnabé</a>
  <div class="right">
    <nav aria-label="{nav_label}">
      <a href="{home}" {cur_home}>{nav_home}</a>
      <a href="{projects}" {cur_apps}>{nav_projects}</a>
    </nav>
    <details class="langsw">
      <summary aria-label="{switch_label}">{flag_now}</summary>
      <ul>
        <li><a href="{pt_href}" hreflang="pt-BR" lang="pt-BR">{flag_pt} Português</a></li>
        <li><a href="{en_href}" hreflang="en" lang="en">{flag_en} English</a></li>
      </ul>
    </details>
  </div>
</div></header>
<main id="conteudo">
{content}
</main>
<footer class="site"><div class="wrap">
  <p>© {year} João Barnabé · <a href="https://www.linkedin.com/in/joao-barnabe">LinkedIn</a> · <a href="mailto:joaobarna@gmail.com">{footer_email}</a></p>
</div></footer>
</body>
</html>
"""

POS: set[str] = set()


def sem_estilo_inline(html: str) -> str:
    """A CSP do site bloqueia style="..."; posicoes left/width viram classes (regras em posicoes.css)."""
    def troca(m: re.Match) -> str:
        cls, left, width = m.group(1), m.group(2), m.group(3)
        extra = " l" + left.replace(".", "_")
        POS.add(f".l{left.replace('.', '_')}{{left:{left}%}}")
        if width:
            extra += " w" + width.replace(".", "_")
            POS.add(f".w{width.replace('.', '_')}{{width:{width}%}}")
        return f'class="{cls}{extra}"'
    return re.sub(r'class="([^"]*)" style="left:([\d.]+)%(?:;width:([\d.]+)%)?"', troca, html)


def render(content: str, lang: str, page: str, path: str, alt_paths: dict[str, str]) -> str:
    """page: home | projects | jb | docs | 404. alt_paths: caminho equivalente em cada idioma."""
    L = LANGS[lang]
    title, desc = L["titles"][page]
    mark = lambda k: 'aria-current="page"' if page == k else ""  # noqa: E731
    if page in ("jb", "docs"):  # JB e a documentacao ficam dentro de Projetos: trilha de volta
        last = '<span aria-current="page">JB - Jot Brief</span>' if page == "jb" else (
            f'<a href="{L["paths"]["jb"]}">JB - Jot Brief</a> <span aria-hidden="true">/</span> '
            f'<span aria-current="page">{L["docs_label"]}</span>')
        content = (f'<div class="wrap"><nav class="crumbs" aria-label="{L["crumb_label"]}">'
                   f'<a href="{L["paths"]["projects"]}">{L["nav"]["projects"]}</a> <span aria-hidden="true">/</span> {last}</nav></div>\n'
                   + content)
    alternates = ""
    if "pt" in alt_paths and "en" in alt_paths:
        alternates = "\n".join(
            [f'<link rel="alternate" hreflang="{LANGS[k]["html"]}" href="{CFG["site_url"]}{alt_paths[k]}">' for k in ("pt", "en")]
            + [f'<link rel="alternate" hreflang="x-default" href="{CFG["site_url"]}{alt_paths["pt"]}">'])
    html = LAYOUT.format(
        html_lang=L["html"], og_locale=L["og"], title=title, description=desc, site_url=CFG["site_url"], path=path,
        alternates=alternates, content=content, year=date.today().year,
        home=L["paths"]["home"], projects=L["paths"]["projects"], nav_label=L["nav_label"],
        nav_home=L["nav"]["home"], nav_projects=L["nav"]["projects"], switch_label=L["switch_label"],
        cur_home=mark("home"), cur_apps=('aria-current="page"' if page in ("projects", "jb", "docs") else ""),
        flag_now=L["flag"], flag_pt=BR, flag_en=US,
        pt_href=alt_paths.get("pt", "/"), en_href=alt_paths.get("en", "/en/"), footer_email=L["footer_email"])
    for k, v in CFG.items():
        html = html.replace("{{" + k + "}}", str(v))
    return sem_estilo_inline(html)


def write(path: str, html: str) -> None:
    target = OUT / path.lstrip("/")
    if path.endswith("/"):
        target = target / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8", newline="\n")


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    shutil.copytree(SRC / "assets", OUT / "assets")
    shutil.copy(SRC / "assets" / "favicon.ico", OUT / "favicon.ico")  # navegadores pedem /favicon.ico por padrão
    urls: list[str] = []
    for page in ("home", "projects", "jb", "docs"):
        alt = {k: LANGS[k]["paths"][page] for k in LANGS}
        for lang, L in LANGS.items():
            path = L["paths"][page]
            if page == "docs":
                md = L["docs_md"].read_text(encoding="utf-8")
                body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists", "toc"])
                content = f'<div class="wrap"><article class="doc">{body}</article></div>'
            else:
                frag = FRAGS[page]
                frag = frag[lang] if isinstance(frag, dict) else frag
                content = (SRC / "pages" / lang / frag).read_text(encoding="utf-8")
            write(path, render(content, lang, page, path, alt))
            urls.append(path)
    # 404 bilíngue: a Cloudflare serve /404.html da raiz
    write("/404.html", render((SRC / "pages" / "pt" / "404.html").read_text(encoding="utf-8"), "pt", "404", "/404.html",
                              {"pt": "/", "en": "/en/"}))
    (OUT / "assets" / "posicoes.css").write_text("\n".join(sorted(POS)) + "\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {CFG['site_url']}/sitemap.xml\n", encoding="utf-8")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{CFG['site_url']}{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (OUT / "_redirects").write_text("/apps /projetos/ 301\n/apps/ /projetos/ 301\n/en /en/ 301\n", encoding="utf-8")
    (OUT / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  X-Frame-Options: DENY\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n"
        "  Content-Security-Policy: default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; base-uri 'self'; form-action 'none'\n"
        "/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n", encoding="utf-8")
    print("site gerado em", OUT, "|", sum(1 for _ in OUT.rglob("*") if _.is_file()), "arquivos")


if __name__ == "__main__":
    main()

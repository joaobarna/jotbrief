"""Gera o site estático em site/public/ (Cloudflare Pages publica essa pasta).

Uso (na raiz do projeto):  uv run --with markdown python site/build.py
Páginas: site/src/pages/*.html (só o miolo) + o layout abaixo; a documentação sai do DOCUMENTACAO.md.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
SRC, OUT = HERE / "src", HERE / "public"
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

LAYOUT = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:url" content="{site_url}{path}">
<link rel="canonical" href="{site_url}{path}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Playfair+Display:wght@600;700&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css?v=6">
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="/">João Barnabé</a>
  <nav aria-label="Principal">
    <a href="/" {cur_home}>Sobre</a>
    <a href="/projetos/" {cur_apps}>Projetos</a>
  </nav>
</div></header>
<main id="conteudo">
{content}
</main>
<footer class="site"><div class="wrap">
  <p>© {year} João Barnabé · <a href="https://www.linkedin.com/in/joao-barnabe">LinkedIn</a> · <a href="mailto:joaobarna@gmail.com">E-mail</a></p>
</div></footer>
</body>
</html>
"""

PAGES = [  # (fragmento, caminho de saída, título, descrição, menu ativo)
    ("index.html", "/", "João Barnabé · CFO e Diretor Financeiro",
     "CFO e Diretor Financeiro com mais de 8 anos em e-commerce de alto crescimento: Controladoria, Tesouraria, FP&A, 2 IPOs e integração de M&A.", "home"),
    ("projetos.html", "/projetos/", "Projetos · João Barnabé",
     "Projetos de João Barnabé: ferramentas para o dia a dia de finanças e gestão, abertas para quem quiser usar.", "apps"),
    ("jot-brief.html", "/jot-brief/", "JB - Jot Brief · Transcrição de reuniões para Windows",
     "Transcreva reuniões do Meet, Teams e Zoom sem bot, veja quem falou e converse com o Claude. 100% local.", "jb"),
    ("404.html", "/404.html", "Página não encontrada · João Barnabé", "Esta página não existe.", ""),
]


def render(content: str, path: str, title: str, desc: str, current: str) -> str:
    from datetime import date
    mark = lambda k: 'aria-current="page"' if current == k else ""  # noqa: E731
    if current in ("jb", "docs"):  # JB e a documentacao ficam dentro de Projetos: trilha de volta
        last = '<span aria-current="page">JB - Jot Brief</span>' if current == "jb" else (
            '<a href="/jot-brief/">JB - Jot Brief</a> <span aria-hidden="true">/</span> <span aria-current="page">Documentação</span>')
        content = ('<div class="wrap"><nav class="crumbs" aria-label="Você está em">'
                   f'<a href="/projetos/">Projetos</a> <span aria-hidden="true">/</span> {last}</nav></div>\n' + content)
    html = LAYOUT.format(title=title, description=desc, site_url=CFG["site_url"], path=path, content=content,
                         cur_home=mark("home"), cur_apps=("aria-current=\"page\"" if current in ("apps", "jb", "docs") else ""), year=date.today().year)
    for k, v in CFG.items():
        html = html.replace("{{" + k + "}}", str(v))
    return html


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
    for frag, path, title, desc, cur in PAGES:
        write(path, render((SRC / "pages" / frag).read_text(encoding="utf-8"), path, title, desc, cur))
    # documentação: vem do DOCUMENTACAO.md do projeto
    md = (HERE.parent / "DOCUMENTACAO.md").read_text(encoding="utf-8")
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists", "toc"])
    write("/jot-brief/docs/", render(f'<div class="wrap"><article class="doc">{body}</article></div>', "/jot-brief/docs/",
                                    "Documentação · JB - Jot Brief", "Tudo o que o JB - Jot Brief faz e como usar.", "docs"))
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {CFG['site_url']}/sitemap.xml\n", encoding="utf-8")
    urls = ["/", "/projetos/", "/jot-brief/", "/jot-brief/docs/"]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{CFG['site_url']}{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (OUT / "_redirects").write_text("/apps /projetos/ 301\n/apps/ /projetos/ 301\n", encoding="utf-8")
    (OUT / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  X-Frame-Options: DENY\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n"
        "  Content-Security-Policy: default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; base-uri 'self'; form-action 'none'\n"
        "/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n", encoding="utf-8")
    print("site gerado em", OUT, "|", sum(1 for _ in OUT.rglob("*") if _.is_file()), "arquivos")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build static site for blog.omeglechat.love from _posts/*.md."""
from __future__ import annotations

import html
import re
import shutil
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "_posts"
SITE = ROOT / "_site"
ASSETS = ROOT / "assets"

SITE_TITLE = "blog.omeglechat.love"
SITE_DESC = "Original love stories for omeglechat.love — strangers, second chances, and a happy ending."
SITE_URL = "https://blog.omeglechat.love"
MAIN_SITE = "https://omeglechat.love"
CHAT_URL = "https://omeglechat.love/chat"


def parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    raw_fm, body = parts[1], parts[2]
    data: dict = {}
    if yaml:
        data = yaml.safe_load(raw_fm) or {}
    else:
        # Minimal fallback parser
        for line in raw_fm.splitlines():
            if ":" not in line or line.strip().startswith("-"):
                continue
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip('"')
            if k == "tags":
                continue
            if k in ("series_part",):
                try:
                    data[k] = int(v)
                except ValueError:
                    data[k] = v
            else:
                data[k] = v
        tags = re.findall(r'^\s*-\s*"([^"]+)"', raw_fm, flags=re.M)
        if tags:
            data["tags"] = tags
    return data, body.lstrip("\n")


def md_to_html(md: str) -> str:
    """Small Markdown subset → HTML (headings, paragraphs, links, quotes, bold/italic)."""
    lines = md.splitlines()
    out: list[str] = []
    buf: list[str] = []
    in_quote = False

    def flush_para():
        nonlocal buf
        if not buf:
            return
        text = " ".join(buf).strip()
        buf = []
        if text:
            out.append(f"<p>{inline(text)}</p>")

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        s = re.sub(
            r"\[([^\]]+)\]\((https?://[^)]+)\)",
            r'<a href="\2" rel="noopener">\1</a>',
            s,
        )
        return s

    for line in lines:
        if line.startswith("## "):
            flush_para()
            if in_quote:
                out.append("</blockquote>")
                in_quote = False
            out.append(f"<h2>{inline(line[3:].strip())}</h2>")
            continue
        if line.startswith("# "):
            flush_para()
            if in_quote:
                out.append("</blockquote>")
                in_quote = False
            out.append(f"<h2>{inline(line[2:].strip())}</h2>")
            continue
        if line.startswith("> "):
            flush_para()
            if not in_quote:
                out.append("<blockquote>")
                in_quote = True
            out.append(f"<p>{inline(line[2:].strip())}</p>")
            continue
        if not line.strip():
            flush_para()
            if in_quote:
                out.append("</blockquote>")
                in_quote = False
            continue
        if in_quote and not line.startswith(">"):
            out.append("</blockquote>")
            in_quote = False
        buf.append(line.strip())
    flush_para()
    if in_quote:
        out.append("</blockquote>")
    return "\n".join(out)


def parse_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def load_posts() -> list[dict]:
    posts = []
    today = date.today()
    for path in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        if not meta.get("title"):
            continue
        d = parse_date(meta.get("date") or path.name[:10])
        if d > today:
            continue
        slug = meta.get("slug") or path.stem
        permalink = meta.get("permalink") or f"/truyen/{slug}/"
        if not str(permalink).endswith("/"):
            permalink = str(permalink) + "/"
        posts.append(
            {
                **meta,
                "date": d,
                "slug": slug,
                "permalink": permalink,
                "body_md": body,
                "body_html": md_to_html(body),
                "path": path,
            }
        )
    posts.sort(key=lambda p: (p["date"], p.get("series_part") or 0), reverse=True)
    return posts


def layout(title: str, body: str, *, description: str | None = None, canonical: str = "/") -> str:
    desc = html.escape(description or SITE_DESC)
    full_title = html.escape(f"{title} · {SITE_TITLE}" if title != SITE_TITLE else SITE_TITLE)
    canon = SITE_URL.rstrip("/") + canonical
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{full_title}</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="{html.escape(canon)}">
  <meta name="theme-color" content="#6b1838">
  <meta property="og:site_name" content="{SITE_TITLE}">
  <meta property="og:title" content="{full_title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="{html.escape(canon)}">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/blog.css">
</head>
<body>
  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="/">
        <strong>blog.omeglechat.love</strong>
        <small>meet the strangers · love stories</small>
      </a>
      <nav class="nav-links">
        <a href="/truyen/">All stories</a>
        <a href="/about/">About</a>
        <a class="nav-cta" href="{CHAT_URL}" data-cta="chat" data-cta-placement="header">Start chat</a>
      </nav>
    </div>
  </header>
  <main class="site-main">
    {body}
  </main>
  <footer class="site-footer">
    <div class="container footer-inner">
      <div class="footer-brand">
        <strong>blog.omeglechat.love</strong>
        <span>Original English love stories · tied to omeglechat.love</span>
      </div>
      <div class="footer-links">
        <a href="{MAIN_SITE}">omeglechat.love</a>
        <a href="{CHAT_URL}">Start chat</a>
        <a href="/about/">About</a>
        <a href="/truyen/">Archive</a>
      </div>
    </div>
    <div class="container footer-note">
      Stories are original syntheses. We do not reprint books, articles, or other people's text.
      © {date.today().year} omeglechat.love
    </div>
  </footer>
</body>
</html>
"""


def card_html(p: dict) -> str:
    cover = p.get("hero_image") or p.get("image") or ""
    title = html.escape(str(p["title"]))
    excerpt = html.escape(str(p.get("excerpt") or "")[:180])
    meta_bits = []
    if p.get("series_part"):
        meta_bits.append(f"Part {p['series_part']}")
    meta_bits.append(p["date"].strftime("%b %d, %Y"))
    if p.get("city"):
        meta_bits.append(str(p["city"]))
    meta = " · ".join(html.escape(x) for x in meta_bits)
    img = (
        f'<img class="post-card-cover" src="{html.escape(cover)}" alt="" loading="lazy">'
        if cover
        else '<div class="post-card-cover" aria-hidden="true"></div>'
    )
    return f"""
<a class="post-card" href="{html.escape(p['permalink'])}">
  {img}
  <div class="post-card-body">
    <div class="post-card-meta">{meta}</div>
    <h2>{title}</h2>
    <p>{excerpt}</p>
    <span class="read-more">Read story →</span>
  </div>
</a>
"""


def build_home(posts: list[dict]) -> str:
    featured = posts[0] if posts else None
    side = posts[1] if len(posts) > 1 else None
    feat = ""
    if featured:
        feat = f"""
<section class="featured container">
  <article class="featured-card">
    <p class="label">★ Read first · Part {html.escape(str(featured.get('series_part') or ''))}</p>
    <h2><a href="{html.escape(featured['permalink'])}">{html.escape(str(featured['title']))}</a></h2>
    <p>{html.escape(str(featured.get('excerpt') or '')[:200])}</p>
    <p><a class="btn btn-primary" href="{html.escape(featured['permalink'])}">Read now</a></p>
  </article>
  <article class="featured-side">
    <p class="post-card-meta">Also worth reading</p>
    <h2><a href="{html.escape(side['permalink']) if side else '/truyen/'}">{html.escape(str(side['title']) if side else 'Story archive')}</a></h2>
    <p>{html.escape(str((side or {}).get('excerpt') or 'The full late-night love-story series.'))[:180]}</p>
    <a class="btn btn-outline" href="/truyen/">See all</a>
  </article>
</section>
"""
    grid = "\n".join(card_html(p) for p in posts[:24])
    body = f"""
<div class="container">
  <section class="hero">
    <h1>Love stories, written in English</h1>
    <p class="hero-lead">Original short stories synthesized from meetings people have told in public — strangers, second chances, and a hello that arrives late. Adults only.</p>
    <div class="hero-actions">
      <a class="btn btn-primary" href="/truyen/">Browse stories</a>
      <a class="btn btn-outline" href="{CHAT_URL}">meet the strangers</a>
    </div>
  </section>
  <div class="notice">Each story is an original synthesis. We do not reprint copyrighted books or copy articles from the web.</div>
</div>
{feat}
<div class="container">
  <h2 class="section-title">Latest</h2>
  <div class="pill-row">
    <a class="pill active" href="/">All</a>
    <a class="pill" href="/truyen/">Series</a>
    <a class="pill" href="/about/">About</a>
  </div>
  <div class="post-grid">
    {grid}
  </div>
  <p style="margin-top:1.25rem"><a href="/truyen/">See all {len(posts)} stories →</a></p>
</div>
"""
    return layout(SITE_TITLE, body, canonical="/")


def build_archive(posts: list[dict]) -> str:
    grid = "\n".join(card_html(p) for p in posts)
    body = f"""
<div class="container">
  <section class="hero">
    <h1>Story archive</h1>
    <p class="hero-lead">{len(posts)} English love stories · happy endings · late nights and second meetings.</p>
  </section>
  <div class="ad-slot" aria-label="Advertisement"><div class="ad-placeholder">Advertisement</div></div>
  <div class="post-grid">{grid}</div>
</div>
"""
    return layout("Story archive", body, description="All love stories on blog.omeglechat.love", canonical="/truyen/")


def build_post(p: dict, by_slug: dict) -> str:
    cover = p.get("hero_image") or ""
    cover_html = (
        f'<div class="post-cover"><img src="{html.escape(cover)}" alt=""></div>'
        if cover
        else ""
    )
    prev_h = next_h = ""
    prev = str(p.get("prev_part") or "").strip('"')
    nxt = str(p.get("next_part") or "").strip('"')
    if prev:
        prev_h = f'<a href="{html.escape(prev)}">← Previous</a>'
    if nxt:
        next_h = f'<a href="{html.escape(nxt)}" style="margin-left:auto;text-align:right">Next →</a>'
    body = f"""
<article class="post-page container-narrow">
  <p class="post-kicker">{html.escape(str(p.get('series_name') or 'Love story'))} · Part {html.escape(str(p.get('series_part') or ''))}</p>
  <header class="post-header">
    <h1>{html.escape(str(p['title']))}</h1>
    <div class="post-meta">
      <time datetime="{p['date'].isoformat()}">{p['date'].strftime('%b %d, %Y')}</time>
      <span class="sep">·</span>
      <span>{html.escape(str(p.get('couple') or ''))}</span>
      <span class="sep">·</span>
      <span>{html.escape(str(p.get('city') or ''))}</span>
    </div>
  </header>
  {cover_html}
  <div class="ad-slot" aria-label="Advertisement"><div class="ad-placeholder">Advertisement</div></div>
  <div class="post-body">
    {p['body_html']}
  </div>
  <div class="chat-cta-box">
    <h3>Still awake?</h3>
    <p>If the story feels familiar, you can say hello to one stranger on omeglechat.love. Text, voice, or video. Adults only. No signup.</p>
    <a class="btn btn-primary" href="{CHAT_URL}" data-cta="chat" data-cta-placement="post">Start a free chat</a>
  </div>
  <nav class="post-nav">{prev_h}{next_h}</nav>
</article>
"""
    return layout(
        str(p["title"]),
        body,
        description=str(p.get("excerpt") or SITE_DESC)[:160],
        canonical=p["permalink"],
    )


def build_about() -> str:
    body = f"""
<article class="page-static container-narrow">
  <h1>About</h1>
  <p><strong>blog.omeglechat.love</strong> publishes original English love stories for omeglechat.love — late-night meetings, second chances, and a happy ending.</p>
  <p>We read meetings people have already told in public, then write a new story in our own words. We do not reprint books, lyrics, or articles.</p>
  <p>The characters are adults. The chat on <a href="{CHAT_URL}">omeglechat.love</a> is one stranger at a time, in the browser, with no account. We are not the old Omegle company.</p>
  <p><a class="btn btn-primary" href="/truyen/">Browse stories</a></p>
</article>
"""
    return layout("About", body, canonical="/about/")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_sitemap(posts: list[dict]) -> str:
    urls = ["/", "/truyen/", "/about/"] + [p["permalink"] for p in posts]
    items = []
    for u in urls:
        items.append(
            f"  <url><loc>{html.escape(SITE_URL.rstrip('/') + u)}</loc></url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(items)
        + "\n</urlset>\n"
    )


def main() -> int:
    if not POSTS_DIR.exists():
        print("No _posts/ — run sync-from-ngon-tinh.py first")
        return 1
    posts = load_posts()
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)

    # assets
    if ASSETS.exists():
        shutil.copytree(ASSETS, SITE / "assets")
    for name in ("CNAME", "robots.txt"):
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, SITE / name)

    write(SITE / "index.html", build_home(posts))
    write(SITE / "truyen" / "index.html", build_archive(posts))
    write(SITE / "about" / "index.html", build_about())
    write(SITE / "sitemap.xml", build_sitemap(posts))

    by_slug = {p["slug"]: p for p in posts}
    for p in posts:
        # permalink /truyen/slug/ → _site/truyen/slug/index.html
        rel = p["permalink"].strip("/")
        write(SITE / rel / "index.html", build_post(p, by_slug))

    publish_root()
    print(f"Built {len(posts)} posts → {SITE}")
    return 0


def publish_root() -> None:
    """GitHub Pages serves the branch root with Jekyll, which shows README.
    Copy the built pages to the root and disable Jekyll."""
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    for name in ("index.html", "sitemap.xml"):
        shutil.copy2(SITE / name, ROOT / name)
    for folder in ("truyen", "about"):
        dest = ROOT / folder
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(SITE / folder, dest)


if __name__ == "__main__":
    raise SystemExit(main())

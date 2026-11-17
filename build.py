#!/usr/bin/env python3
"""Build static site for blog.omeglechat.love from _posts/*.md."""
from __future__ import annotations

import html
import json
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
STORIES = "/stories/"


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
        slug = slugify(str(meta.get("slug") or path.stem))
        permalink = f"{STORIES}{slug}/"
        words = len(re.findall(r"[A-Za-z0-9']+", body))
        posts.append(
            {
                **meta,
                "date": d,
                "slug": slug,
                "permalink": permalink,
                "minutes": max(1, round(words / 220)),
                "body_md": body,
                "body_html": md_to_html(body),
                "path": path,
            }
        )
    posts.sort(key=lambda p: (p["date"], p.get("series_part") or 0), reverse=True)
    return posts


def clip(text: str, limit: int = 155) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return cut + "..."


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^part-\d+-", "", value)
    value = re.sub(r"^tap-\d+-", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "story"


def link_series(posts: list[dict]) -> None:
    ordered = sorted(posts, key=lambda p: int(p.get("series_part") or 0))
    for i, post in enumerate(ordered):
        post["prev_url"] = ordered[i - 1]["permalink"] if i else ""
        post["next_url"] = ordered[i + 1]["permalink"] if i + 1 < len(ordered) else ""
        post["prev_title"] = ordered[i - 1]["title"] if i else ""
        post["next_title"] = ordered[i + 1]["title"] if i + 1 < len(ordered) else ""


def layout(
    title: str,
    body: str,
    *,
    description: str | None = None,
    canonical: str = "/",
    og_type: str = "website",
    image: str | None = None,
    json_ld: list | None = None,
) -> str:
    raw_desc = clip(description or SITE_DESC)
    desc = html.escape(raw_desc)
    full_title = html.escape(title if title == SITE_TITLE else f"{title} · {SITE_TITLE}")
    canon = SITE_URL.rstrip("/") + canonical
    image_tags = ""
    if image:
        image_tags = f"""
  <meta property="og:image" content="{html.escape(image)}">
  <meta name="twitter:image" content="{html.escape(image)}">"""
    ld = ""
    if json_ld:
        ld = "\n".join(
            f'  <script type="application/ld+json">{json.dumps(block, ensure_ascii=False)}</script>'
            for block in json_ld
        )
        ld = "\n" + ld
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{full_title}</title>
  <meta name="description" content="{desc}">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="{html.escape(canon)}">
  <link rel="alternate" hreflang="en" href="{html.escape(canon)}">
  <meta name="theme-color" content="#6b1838">
  <meta property="og:site_name" content="{SITE_TITLE}">
  <meta property="og:title" content="{full_title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="{html.escape(canon)}">
  <meta property="og:type" content="{html.escape(og_type)}">
  <meta property="og:locale" content="en_US">{image_tags}
  <meta name="twitter:card" content="{"summary_large_image" if image else "summary"}">
  <meta name="twitter:title" content="{full_title}">
  <meta name="twitter:description" content="{desc}">{ld}
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
        <small>English love stories</small>
      </a>
      <nav class="nav-links" aria-label="Primary">
        <a href="/stories/">Stories</a>
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
        <a href="/stories/">Stories</a>
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
        f'<img class="post-card-cover" src="{html.escape(cover)}" alt="{title}" loading="lazy">'
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
    <span class="read-more">Read story</span>
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
    <h2><a href="{html.escape(side['permalink']) if side else '/stories/'}">{html.escape(str(side['title']) if side else 'Story archive')}</a></h2>
    <p>{html.escape(str((side or {}).get('excerpt') or 'The full late-night love-story series.'))[:180]}</p>
    <a class="btn btn-outline" href="/stories/">See all stories</a>
  </article>
</section>
"""
    grid = "\n".join(card_html(p) for p in posts[:24])
    body = f"""
<div class="container">
  <section class="hero">
    <h1>English love stories</h1>
    <p class="hero-lead">Short original stories about strangers, second chances, and the moment two adults recognize each other. Free to read. Adults only.</p>
    <div class="hero-actions">
      <a class="btn btn-primary" href="/stories/">Browse stories</a>
      <a class="btn btn-outline" href="{CHAT_URL}">Meet a stranger</a>
    </div>
  </section>
  <div class="notice">Each story is an original synthesis. We do not reprint copyrighted books or copy articles from the web.</div>
</div>
{feat}
<div class="container">
  <h2 class="section-title">Latest stories</h2>
  <div class="pill-row">
    <a class="pill active" href="/" aria-current="page">All</a>
    <a class="pill" href="/stories/">Archive</a>
    <a class="pill" href="/about/">About</a>
  </div>
  <div class="post-grid">
    {grid}
  </div>
  <p class="archive-link"><a href="/stories/">See all {len(posts)} stories</a></p>
</div>
"""
    return layout(
        "English Love Stories",
        body,
        description="Original English love stories about strangers, second chances, and late meetings. Read free short stories on blog.omeglechat.love.",
        canonical="/",
        json_ld=[
            {
                "@context": "https://schema.org",
                "@type": "Blog",
                "name": SITE_TITLE,
                "description": SITE_DESC,
                "url": SITE_URL + "/",
                "inLanguage": "en",
                "publisher": {"@type": "Organization", "name": "omeglechat.love", "url": MAIN_SITE},
            }
        ],
    )


def build_archive(posts: list[dict]) -> str:
    grid = "\n".join(card_html(p) for p in posts)
    body = f"""
<div class="container">
  <section class="hero">
    <h1>Love stories</h1>
    <p class="hero-lead">{len(posts)} original English short stories. Happy endings, late nights, and second meetings.</p>
  </section>
  <div class="post-grid">{grid}</div>
</div>
"""
    return layout(
        "Love Story Archive",
        body,
        description="Archive of original English love stories on blog.omeglechat.love. Strangers, reunions, and happy endings.",
        canonical=STORIES,
        json_ld=[breadcrumb([("Home", "/"), ("Stories", STORIES)])],
    )


def breadcrumb(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": name,
                "item": SITE_URL.rstrip("/") + path,
            }
            for i, (name, path) in enumerate(items)
        ],
    }


def crumb_html(items: list[tuple[str, str]]) -> str:
    parts = []
    for i, (name, path) in enumerate(items):
        if i == len(items) - 1:
            parts.append(f'<li aria-current="page">{html.escape(name)}</li>')
        else:
            parts.append(f'<li><a href="{html.escape(path)}">{html.escape(name)}</a></li>')
    return f'<nav class="breadcrumbs" aria-label="Breadcrumb"><ol>{"".join(parts)}</ol></nav>'


def build_post(p: dict, by_slug: dict) -> str:
    del by_slug
    cover = str(p.get("hero_image") or "")
    alt = html.escape(f"{p['title']}, a love story set in {p.get('city') or 'the city'}")
    cover_html = (
        f'<figure class="post-cover"><img src="{html.escape(cover)}" alt="{alt}" width="1200" height="675"></figure>'
        if cover
        else ""
    )
    prev_h = next_h = ""
    if p.get("prev_url"):
        prev_h = f'<a href="{html.escape(p["prev_url"])}"><span>Previous</span>{html.escape(str(p.get("prev_title") or ""))}</a>'
    if p.get("next_url"):
        next_h = f'<a class="next" href="{html.escape(p["next_url"])}"><span>Next</span>{html.escape(str(p.get("next_title") or ""))}</a>'
    crumbs = [
        ("Home", "/"),
        ("Stories", STORIES),
        (str(p["title"]), p["permalink"]),
    ]
    canon = SITE_URL.rstrip("/") + p["permalink"]
    article_ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": str(p["title"]),
        "description": clip(str(p.get("excerpt") or SITE_DESC)),
        "datePublished": p["date"].isoformat(),
        "dateModified": p["date"].isoformat(),
        "inLanguage": "en",
        "articleSection": "Love story",
        "mainEntityOfPage": canon,
        "url": canon,
        "author": {"@type": "Organization", "name": "OmegleChat editors"},
        "publisher": {"@type": "Organization", "name": "omeglechat.love", "url": MAIN_SITE},
        "keywords": ", ".join(p.get("tags") or []),
    }
    if cover:
        article_ld["image"] = cover
    body = f"""
<article class="post-page container-narrow">
  {crumb_html(crumbs)}
  <p class="post-kicker">{html.escape(str(p.get('series_name') or 'Love story'))} · Part {html.escape(str(p.get('series_part') or ''))}</p>
  <header class="post-header">
    <h1>{html.escape(str(p['title']))}</h1>
    <div class="post-meta">
      <time datetime="{p['date'].isoformat()}">{p['date'].strftime('%b %d, %Y')}</time>
      <span class="sep" aria-hidden="true">·</span>
      <span>{p['minutes']} min read</span>
      <span class="sep" aria-hidden="true">·</span>
      <span>{html.escape(str(p.get('couple') or ''))}</span>
      <span class="sep" aria-hidden="true">·</span>
      <span>{html.escape(str(p.get('city') or ''))}</span>
    </div>
  </header>
  {cover_html}
  <div class="post-body">
    {p['body_html']}
  </div>
  <aside class="chat-cta-box">
    <h2>Still awake?</h2>
    <p>Say hello to one stranger on omeglechat.love. Text, voice, or video. Adults only. No account.</p>
    <a class="btn btn-primary" href="{CHAT_URL}">Start a free chat</a>
  </aside>
  <nav class="post-nav" aria-label="More stories">{prev_h}{next_h}</nav>
</article>
"""
    return layout(
        str(p["title"]),
        body,
        description=str(p.get("excerpt") or SITE_DESC),
        canonical=p["permalink"],
        og_type="article",
        image=cover or None,
        json_ld=[article_ld, breadcrumb(crumbs)],
    )


def build_about() -> str:
    body = f"""
<article class="page-static container-narrow">
  <h1>About</h1>
  <p><strong>blog.omeglechat.love</strong> publishes original English love stories for omeglechat.love — late-night meetings, second chances, and a happy ending.</p>
  <p>We read meetings people have already told in public, then write a new story in our own words. We do not reprint books, lyrics, or articles.</p>
  <p>The characters are adults. The chat on <a href="{CHAT_URL}">omeglechat.love</a> is one stranger at a time, in the browser, with no account. We are not the old Omegle company.</p>
  <p><a class="btn btn-primary" href="/stories/">Browse stories</a></p>
</article>
"""
    return layout(
        "About",
        body,
        description="About blog.omeglechat.love, the English love-story site for omeglechat.love. Original stories. Adults only.",
        canonical="/about/",
        json_ld=[breadcrumb([("Home", "/"), ("About", "/about/")])],
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_sitemap(posts: list[dict]) -> str:
    rows = [("/", date.today())]
    rows.append((STORIES, posts[0]["date"] if posts else date.today()))
    rows.append(("/about/", date.today()))
    rows.extend((p["permalink"], p["date"]) for p in posts)
    items = []
    for path, stamp in rows:
        items.append(
            "  <url>"
            f"<loc>{html.escape(SITE_URL.rstrip('/') + path)}</loc>"
            f"<lastmod>{stamp.isoformat()}</lastmod>"
            "</url>"
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
    link_series(posts)
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
    write(SITE / "stories" / "index.html", build_archive(posts))
    write(SITE / "about" / "index.html", build_about())
    write(SITE / "sitemap.xml", build_sitemap(posts))
    write_legacy_redirects()

    by_slug = {p["slug"]: p for p in posts}
    for p in posts:
        # permalink /truyen/slug/ → _site/truyen/slug/index.html
        rel = p["permalink"].strip("/")
        write(SITE / rel / "index.html", build_post(p, by_slug))

    publish_root()
    print(f"Built {len(posts)} posts → {SITE}")
    return 0


def publish_root() -> None:
    """GitHub Pages serves the branch root. Copy the built English site there."""
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    for name in ("index.html", "sitemap.xml"):
        shutil.copy2(SITE / name, ROOT / name)
    for folder in ("stories", "about", "truyen"):
        dest = ROOT / folder
        src = SITE / folder
        if dest.exists():
            shutil.rmtree(dest)
        if src.exists():
            shutil.copytree(src, dest)


def write_legacy_redirects() -> None:
    """Old Vietnamese paths keep a canonical pointer to the English URL."""
    targets = {
        "/truyen/": STORIES,
        "/truyen/part-001-the-other-chair/": "/stories/the-other-chair/",
        "/truyen/part-002-the-late-platform/": "/stories/the-late-platform/",
    }
    for old, new in targets.items():
        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Moved</title>
  <link rel="canonical" href="{SITE_URL.rstrip('/')}{new}">
  <meta http-equiv="refresh" content="0; url={new}">
  <script>location.replace({json.dumps(new)});</script>
</head>
<body>
  <p>This page has moved. <a href="{html.escape(new)}">Continue to the story</a>.</p>
</body>
</html>
"""
        rel = old.strip("/")
        write(SITE / rel / "index.html", page)


if __name__ == "__main__":
    raise SystemExit(main())

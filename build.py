#!/usr/bin/env python3
"""Build the multilingual static site into ./public.

    python build.py

No required packages. If Pillow is installed (pip install pillow), it also
draws a social-share image for every article.

  site.json            settings (name, ads, affiliate links, news feeds)
  i18n.json            interface text for each language
  content/<lang>/posts articles in Markdown, one file per article
  content/<lang>/pages about, privacy, imprint
  data/headlines-<lang>.json   written by fetch_news.py

A translation is linked to the original by having the same file name.
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import textwrap
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "public"
CFG = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
I18N = json.loads((ROOT / "i18n.json").read_text(encoding="utf-8"))
BASE = os.environ.get("SITE_BASE_URL", CFG["base_url"]).rstrip("/")
PREFIX = urlparse(BASE).path.rstrip("/")  # e.g. "/my-repo" on GitHub Pages
NAME = CFG["name"]
LANGS = CFG["languages"]
DEFAULT = LANGS[0]

POSTS = {}  # lang -> {key: doc}
PAGES = {}  # lang -> {key: doc}
CUR = {"lang": DEFAULT}  # language being rendered (used by the Markdown link resolver)


def u(path: str) -> str:
    """Site-relative link that also works when hosted in a subfolder."""
    return PREFIX + path


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def T(lang: str, key: str, **kw) -> str:
    s = I18N.get(lang, {}).get(key, I18N[DEFAULT].get(key, key))
    return s.format(**kw) if kw and isinstance(s, str) else s


def lang_root(lang: str) -> str:
    return "/" if lang == DEFAULT else f"/{lang}/"


def path_of(lang: str, ref: str):
    """Resolve 'home', 'news', 'guides', 'post:<key>' or 'page:<key>' to a path.
    Returns None if that page does not exist in this language."""
    root = lang_root(lang)
    if ref == "home":
        return root
    if ref in ("news", "guides"):
        return root + T(lang, "slug_" + ref) + "/"
    kind, _, key = ref.partition(":")
    if kind == "page" and key in ("news", "guides", "home"):
        return path_of(lang, key)
    doc = (POSTS if kind == "post" else PAGES).get(lang, {}).get(key)
    return doc["path"] if doc else None


def resolve(lang: str, ref: str) -> str:
    """Like path_of, but falls back to the default language, then the homepage."""
    return path_of(lang, ref) or path_of(DEFAULT, ref) or lang_root(lang)


def fmt_date(lang: str, iso: str) -> str:
    try:
        d = dt.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return iso
    return T(lang, "date_fmt").format(M=T(lang, "months")[d.month - 1], d=d.day, y=d.year)


# --------------------------------------------------------------------------
# Minimal Markdown
# --------------------------------------------------------------------------
def _link(m):
    text, href = m[1], m[2].replace('"', "%22")
    if re.match(r"(post|page):", href):
        return f'<a href="{u(resolve(CUR["lang"], href))}">{text}</a>'
    external = href.startswith("http") and not href.startswith(BASE)
    attrs = ' target="_blank" rel="noopener"' if external else ""
    if not external and href.startswith("/"):
        href = u(href)
    return f'<a href="{href}"{attrs}>{text}</a>'


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def markdown(text: str, lang: str) -> str:
    CUR["lang"] = lang
    out, para, quote = [], [], []
    lst = None  # (tag, [items])
    in_comment = False

    def flush():
        nonlocal para, quote, lst
        if para:
            # a single line break in the source becomes a line break (handy for addresses)
            out.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
            para = []
        if quote:
            out.append("<blockquote><p>" + inline(" ".join(quote)) + "</p></blockquote>")
            quote = []
        if lst:
            items = "".join(f"<li>{inline(i)}</li>" for i in lst[1])
            out.append(f"<{lst[0]}>{items}</{lst[0]}>")
            lst = None

    for line in text.splitlines():
        s = line.strip()
        # <!-- editor notes --> are never published
        if in_comment or s.startswith("<!--"):
            in_comment = "-->" not in s
            continue
        if not s:
            flush()
            continue
        if s == "[[ad]]":
            flush(); out.append(ad(lang, "in_article")); continue
        if s == "[[affiliate]]":
            flush(); out.append(affiliate_box(lang)); continue
        if s == "[[newsletter]]":
            flush(); out.append(newsletter(lang)); continue
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if m:
            flush()
            level = max(2, len(m[1]))
            slug = re.sub(r"[^\w]+", "-", m[2].lower()).strip("-")
            out.append(f'<h{level} id="{esc(slug)}">{inline(m[2])}</h{level}>')
            continue
        m = re.match(r"[-*]\s+(.*)", s) or re.match(r"\d+[.)]\s+(.*)", s)
        if m:
            tag = "ul" if s[0] in "-*" else "ol"
            if para or quote or (lst and lst[0] != tag):
                flush()
            if not lst:
                lst = (tag, [])
            lst[1].append(m[1])
            continue
        if s.startswith(">"):
            if para or lst:
                flush()
            quote.append(s.lstrip("> "))
            continue
        if lst:
            flush()
        para.append(s)
    flush()
    return "\n".join(out)


def read_doc(path: Path, lang: str):
    raw = path.read_text(encoding="utf-8")
    meta, body = {}, raw
    if raw.startswith("---"):
        _, fm, body = raw.split("---", 2)
        for line in fm.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    meta["key"] = path.stem
    meta.setdefault("slug", path.stem)
    meta["lang"] = lang
    meta["path"] = lang_root(lang) + meta["slug"] + "/"
    meta["body_md"] = body
    return meta


def load_content():
    for lang in LANGS:
        POSTS[lang], PAGES[lang] = {}, {}
        for kind, store in (("posts", POSTS), ("pages", PAGES)):
            folder = ROOT / "content" / lang / kind
            for f in sorted(folder.glob("*.md")) if folder.exists() else []:
                d = read_doc(f, lang)
                if d.get("draft", "false").lower() != "true":
                    store[lang][d["key"]] = d


def sorted_posts(lang):
    posts = list(POSTS[lang].values())
    posts.sort(key=lambda p: p.get("updated", p.get("date", "")), reverse=True)
    posts.sort(key=lambda p: p.get("featured", "false").lower() == "true", reverse=True)
    return posts


# --------------------------------------------------------------------------
# Money blocks
# --------------------------------------------------------------------------
def ad(lang: str, slot_name: str) -> str:
    client = CFG.get("adsense_client", "").strip()
    slot = CFG.get("ad_slots", {}).get(slot_name, "").strip()
    label = f'<span class="ad-label">{esc(T(lang, "advertisement"))}</span>'
    if client and slot:
        return (
            f'<div class="ad ad-{esc(slot_name)}">{label}'
            '<ins class="adsbygoogle" style="display:block" '
            f'data-ad-client="{esc(client)}" data-ad-slot="{esc(slot)}" '
            'data-ad-format="auto" data-full-width-responsive="true"></ins>'
            "<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>"
        )
    if CFG.get("show_ad_placeholders", True):
        return f'<div class="ad ad-{esc(slot_name)}">{label}<div class="ad-box"></div></div>'
    return ""


def affiliate_url(url: str):
    """Adds your Amazon tracking tag for that Amazon store. Returns (url, is_amazon)."""
    host = urlparse(url).netloc.replace("www.", "")
    tag = CFG.get("amazon_tags", {}).get(host, "").strip()
    if tag and "tag=" not in url:
        url += ("&" if "?" in url else "?") + "tag=" + tag
    return url, bool(tag)


def affiliate_box(lang: str) -> str:
    links = CFG.get("affiliate_links", {})
    links = links.get(lang) or links.get(DEFAULT) or []
    if not links:
        return ""
    items, amazon = [], False
    for l in links:
        href, tagged = affiliate_url(l["url"])
        amazon |= tagged
        items.append(f'<li><a href="{esc(href)}" target="_blank" rel="sponsored nofollow noopener">{esc(l["label"])}</a></li>')
    note = T(lang, "aff_amazon") if amazon else T(lang, "aff_generic")
    return (f'<aside class="shop"><h2 class="rubric">{esc(T(lang, "where_to_buy"))}</h2>'
            f'<ul>{"".join(items)}</ul><p class="fine">{esc(note)}</p></aside>')


def newsletter(lang: str) -> str:
    url = CFG.get("newsletter_url", "").strip()
    if not url:
        return ""
    return (f'<section class="newsletter"><h2 class="rubric">{esc(T(lang, "nl_title"))}</h2>'
            f'<p>{esc(T(lang, "nl_text"))}</p>'
            f'<a class="btn" href="{esc(url)}" target="_blank" rel="noopener">{esc(T(lang, "nl_cta"))}</a></section>')


# --------------------------------------------------------------------------
# Social share images (needs Pillow; skipped quietly without it)
# --------------------------------------------------------------------------
FONT_SERIF = ["C:/Windows/Fonts/georgiab.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"]
FONT_SANS = ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]


def _font(candidates, size):
    from PIL import ImageFont
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default(size=size)


def share_image(name: str, title: str, label: str = ""):
    """Draws a 1200x630 image for link previews. Returns its absolute URL or ''."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return ""
    W, H, M = 1200, 630, 72
    img = Image.new("RGB", (W, H), "#f6f4ef")
    d = ImageDraw.Draw(img)
    d.text((M, 58), NAME, font=_font(FONT_SERIF, 46), fill="#16140f")
    d.rectangle([M, 132, W - M, 135], fill="#16140f")
    y = 172
    if label:
        d.text((M, y), label.upper(), font=_font(FONT_SANS, 26), fill="#b3122e")
        y += 52
    for size, width in ((76, 26), (64, 31), (54, 37)):
        lines = textwrap.wrap(title, width=width)
        if len(lines) <= 4:
            break
    f = _font(FONT_SERIF, size)
    for line in lines[:4]:
        d.text((M, y), line, font=f, fill="#16140f")
        y += int(size * 1.18)
    d.rectangle([0, H - 18, W, H], fill="#b3122e")
    target = OUT / "og" / f"{name}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target, optimize=True)
    return f"{BASE}/og/{name}.png"


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
GLOBE = ('<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" '
         'stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9'
         'M12 3c-2.5 2.6-3.8 5.6-3.8 9s1.3 6.4 3.8 9"/></svg>')


def lang_switcher(lang: str, alternates: dict) -> str:
    items = []
    for l in LANGS:
        href = alternates.get(l) or lang_root(l)
        cur = ' aria-current="true"' if l == lang else ""
        items.append(f'<li><a href="{u(href)}" hreflang="{l}" lang="{l}" data-lang="{l}"{cur}>'
                     f'{esc(T(l, "lang_name"))}</a></li>')
    return (f'<details class="lang"><summary aria-label="{esc(T(lang, "language"))}">{GLOBE}'
            f'<span>{lang.upper()}</span></summary><ul>{"".join(items)}</ul></details>')


def page(lang, ref, title, desc, body, alternates=None, og_type="website", jsonld=None,
         full_title=None, image=""):
    path = resolve(lang, ref) if ref else "/404.html"
    alternates = alternates if alternates is not None else {l: resolve(l, ref) for l in LANGS}
    canonical = BASE + path
    t = full_title or f"{title} | {NAME}"

    head = []
    if ref:
        for l, p in alternates.items():
            head.append(f'<link rel="alternate" hreflang="{l}" href="{esc(BASE + p)}">')
        if DEFAULT in alternates:
            head.append(f'<link rel="alternate" hreflang="x-default" href="{esc(BASE + alternates[DEFAULT])}">')
    if image:
        head.append(f'<meta property="og:image" content="{esc(image)}">'
                    '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">')
    if CFG.get("google_site_verification"):
        head.append(f'<meta name="google-site-verification" content="{esc(CFG["google_site_verification"])}">')
    if CFG.get("adsense_client"):
        head.append('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                    f'?client={esc(CFG["adsense_client"])}" crossorigin="anonymous"></script>')
    if CFG.get("goatcounter_code"):
        head.append(f'<script data-goatcounter="https://{esc(CFG["goatcounter_code"])}.goatcounter.com/count" '
                    'async src="https://gc.zgo.at/count.js"></script>')
    if jsonld:
        head.append(f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>')

    current = ' aria-current="page"'
    nav = "".join(
        f'<a href="{u(resolve(lang, r))}"{current if r == ref else ""}>{esc(label)}</a>'
        for label, r in T(lang, "nav")
    )
    hints = {l: T(l, "read_in") for l in LANGS}
    foot_links = " &middot; ".join(
        f'<a href="{u(d["path"])}">{esc(d["title"])}</a>' for d in PAGES[lang].values()
    )
    return f"""<!doctype html>
<html lang="{lang}" data-hints="{esc(json.dumps(hints, ensure_ascii=False))}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="max-image-preview:large">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:site_name" content="{esc(NAME)}">
<meta property="og:locale" content="{T(lang, 'locale')}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="color-scheme" content="light dark">
<link rel="alternate" type="application/rss+xml" title="{esc(NAME)}" href="{u(lang_root(lang) + 'feed.xml')}">
<link rel="icon" href="{u('/static/favicon.svg')}" type="image/svg+xml">
<link rel="stylesheet" href="{u('/static/style.css')}">
{chr(10).join(head)}
</head>
<body>
<header class="masthead">
  <div class="wrap mast">
    <span class="dateline" data-today>{fmt_date(lang, dt.date.today().isoformat())}</span>
    <a class="wordmark" href="{u(lang_root(lang))}">{esc(NAME)}</a>
    <div class="mast-tools">{lang_switcher(lang, alternates)}</div>
  </div>
  <nav class="wrap mainnav" aria-label="Sections">{nav}</nav>
</header>
<div class="ticker" data-launch="{esc(CFG.get('launch_date_local', ''))}" data-out="{esc(T(lang, 'ticker_out'))}">
  <div class="wrap">
    <span class="ticker-tag">GTA VI</span>
    <span class="ticker-text">{esc(T(lang, 'ticker'))}<span data-cd></span></span>
    <a href="{u(resolve(lang, 'post:gta-6-release-date-time'))}">{esc(T(lang, 'ticker_link'))}</a>
  </div>
</div>
<main class="wrap">
{body}
</main>
<footer class="foot">
  <div class="wrap">
    <p class="foot-name">{esc(NAME)}</p>
    <p>{esc(T(lang, 'footer'))}</p>
    <p>{foot_links} &middot; <a href="{u(lang_root(lang) + 'feed.xml')}">RSS</a></p>
  </div>
</footer>
<script src="{u('/static/app.js')}" defer></script>
</body>
</html>
"""


def headline_list(lang, items) -> str:
    if not items:
        return f'<p class="fine">{esc(T(lang, "no_headlines"))}</p>'
    rows = []
    for h in items:
        pub = esc(h.get("published", ""))
        rows.append(
            f'<li><time datetime="{pub}">{fmt_date(lang, pub)}</time>'
            f'<div><a href="{esc(h["url"])}" target="_blank" rel="noopener nofollow">{esc(h["title"])}</a>'
            f'<span class="src">{esc(h.get("source", ""))}</span></div></li>'
        )
    return '<ol class="river">' + "".join(rows) + "</ol>"


def post_list(posts, numbered=False, dek=True) -> str:
    rows = []
    for p in posts:
        rows.append(
            f'<li><span class="label">{esc(p.get("category", ""))}</span>'
            f'<a class="hed" href="{u(p["path"])}">{esc(p["title"])}</a>'
            + (f'<p class="dek">{esc(p.get("description", ""))}</p>' if dek else "")
            + "</li>"
        )
    tag = "ol" if numbered else "ul"
    return f'<{tag} class="stories{" numbered" if numbered else ""}">' + "".join(rows) + f"</{tag}>"


def sidebar(lang, posts=None) -> str:
    most = ""
    if posts:
        most = (f'<section><h2 class="rubric">{esc(T(lang, "explainers"))}</h2>'
                f'{post_list(posts[:5], numbered=True, dek=False)}</section>')
    return f'<aside class="side">{most}{newsletter(lang)}{ad(lang, "sidebar")}{affiliate_box(lang)}</aside>'


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def write(path: str, content: str):
    target = OUT / path.lstrip("/")
    if path.endswith("/"):
        target = target / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def build_language(lang: str, sitemap: list):
    posts = sorted_posts(lang)
    hfile = ROOT / "data" / f"headlines-{lang}.json"
    headlines = json.loads(hfile.read_text(encoding="utf-8")) if hfile.exists() else []
    root = lang_root(lang)
    default_img = share_image(f"{lang}-home", T(lang, "tagline"))

    # Home
    lead_html = ""
    if posts:
        lead, rest = posts[0], posts[1:]
        lead_html = f"""
<section class="front">
  <article class="lead">
    <span class="label">{esc(lead.get("category", ""))}</span>
    <h1><a href="{u(lead['path'])}">{esc(lead["title"])}</a></h1>
    <p class="dek">{esc(lead.get("description", ""))}</p>
    <p class="byline">{esc(T(lang, "updated"))} {fmt_date(lang, lead.get("updated", lead.get("date", "")))}</p>
  </article>
  <div class="front-side">{post_list(rest[:3])}</div>
</section>"""
    home = f"""
{lead_html}
{ad(lang, "home_top")}
<div class="grid">
  <section>
    <h2 class="rubric">{esc(T(lang, "latest"))} <a class="more" href="{u(resolve(lang, 'news'))}">{esc(T(lang, "all_news"))}</a></h2>
    {headline_list(lang, headlines[:15])}
  </section>
  {sidebar(lang, posts)}
</div>
"""
    write(root, page(lang, "home", NAME, T(lang, "tagline"), home, image=default_img,
                     full_title=f"{NAME}: {T(lang, 'tagline')}",
                     jsonld={"@context": "https://schema.org", "@type": "WebSite", "name": NAME,
                             "url": BASE + root, "inLanguage": lang}))

    # News
    news = f"""
<header class="page-head">
  <h1>{esc(T(lang, "news_title"))}</h1>
  <p class="dek">{esc(T(lang, "news_dek"))}</p>
</header>
<div class="grid"><section>{headline_list(lang, headlines[:CFG.get("max_headlines", 80)])}</section>{sidebar(lang, posts)}</div>
"""
    write(resolve(lang, "news"), page(lang, "news", T(lang, "news_title"), T(lang, "news_meta"), news, image=default_img))

    # Guides
    guides = f"""
<header class="page-head">
  <h1>{esc(T(lang, "guides_title"))}</h1>
  <p class="dek">{esc(T(lang, "guides_dek"))}</p>
</header>
<div class="grid"><section>{post_list(posts)}</section>{sidebar(lang)}</div>
"""
    write(resolve(lang, "guides"), page(lang, "guides", T(lang, "guides_title"), T(lang, "guides_meta"), guides, image=default_img))
    today = dt.date.today().isoformat()
    sitemap += [(root, today), (resolve(lang, "news"), today), (resolve(lang, "guides"), today)]

    # Articles
    for p in posts:
        ref = "post:" + p["key"]
        alternates = {l: POSTS[l][p["key"]]["path"] for l in LANGS if p["key"] in POSTS[l]}
        updated = p.get("updated", p.get("date", ""))
        others = [q for q in posts if q is not p]
        img = share_image(f"{lang}-{p['key']}", p["title"], p.get("category", ""))
        art = f"""
<div class="grid">
<article class="post">
  <header class="post-head">
    <span class="label">{esc(p.get("category", ""))}</span>
    <h1>{esc(p["title"])}</h1>
    <p class="dek">{esc(p.get("description", ""))}</p>
    <p class="byline">{esc(T(lang, "by_staff", name=NAME))} &middot; {esc(T(lang, "updated"))} <time datetime="{esc(updated)}">{fmt_date(lang, updated)}</time></p>
  </header>
  <div class="body">{markdown(p["body_md"], lang)}</div>
  {newsletter(lang)}
  <section class="related"><h2 class="rubric">{esc(T(lang, "read_next"))}</h2>{post_list(others[:3])}</section>
</article>
{sidebar(lang, others)}
</div>
"""
        ld = {"@context": "https://schema.org", "@type": "Article", "headline": p["title"],
              "description": p.get("description", ""), "inLanguage": lang,
              "datePublished": p.get("date", ""), "dateModified": updated,
              "mainEntityOfPage": BASE + p["path"], "author": {"@type": "Organization", "name": NAME},
              "publisher": {"@type": "Organization", "name": NAME}}
        if img:
            ld["image"] = [img]
        write(p["path"], page(lang, ref, p["title"], p.get("description", ""), art, alternates=alternates,
                              og_type="article", jsonld=ld, image=img))
        sitemap.append((p["path"], updated))

    # About, privacy, imprint
    for d in PAGES[lang].values():
        alternates = {l: PAGES[l][d["key"]]["path"] for l in LANGS if d["key"] in PAGES[l]}
        body = f'<article class="post narrow"><h1>{esc(d["title"])}</h1>{markdown(d["body_md"], lang)}</article>'
        write(d["path"], page(lang, "page:" + d["key"], d["title"], d.get("description", ""), body, alternates=alternates))
        sitemap.append((d["path"], today))

    # RSS
    items = ""
    for p in posts[:20]:
        d = dt.datetime.fromisoformat(p.get("date", today)[:10]).replace(tzinfo=dt.timezone.utc)
        items += (f"<item><title>{esc(p['title'])}</title><link>{esc(BASE + p['path'])}</link>"
                  f"<guid>{esc(BASE + p['path'])}</guid><pubDate>{format_datetime(d)}</pubDate>"
                  f"<description>{esc(p.get('description', ''))}</description></item>")
    write(root + "feed.xml", f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
                             f"<title>{esc(NAME)}</title><link>{esc(BASE + root)}</link><language>{lang}</language>"
                             f"<description>{esc(T(lang, 'tagline'))}</description>{items}</channel></rss>")
    return len(posts), len(headlines)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    load_content()

    sitemap, report = [], []
    for lang in LANGS:
        n_posts, n_head = build_language(lang, sitemap)
        report.append(f"{lang}: {n_posts} articles, {n_head} headlines")

    write("/404.html", page(DEFAULT, None, T(DEFAULT, "not_found"), T(DEFAULT, "not_found"),
                            f'<header class="page-head"><h1>{esc(T(DEFAULT, "not_found"))}</h1>'
                            f'<p class="dek"><a href="{u("/")}">{esc(T(DEFAULT, "back_home"))}</a></p></header>',
                            alternates={}))
    sm = "".join(f"<url><loc>{esc(BASE + p)}</loc><lastmod>{str(d)[:10]}</lastmod></url>" for p, d in sitemap)
    write("/sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>')
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    client = CFG.get("adsense_client", "").strip()
    if client:
        write("/ads.txt", f"google.com, {client.replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n")
    print("Built", " | ".join(report))


if __name__ == "__main__":
    main()

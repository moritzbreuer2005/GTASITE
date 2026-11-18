#!/usr/bin/env python3
"""Pull the latest GTA 6 headlines for every language in site.json.

    python fetch_news.py

Uses Google News in each language's edition (German news for the German
site, and so on). Saves only titles and links, never full articles, to
data/headlines-<lang>.json, merged with what was saved before.
"""
import email.utils
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
ATOM = "{http://www.w3.org/2005/Atom}"
KEYWORDS = [k.lower() for k in CFG.get("news_keywords", [])]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; news-reader/1.0)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def parse_date(s: str) -> str:
    if not s:
        return datetime.now(timezone.utc).isoformat()
    try:
        d = email.utils.parsedate_to_datetime(s)  # RSS style
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))  # Atom style
        except ValueError:
            return datetime.now(timezone.utc).isoformat()
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()


def parse(feed_bytes: bytes, default_source: str):
    root = ET.fromstring(feed_bytes)
    items = []
    for it in root.iter("item"):  # RSS 2.0
        title = (it.findtext("title") or "").strip()
        source = (it.findtext("source") or default_source).strip()
        if source and title.endswith(" - " + source):  # Google News appends " - Publisher"
            title = title[: -len(" - " + source)]
        items.append({"title": title, "url": (it.findtext("link") or "").strip(),
                      "source": source, "published": parse_date(it.findtext("pubDate"))})
    for e in root.iter(ATOM + "entry"):  # Atom
        link = e.find(ATOM + "link")
        items.append({"title": (e.findtext(ATOM + "title") or "").strip(),
                      "url": link.get("href", "") if link is not None else "",
                      "source": default_source,
                      "published": parse_date(e.findtext(ATOM + "updated") or e.findtext(ATOM + "published"))})
    return items


def feeds_for(lang: str):
    q = urllib.parse.quote_plus(CFG.get("news_query", "GTA 6"))
    edition = CFG.get("news_editions", {}).get(lang)
    if edition:
        yield "Google News", f"https://news.google.com/rss/search?q={q}&{edition}"
    for extra in CFG.get("extra_feeds", {}).get(lang, []):
        yield extra.get("source", "Web"), extra["url"]


def key(title: str) -> str:
    return re.sub(r"[^\w]", "", title.lower())[:80]


def update(lang: str):
    out = ROOT / "data" / f"headlines-{lang}.json"
    existing = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    fresh = []
    for source, url in feeds_for(lang):
        try:
            got = parse(fetch(url), source)
            fresh += got
        except Exception as exc:  # one broken feed should not stop the others
            print(f"[{lang}] skipped {source}: {exc}")

    seen, merged = set(), []
    for h in sorted(fresh + existing, key=lambda h: h["published"], reverse=True):
        k = key(h["title"])
        t = h["title"].lower()
        if not h["title"] or not h["url"].startswith("http") or k in seen:
            continue
        if KEYWORDS and not any(w in t for w in KEYWORDS):
            continue
        seen.add(k)
        merged.append(h)

    merged = merged[: max(CFG.get("max_headlines", 80), 100)]
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(merged, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[{lang}] {len(fresh)} fetched, {len(merged)} saved")


if __name__ == "__main__":
    for lang in CFG["languages"]:
        update(lang)

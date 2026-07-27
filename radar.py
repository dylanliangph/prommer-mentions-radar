#!/usr/bin/env python3
"""Mentions radar for prommer.net — fetches public mentions of Thomas Prommer /
We The Flywheel and renders a static dashboard page.

Stdlib only, no dependencies. Each source fails independently: a blocked or
down feed logs a warning and the run still ships whatever the other sources
returned.
"""

import html as htmllib
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import escape
from pathlib import Path

QUERIES = ['"Thomas Prommer"', '"We The Flywheel"', "prommer.net"]
OUT_DIR = Path(__file__).parent / "docs"
STATE_FILE = OUT_DIR / "mentions.json"
UA = "mentions-radar/1.0 (personal brand monitor; github.com/dylanliangph)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def clean(text):
    """Strip tags and decode HTML entities."""
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", text)).strip()


def relevant(q, *texts):
    """Exact-phrase check — search APIs match loose word combos otherwise."""
    phrase = q.strip('"').lower()
    return any(phrase in t.lower() for t in texts if t)


def fetch_hn():
    """Hacker News via Algolia search API — stories and comments."""
    items = []
    for q in QUERIES:
        for tag in ("story", "comment"):
            url = ("https://hn.algolia.com/api/v1/search_by_date?query="
                   + urllib.parse.quote(q) + f"&tags={tag}&hitsPerPage=10")
            data = json.loads(get(url))
            for h in data.get("hits", []):
                title = clean(h.get("title") or h.get("story_title") or "(comment)")
                text = clean(h.get("comment_text") or "")
                if not relevant(q, title, text):
                    continue
                items.append({
                    "source": "Hacker News",
                    "title": title,
                    "snippet": text[:280],
                    "url": f"https://news.ycombinator.com/item?id={h['objectID']}",
                    "author": h.get("author", ""),
                    "date": h.get("created_at", "")[:10],
                    "query": q,
                })
    return items


def fetch_bluesky():
    """Bluesky public search API. Blocked from some networks — that's fine."""
    items = []
    for q in QUERIES:
        url = ("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q="
               + urllib.parse.quote(q) + "&limit=10")
        data = json.loads(get(url))
        for p in data.get("posts", []):
            handle = p.get("author", {}).get("handle", "")
            rkey = p.get("uri", "").rsplit("/", 1)[-1]
            if not relevant(q, p.get("record", {}).get("text", "")):
                continue
            items.append({
                "source": "Bluesky",
                "title": p.get("record", {}).get("text", "")[:120],
                "snippet": p.get("record", {}).get("text", "")[:280],
                "url": f"https://bsky.app/profile/{handle}/post/{rkey}",
                "author": handle,
                "date": p.get("record", {}).get("createdAt", "")[:10],
                "query": q,
            })
    return items


def fetch_google_news():
    """Google News RSS. Titles + links only, personal/demo use."""
    q = urllib.parse.quote(" OR ".join(QUERIES))
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    root = ET.fromstring(get(url))
    items = []
    for it in root.iter("item"):
        pub = it.findtext("pubDate", "")
        try:
            date = datetime.strptime(pub[:16], "%a, %d %b %Y").strftime("%Y-%m-%d")
        except ValueError:
            date = ""
        title = clean(it.findtext("title", ""))
        if not any(relevant(q2, title) for q2 in QUERIES):
            continue
        items.append({
            "source": "Google News",
            "title": title,
            "snippet": "",
            "url": it.findtext("link", ""),
            "author": it.findtext("{https://news.google.com}source", "") or "",
            "date": date,
            "query": "",
        })
    return items


SOURCES = [fetch_hn, fetch_bluesky, fetch_google_news]


def run():
    OUT_DIR.mkdir(exist_ok=True)
    previous = []
    if STATE_FILE.exists():
        previous = json.loads(STATE_FILE.read_text()).get("mentions", [])
    known = {m["url"] for m in previous}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mentions = list(previous)
    status = {}
    for fn in SOURCES:
        name = fn.__name__.replace("fetch_", "")
        try:
            fresh = [m for m in fn() if m["url"] not in known]
            for m in fresh:
                known.add(m["url"])
                m["first_seen"] = today
            mentions.extend(fresh)
            status[name] = f"ok, {len(fresh)} new"
        except Exception as e:  # one dead feed must never kill the run
            status[name] = f"unavailable ({type(e).__name__})"

    mentions.sort(key=lambda m: m["date"], reverse=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    STATE_FILE.write_text(json.dumps(
        {"updated": now, "status": status, "mentions": mentions}, indent=1))
    render(mentions, status, now, today)
    print(f"{len(mentions)} mentions · " +
          " · ".join(f"{k}: {v}" for k, v in status.items()))


def render(mentions, status, now, today):
    cards = ""
    for m in mentions[:100]:
        snippet = f'<p class="snip">{escape(m["snippet"])}</p>' if m["snippet"] else ""
        author = f" · {escape(m['author'])}" if m["author"] else ""
        new = '<span class="new">new</span>' if m.get("first_seen") == today else ""
        cards += f"""
  <article>
   <span class="src">{m['source']}</span>{new}
   <a href="{escape(m['url'])}" target="_blank" rel="noopener">{escape(m['title'])}</a>
   {snippet}
   <footer>{m['date']}{author}</footer>
  </article>"""
    if not mentions:
        cards = '<p class="empty">No public mentions found yet. The radar keeps watching.</p>'

    feed_status = " · ".join(f"{escape(k)}: {escape(v)}" for k, v in status.items())
    html = f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mentions Radar · prommer.net</title>
<style>
 :root {{ color-scheme: light dark; --fg:#1a1a1a; --bg:#fafaf7; --muted:#767672;
   --card:#fff; --line:#e5e5e0; --accent:#0a6c4a; }}
 @media (prefers-color-scheme: dark) {{
   :root {{ --fg:#e8e8e4; --bg:#141414; --muted:#8f8f8a; --card:#1d1d1d;
     --line:#2b2b2b; --accent:#4dc593; }} }}
 body {{ font: 16px/1.55 -apple-system, system-ui, sans-serif; color:var(--fg);
   background:var(--bg); max-width:680px; margin:0 auto; padding:2.5rem 1.25rem 4rem; }}
 h1 {{ font-size:1.5rem; margin:0 0 .25rem; }}
 .sub {{ color:var(--muted); margin:0 0 2rem; font-size:.9rem; }}
 article {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
   padding:1rem 1.1rem; margin-bottom:.8rem; }}
 article a {{ color:var(--fg); font-weight:600; text-decoration:none; }}
 article a:hover {{ color:var(--accent); }}
 .src {{ display:inline-block; font-size:.72rem; font-weight:600; letter-spacing:.03em;
   text-transform:uppercase; color:var(--accent); margin-bottom:.3rem; margin-right:.5rem; }}
 .new {{ display:inline-block; font-size:.68rem; font-weight:700; letter-spacing:.05em;
   text-transform:uppercase; color:var(--bg); background:var(--accent);
   border-radius:4px; padding:.05rem .35rem; vertical-align:1px; }}
 .snip {{ color:var(--muted); font-size:.88rem; margin:.4rem 0 0; }}
 footer {{ color:var(--muted); font-size:.8rem; margin-top:.5rem; }}
 .empty {{ color:var(--muted); }}
 .meta {{ color:var(--muted); font-size:.78rem; margin-top:2.5rem;
   border-top:1px solid var(--line); padding-top:1rem; }}
</style>
<h1>Mentions Radar</h1>
<p class="sub">Public mentions of Thomas Prommer · We The Flywheel · prommer.net,
 refreshed daily by a scheduled agent. You can't grow attention you don't measure.</p>
{cards}
<p class="meta">Last run: {now} · Feeds: {feed_status}<br>
 Built as a We The Flywheel assessment submission · sources are linked, content
 belongs to its authors · Google News items shown as title+link only (demo use).</p>
"""
    (OUT_DIR / "index.html").write_text(html)


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""
Fetches cybersecurity news from RSS feeds, sorts stories into
Attacks & Breaches / Vulnerabilities & Tools / Policy & Regulation,
and rebuilds index.html. Designed to run daily via GitHub Actions.
No API keys, no paid services — just public RSS feeds.
"""

import html
import re
from datetime import datetime, timezone

import feedparser

FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
    "https://krebsonsecurity.com/feed/",
    "https://www.darkreading.com/rss.xml",
    "https://www.securityweek.com/feed/",
    "https://www.cisa.gov/cybersecurity-advisories/all.xml",
]

POLICY_KEYWORDS = [
    "regulation", "regulator", "bill", "law", "policy", "compliance",
    "executive order", "gdpr", "nis2", "act", "mandate", "rule",
    "congress", "legislation", "government", "sanction", "senate",
    "white house", "eu ", "cisa rule", "framework",
]
VULN_KEYWORDS = [
    "vulnerability", "vulnerabilities", "cve-", "patch", "flaw", "bug",
    "zero-day", "zero day", "exploit", "malware", "backdoor", "rce",
    "privilege escalation", "security update", "advisory",
]
ATTACK_KEYWORDS = [
    "breach", "ransomware", "hack", "attack", "leak", "stolen",
    "compromised", "phishing", "data leak", "exposed", "intrusion",
    "cyberattack", "hacker", "extortion",
]

MAX_PER_CATEGORY = 6
SUMMARY_MAX_LEN = 220


def categorize(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in POLICY_KEYWORDS):
        return "policy"
    if any(k in text for k in VULN_KEYWORDS):
        return "vulns"
    if any(k in text for k in ATTACK_KEYWORDS):
        return "attacks"
    return "attacks"  # default bucket for general security news


def clean_summary(raw):
    text = re.sub("<[^<]+?>", "", raw or "")
    text = html.unescape(text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > SUMMARY_MAX_LEN:
        text = text[:SUMMARY_MAX_LEN].rsplit(" ", 1)[0] + "…"
    return text


def fetch_all():
    items = {"attacks": [], "vulns": [], "policy": []}
    seen_titles = set()

    for url in FEEDS:
        try:
            parsed = feedparser.parse(url)
            source_name = parsed.feed.get("title", url)
        except Exception:
            continue

        for entry in parsed.entries[:15]:
            title = html.unescape(entry.get("title", "")).strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())

            link = entry.get("link", "")
            summary = clean_summary(
                entry.get("summary", entry.get("description", ""))
            )

            published_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            if published_struct:
                published_dt = datetime(*published_struct[:6], tzinfo=timezone.utc)
            else:
                published_dt = datetime.now(timezone.utc)

            category = categorize(title, summary)
            items[category].append({
                "title": title,
                "summary": summary,
                "link": link,
                "source": source_name,
                "date": published_dt,
            })

    for cat in items:
        items[cat].sort(key=lambda x: x["date"], reverse=True)
        items[cat] = items[cat][:MAX_PER_CATEGORY]

    return items


ICONS = {
    "attacks": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L4 5.5V11C4 16 7.5 20.3 12 22C16.5 20.3 20 16 20 11V5.5L12 2Z"/><path d="M12 8v5M12 16h.01"/></svg>',
    "vulns": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="6" width="8" height="12" rx="4"/><path d="M12 2v4M12 18v4M4 10h4M16 10h4M4 16h4M16 16h4M6 6l2 2M18 6l-2 2"/></svg>',
    "policy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M5 7l-3 6a4 4 0 008 0l-3-6M19 7l-3 6a4 4 0 008 0l-3-6M5 7h14M8 21h8"/></svg>',
}
SECTION_TITLES = {
    "attacks": "Attacks &amp; Breaches",
    "vulns": "Vulnerabilities &amp; Tools",
    "policy": "Policy &amp; Regulation",
}
TAG_CLASS = {"attacks": "t1", "vulns": "t2", "policy": "t3"}


def render_card(item, category):
    tag_cls = TAG_CLASS[category]
    date_str = item["date"].strftime("%b %d, %Y")
    return f"""
    <div class="card">
      <div class="card-icon">{ICONS[category]}</div>
      <div>
        <div class="card-top"><span class="tag {tag_cls}">{html.escape(item['source'])}</span></div>
        <h3><a href="{html.escape(item['link'])}" target="_blank" rel="noopener">{html.escape(item['title'])}</a></h3>
        <p>{html.escape(item['summary'])}</p>
        <div class="card-footer"><span><b>{html.escape(item['source'])}</b></span><span>{date_str}</span></div>
      </div>
    </div>"""


def render_section(category, items):
    cards = "".join(render_card(i, category) for i in items) if items else \
        '<p style="color:var(--muted); font-size:13.5px;">No fresh stories in this category today.</p>'
    return f"""
  <section class="section {category}">
    <div class="section-head">
      {ICONS[category]}
      <h2>{SECTION_TITLES[category]}</h2>
      <span class="count">{len(items)} stories</span>
    </div>
    {cards}
  </section>"""


def render_chart(items):
    counts = {cat: len(items[cat]) for cat in ["attacks", "vulns", "policy"]}
    max_count = max(counts.values()) or 1
    bars = ""
    gradients = {
        "attacks": "linear-gradient(180deg,#4C7CE0,var(--navy))",
        "vulns": "linear-gradient(180deg, var(--sky), var(--blue))",
        "policy": "linear-gradient(180deg,#BAE6FD,#38BDF8)",
    }
    labels = {"attacks": "Attacks &amp; Breaches", "vulns": "Vulns &amp; Tools", "policy": "Policy"}
    for cat in ["attacks", "vulns", "policy"]:
        pct = max(int(counts[cat] / max_count * 100), 8)
        bars += f"""
        <div class="bar-col">
          <span class="bar-num">{counts[cat]}</span>
          <div class="bar" style="height:{pct}%; background:{gradients[cat]};"></div>
          <span class="bar-label">{labels[cat]}</span>
        </div>"""
    return bars


def render_tldr(items):
    top = []
    for cat in ["attacks", "vulns", "policy"]:
        if items[cat]:
            top.append(items[cat][0])
    top.sort(key=lambda x: x["date"], reverse=True)
    top = top[:3]
    lis = "".join(
        f'<li><b>{html.escape(t["title"])}</b> — {html.escape(t["summary"][:110])}…</li>'
        for t in top
    )
    return lis or "<li>No stories fetched today — check the feed sources.</li>"


def build_html(items):
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    total = sum(len(v) for v in items.values())

    template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal — Daily Cyber Briefing</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{{
    --bg:#FFFFFF; --bg-soft:#F3F8FE; --line:#DEE9F7; --ink:#0B2545;
    --muted:#5B7085; --blue:#2563EB; --blue-deep:#0F3D91; --sky:#38BDF8; --navy:#0B2545;
  }}
  *{{box-sizing:border-box; margin:0; padding:0;}}
  body{{ background:var(--bg); color:var(--ink); font-family:'Inter', sans-serif; line-height:1.5; padding-bottom:60px; }}
  ::selection{{ background:var(--sky); color:#fff; }}
  header{{ border-bottom:1px solid var(--line); padding:20px 24px; position:sticky; top:0; background:rgba(255,255,255,0.94); backdrop-filter:blur(6px); z-index:10; }}
  .header-row{{ max-width:980px; margin:0 auto; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; }}
  .brand{{ display:flex; align-items:center; gap:10px; }}
  .brand-icon{{ width:30px; height:30px; flex-shrink:0; }}
  .brand h1{{ font-family:'Space Grotesk', sans-serif; font-size:19px; font-weight:700; letter-spacing:-0.01em; }}
  .brand h1 span{{ color:var(--blue); }}
  .meta{{ font-size:12px; color:var(--muted); text-align:right; }}
  main{{ max-width:980px; margin:0 auto; padding:0 24px; }}
  .overview{{ display:grid; grid-template-columns: 1.4fr 1fr; gap:16px; margin-top:28px; }}
  @media (max-width:700px){{ .overview{{ grid-template-columns:1fr; }} }}
  .tldr{{ background:var(--bg-soft); border:1px solid var(--line); border-radius:12px; padding:20px 22px; }}
  .panel-label{{ font-family:'Space Grotesk', sans-serif; font-size:12px; font-weight:600; color:var(--blue-deep); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:12px; }}
  .tldr ol{{ list-style:none; counter-reset:item; }}
  .tldr li{{ counter-increment:item; padding:8px 0 8px 30px; position:relative; font-size:14px; border-top:1px solid var(--line); }}
  .tldr li:first-child{{ border-top:none; }}
  .tldr li::before{{ content:counter(item); position:absolute; left:0; top:8px; width:20px; height:20px; border-radius:6px; background:var(--blue); color:#fff; font-family:'Space Grotesk', sans-serif; font-size:11px; font-weight:700; display:flex; align-items:center; justify-content:center; }}
  .chart-card{{ background:var(--bg-soft); border:1px solid var(--line); border-radius:12px; padding:20px 22px; display:flex; flex-direction:column; justify-content:space-between; }}
  .bars{{ display:flex; align-items:flex-end; gap:14px; height:120px; margin-top:8px; }}
  .bar-col{{ flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; }}
  .bar{{ width:100%; max-width:44px; border-radius:6px 6px 3px 3px; }}
  .bar-num{{ font-family:'Space Grotesk', sans-serif; font-weight:700; font-size:13px; margin-bottom:4px; }}
  .bar-label{{ font-size:10.5px; color:var(--muted); margin-top:8px; text-align:center; }}
  .section{{ margin-top:42px; }}
  .section-head{{ display:flex; align-items:center; gap:10px; margin-bottom:16px; padding-bottom:10px; border-bottom:2px solid var(--line); }}
  .section-head svg{{ width:20px; height:20px; flex-shrink:0; }}
  .section-head h2{{ font-family:'Space Grotesk', sans-serif; font-size:15px; font-weight:700; letter-spacing:-0.01em; }}
  .section-head .count{{ margin-left:auto; font-size:11.5px; color:var(--muted); background:var(--bg-soft); border:1px solid var(--line); padding:2px 10px; border-radius:20px; }}
  .section.attacks .section-head h2, .section.attacks .section-head svg{{ color:var(--navy); }}
  .section.vulns .section-head h2, .section.vulns .section-head svg{{ color:var(--blue); }}
  .section.policy .section-head h2, .section.policy .section-head svg{{ color:#0284C7; }}
  .card{{ display:grid; grid-template-columns:40px 1fr; gap:14px; background:#fff; border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin-bottom:12px; transition: box-shadow 0.15s ease, transform 0.15s ease; }}
  .card:hover{{ box-shadow:0 4px 16px rgba(37,99,235,0.10); transform:translateY(-1px); }}
  .card-icon{{ width:38px; height:38px; border-radius:9px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
  .card-icon svg{{ width:19px; height:19px; }}
  .section.attacks .card-icon{{ background:#0B25451A; }} .section.attacks .card-icon svg{{ color:var(--navy); }}
  .section.vulns .card-icon{{ background:#2563EB1A; }} .section.vulns .card-icon svg{{ color:var(--blue); }}
  .section.policy .card-icon{{ background:#38BDF81F; }} .section.policy .card-icon svg{{ color:#0284C7; }}
  .card-top{{ margin-bottom:6px; }}
  .tag{{ font-family:'Space Grotesk', sans-serif; font-size:10px; font-weight:600; letter-spacing:0.04em; text-transform:uppercase; padding:2px 9px; border-radius:20px; }}
  .tag.t1{{ background:#0B25451A; color:var(--navy); }}
  .tag.t2{{ background:#2563EB1A; color:var(--blue); }}
  .tag.t3{{ background:#38BDF81F; color:#0284C7; }}
  .card h3{{ font-size:15px; font-weight:600; margin-bottom:5px; }}
  .card h3 a{{ color:var(--ink); text-decoration:none; }}
  .card h3 a:hover{{ color:var(--blue); text-decoration:underline; }}
  .card p{{ font-size:13.5px; color:var(--muted); }}
  .card-footer{{ display:flex; justify-content:space-between; margin-top:10px; font-size:11.5px; color:var(--muted); }}
  .card-footer b{{ color:var(--ink); font-weight:600; }}
  footer{{ max-width:980px; margin:50px auto 0; padding:20px 24px 0; border-top:1px solid var(--line); font-size:11.5px; color:var(--muted); text-align:center; }}
</style>
</head>
<body>
<header>
  <div class="header-row">
    <div class="brand">
      <svg class="brand-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2L4 5.5V11C4 16 7.5 20.3 12 22C16.5 20.3 20 16 20 11V5.5L12 2Z" fill="#2563EB" fill-opacity="0.12" stroke="#2563EB" stroke-width="1.6"/>
        <path d="M9 12.2L11 14.2L15.5 9.5" stroke="#2563EB" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <h1>Signal <span>// Daily Cyber Briefing</span></h1>
    </div>
    <div class="meta">Edition — {today}<br>{total} stories · Auto-updated daily</div>
  </div>
</header>
<main>
  <div class="overview">
    <div class="tldr">
      <div class="panel-label">Top stories today</div>
      <ol>{render_tldr(items)}</ol>
    </div>
    <div class="chart-card">
      <div class="panel-label">Story volume by category</div>
      <div class="bars">{render_chart(items)}</div>
    </div>
  </div>
  {render_section("attacks", items["attacks"])}
  {render_section("vulns", items["vulns"])}
  {render_section("policy", items["policy"])}
</main>
<footer>
  Auto-compiled from public RSS feeds every day via GitHub Actions.<br>
  Headlines and summaries are from their original publishers — click through to read the full story.
</footer>
</body>
</html>"""
    return template


if __name__ == "__main__":
    data = fetch_all()
    html_out = build_html(data)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    total = sum(len(v) for v in data.values())
    print(f"Built index.html with {total} stories "
          f"(attacks={len(data['attacks'])}, vulns={len(data['vulns'])}, policy={len(data['policy'])})")#!/usr/bin/env python3
"""
Fetches cybersecurity news from RSS feeds, sorts stories into
Attacks & Breaches / Vulnerabilities & Tools / Policy & Regulation,
and rebuilds index.html. Designed to run daily via GitHub Actions.
No API keys, no paid services — just public RSS feeds.
"""

import html
import re
from datetime import datetime, timezone

import feedparser

FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
    "https://krebsonsecurity.com/feed/",
    "https://www.darkreading.com/rss.xml",
    "https://www.securityweek.com/feed/",
    "https://www.cisa.gov/cybersecurity-advisories/all.xml",
]

POLICY_KEYWORDS = [
    "regulation", "regulator", "bill", "law", "policy", "compliance",
    "executive order", "gdpr", "nis2", "act", "mandate", "rule",
    "congress", "legislation", "government", "sanction", "senate",
    "white house", "eu ", "cisa rule", "framework",
]
VULN_KEYWORDS = [
    "vulnerability", "vulnerabilities", "cve-", "patch", "flaw", "bug",
    "zero-day", "zero day", "exploit", "malware", "backdoor", "rce",
    "privilege escalation", "security update", "advisory",
]
ATTACK_KEYWORDS = [
    "breach", "ransomware", "hack", "attack", "leak", "stolen",
    "compromised", "phishing", "data leak", "exposed", "intrusion",
    "cyberattack", "hacker", "extortion",
]

MAX_PER_CATEGORY = 6
SUMMARY_MAX_LEN = 220


def categorize(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in POLICY_KEYWORDS):
        return "policy"
    if any(k in text for k in VULN_KEYWORDS):
        return "vulns"
    if any(k in text for k in ATTACK_KEYWORDS):
        return "attacks"
    return "attacks"  # default bucket for general security news


def clean_summary(raw):
    text = re.sub("<[^<]+?>", "", raw or "")
    text = html.unescape(text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > SUMMARY_MAX_LEN:
        text = text[:SUMMARY_MAX_LEN].rsplit(" ", 1)[0] + "…"
    return text


def fetch_all():
    items = {"attacks": [], "vulns": [], "policy": []}
    seen_titles = set()

    for url in FEEDS:
        try:
            parsed = feedparser.parse(url)
            source_name = parsed.feed.get("title", url)
        except Exception:
            continue

        for entry in parsed.entries[:15]:
            title = html.unescape(entry.get("title", "")).strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())

            link = entry.get("link", "")
            summary = clean_summary(
                entry.get("summary", entry.get("description", ""))
            )

            published_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            if published_struct:
                published_dt = datetime(*published_struct[:6], tzinfo=timezone.utc)
            else:
                published_dt = datetime.now(timezone.utc)

            category = categorize(title, summary)
            items[category].append({
                "title": title,
                "summary": summary,
                "link": link,
                "source": source_name,
                "date": published_dt,
            })

    for cat in items:
        items[cat].sort(key=lambda x: x["date"], reverse=True)
        items[cat] = items[cat][:MAX_PER_CATEGORY]

    return items


ICONS = {
    "attacks": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L4 5.5V11C4 16 7.5 20.3 12 22C16.5 20.3 20 16 20 11V5.5L12 2Z"/><path d="M12 8v5M12 16h.01"/></svg>',
    "vulns": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="6" width="8" height="12" rx="4"/><path d="M12 2v4M12 18v4M4 10h4M16 10h4M4 16h4M16 16h4M6 6l2 2M18 6l-2 2"/></svg>',
    "policy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M5 7l-3 6a4 4 0 008 0l-3-6M19 7l-3 6a4 4 0 008 0l-3-6M5 7h14M8 21h8"/></svg>',
}
SECTION_TITLES = {
    "attacks": "Attacks &amp; Breaches",
    "vulns": "Vulnerabilities &amp; Tools",
    "policy": "Policy &amp; Regulation",
}
TAG_CLASS = {"attacks": "t1", "vulns": "t2", "policy": "t3"}


def render_card(item, category):
    tag_cls = TAG_CLASS[category]
    date_str = item["date"].strftime("%b %d, %Y")
    return f"""
    <div class="card">
      <div class="card-icon">{ICONS[category]}</div>
      <div>
        <div class="card-top"><span class="tag {tag_cls}">{html.escape(item['source'])}</span></div>
        <h3><a href="{html.escape(item['link'])}" target="_blank" rel="noopener">{html.escape(item['title'])}</a></h3>
        <p>{html.escape(item['summary'])}</p>
        <div class="card-footer"><span><b>{html.escape(item['source'])}</b></span><span>{date_str}</span></div>
      </div>
    </div>"""


def render_section(category, items):
    cards = "".join(render_card(i, category) for i in items) if items else \
        '<p style="color:var(--muted); font-size:13.5px;">No fresh stories in this category today.</p>'
    return f"""
  <section class="section {category}">
    <div class="section-head">
      {ICONS[category]}
      <h2>{SECTION_TITLES[category]}</h2>
      <span class="count">{len(items)} stories</span>
    </div>
    {cards}
  </section>"""


def render_chart(items):
    counts = {cat: len(items[cat]) for cat in ["attacks", "vulns", "policy"]}
    max_count = max(counts.values()) or 1
    bars = ""
    gradients = {
        "attacks": "linear-gradient(180deg,#4C7CE0,var(--navy))",
        "vulns": "linear-gradient(180deg, var(--sky), var(--blue))",
        "policy": "linear-gradient(180deg,#BAE6FD,#38BDF8)",
    }
    labels = {"attacks": "Attacks &amp; Breaches", "vulns": "Vulns &amp; Tools", "policy": "Policy"}
    for cat in ["attacks", "vulns", "policy"]:
        pct = max(int(counts[cat] / max_count * 100), 8)
        bars += f"""
        <div class="bar-col">
          <span class="bar-num">{counts[cat]}</span>
          <div class="bar" style="height:{pct}%; background:{gradients[cat]};"></div>
          <span class="bar-label">{labels[cat]}</span>
        </div>"""
    return bars


def render_tldr(items):
    top = []
    for cat in ["attacks", "vulns", "policy"]:
        if items[cat]:
            top.append(items[cat][0])
    top.sort(key=lambda x: x["date"], reverse=True)
    top = top[:3]
    lis = "".join(
        f'<li><b>{html.escape(t["title"])}</b> — {html.escape(t["summary"][:110])}…</li>'
        for t in top
    )
    return lis or "<li>No stories fetched today — check the feed sources.</li>"


def build_html(items):
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    total = sum(len(v) for v in items.values())

    template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal — Daily Cyber Briefing</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{{
    --bg:#FFFFFF; --bg-soft:#F3F8FE; --line:#DEE9F7; --ink:#0B2545;
    --muted:#5B7085; --blue:#2563EB; --blue-deep:#0F3D91; --sky:#38BDF8; --navy:#0B2545;
  }}
  *{{box-sizing:border-box; margin:0; padding:0;}}
  body{{ background:var(--bg); color:var(--ink); font-family:'Inter', sans-serif; line-height:1.5; padding-bottom:60px; }}
  ::selection{{ background:var(--sky); color:#fff; }}
  header{{ border-bottom:1px solid var(--line); padding:20px 24px; position:sticky; top:0; background:rgba(255,255,255,0.94); backdrop-filter:blur(6px); z-index:10; }}
  .header-row{{ max-width:980px; margin:0 auto; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; }}
  .brand{{ display:flex; align-items:center; gap:10px; }}
  .brand-icon{{ width:30px; height:30px; flex-shrink:0; }}
  .brand h1{{ font-family:'Space Grotesk', sans-serif; font-size:19px; font-weight:700; letter-spacing:-0.01em; }}
  .brand h1 span{{ color:var(--blue); }}
  .meta{{ font-size:12px; color:var(--muted); text-align:right; }}
  main{{ max-width:980px; margin:0 auto; padding:0 24px; }}
  .overview{{ display:grid; grid-template-columns: 1.4fr 1fr; gap:16px; margin-top:28px; }}
  @media (max-width:700px){{ .overview{{ grid-template-columns:1fr; }} }}
  .tldr{{ background:var(--bg-soft); border:1px solid var(--line); border-radius:12px; padding:20px 22px; }}
  .panel-label{{ font-family:'Space Grotesk', sans-serif; font-size:12px; font-weight:600; color:var(--blue-deep); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:12px; }}
  .tldr ol{{ list-style:none; counter-reset:item; }}
  .tldr li{{ counter-increment:item; padding:8px 0 8px 30px; position:relative; font-size:14px; border-top:1px solid var(--line); }}
  .tldr li:first-child{{ border-top:none; }}
  .tldr li::before{{ content:counter(item); position:absolute; left:0; top:8px; width:20px; height:20px; border-radius:6px; background:var(--blue); color:#fff; font-family:'Space Grotesk', sans-serif; font-size:11px; font-weight:700; display:flex; align-items:center; justify-content:center; }}
  .chart-card{{ background:var(--bg-soft); border:1px solid var(--line); border-radius:12px; padding:20px 22px; display:flex; flex-direction:column; justify-content:space-between; }}
  .bars{{ display:flex; align-items:flex-end; gap:14px; height:120px; margin-top:8px; }}
  .bar-col{{ flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; }}
  .bar{{ width:100%; max-width:44px; border-radius:6px 6px 3px 3px; }}
  .bar-num{{ font-family:'Space Grotesk', sans-serif; font-weight:700; font-size:13px; margin-bottom:4px; }}
  .bar-label{{ font-size:10.5px; color:var(--muted); margin-top:8px; text-align:center; }}
  .section{{ margin-top:42px; }}
  .section-head{{ display:flex; align-items:center; gap:10px; margin-bottom:16px; padding-bottom:10px; border-bottom:2px solid var(--line); }}
  .section-head svg{{ width:20px; height:20px; flex-shrink:0; }}
  .section-head h2{{ font-family:'Space Grotesk', sans-serif; font-size:15px; font-weight:700; letter-spacing:-0.01em; }}
  .section-head .count{{ margin-left:auto; font-size:11.5px; color:var(--muted); background:var(--bg-soft); border:1px solid var(--line); padding:2px 10px; border-radius:20px; }}
  .section.attacks .section-head h2, .section.attacks .section-head svg{{ color:var(--navy); }}
  .section.vulns .section-head h2, .section.vulns .section-head svg{{ color:var(--blue); }}
  .section.policy .section-head h2, .section.policy .section-head svg{{ color:#0284C7; }}
  .card{{ display:grid; grid-template-columns:40px 1fr; gap:14px; background:#fff; border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin-bottom:12px; transition: box-shadow 0.15s ease, transform 0.15s ease; }}
  .card:hover{{ box-shadow:0 4px 16px rgba(37,99,235,0.10); transform:translateY(-1px); }}
  .card-icon{{ width:38px; height:38px; border-radius:9px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
  .card-icon svg{{ width:19px; height:19px; }}
  .section.attacks .card-icon{{ background:#0B25451A; }} .section.attacks .card-icon svg{{ color:var(--navy); }}
  .section.vulns .card-icon{{ background:#2563EB1A; }} .section.vulns .card-icon svg{{ color:var(--blue); }}
  .section.policy .card-icon{{ background:#38BDF81F; }} .section.policy .card-icon svg{{ color:#0284C7; }}
  .card-top{{ margin-bottom:6px; }}
  .tag{{ font-family:'Space Grotesk', sans-serif; font-size:10px; font-weight:600; letter-spacing:0.04em; text-transform:uppercase; padding:2px 9px; border-radius:20px; }}
  .tag.t1{{ background:#0B25451A; color:var(--navy); }}
  .tag.t2{{ background:#2563EB1A; color:var(--blue); }}
  .tag.t3{{ background:#38BDF81F; color:#0284C7; }}
  .card h3{{ font-size:15px; font-weight:600; margin-bottom:5px; }}
  .card h3 a{{ color:var(--ink); text-decoration:none; }}
  .card h3 a:hover{{ color:var(--blue); text-decoration:underline; }}
  .card p{{ font-size:13.5px; color:var(--muted); }}
  .card-footer{{ display:flex; justify-content:space-between; margin-top:10px; font-size:11.5px; color:var(--muted); }}
  .card-footer b{{ color:var(--ink); font-weight:600; }}
  footer{{ max-width:980px; margin:50px auto 0; padding:20px 24px 0; border-top:1px solid var(--line); font-size:11.5px; color:var(--muted); text-align:center; }}
</style>
</head>
<body>
<header>
  <div class="header-row">
    <div class="brand">
      <svg class="brand-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2L4 5.5V11C4 16 7.5 20.3 12 22C16.5 20.3 20 16 20 11V5.5L12 2Z" fill="#2563EB" fill-opacity="0.12" stroke="#2563EB" stroke-width="1.6"/>
        <path d="M9 12.2L11 14.2L15.5 9.5" stroke="#2563EB" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <h1>Signal <span>// Daily Cyber Briefing</span></h1>
    </div>
    <div class="meta">Edition — {today}<br>{total} stories · Auto-updated daily</div>
  </div>
</header>
<main>
  <div class="overview">
    <div class="tldr">
      <div class="panel-label">Top stories today</div>
      <ol>{render_tldr(items)}</ol>
    </div>
    <div class="chart-card">
      <div class="panel-label">Story volume by category</div>
      <div class="bars">{render_chart(items)}</div>
    </div>
  </div>
  {render_section("attacks", items["attacks"])}
  {render_section("vulns", items["vulns"])}
  {render_section("policy", items["policy"])}
</main>
<footer>
  Auto-compiled from public RSS feeds every day via GitHub Actions.<br>
  Headlines and summaries are from their original publishers — click through to read the full story.
</footer>
</body>
</html>"""
    return template


if __name__ == "__main__":
    data = fetch_all()
    html_out = build_html(data)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    total = sum(len(v) for v in data.values())
    print(f"Built index.html with {total} stories "
          f"(attacks={len(data['attacks'])}, vulns={len(data['vulns'])}, policy={len(data['policy'])})")

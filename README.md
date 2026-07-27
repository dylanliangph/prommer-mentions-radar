# Mentions Radar for prommer.net

A self-updating public dashboard of mentions of Thomas Prommer, We The Flywheel,
and prommer.net across the open web. Built in a 45-minute window for the
We The Flywheel Agentic Engineer assessment.

**Live:** https://dylanliangph.github.io/prommer-mentions-radar/
**Data API:** [`docs/mentions.json`](docs/mentions.json) — the same data,
machine-readable, free for other agents to consume.

## Why this and not a press kit

The product card says prommer.net's job is building inbound demand. A press
kit was the obvious build — it serves the site's stated audience (bookers)
directly, and in a real engagement I'd ship one. But a static page doesn't
demonstrate agentic engineering, and you can't grow attention you don't
measure. So I built the measuring instrument: a scheduled agent that watches
the open web and publishes what it finds, every day, without anyone touching it.

## How it works

- `radar.py` — stdlib-only Python. Queries Hacker News (Algolia API),
  Bluesky (public search API), and Google News (RSS, shown title+link only).
  Each source is wrapped independently: a blocked or down feed logs a status
  and the run ships whatever the others returned. Results are exact-phrase
  filtered (search APIs match loose word combos), deduped against prior runs,
  and rendered to a static page plus JSON.
- `.github/workflows/radar.yml` — daily cron + manual trigger. Commits the
  refreshed data back to the repo; GitHub Pages serves it.
- Items first seen in the latest run get a **new** badge — if you're reading
  this a few days after submission, anything badged arrived after I stopped
  touching it.

## Deliberate V1 cuts

- **Entity disambiguation.** The radar currently surfaces a Law360 piece about
  a *different* Thomas Prommer (a Kirkland & Ellis lawyer). V2 is an LLM
  relevance-judge stage in the pipeline that classifies each hit before it
  ships. Kept in V1 on purpose: it's an honest demo of why that stage matters.
- **Reddit.** Blocks anonymous API access from datacenter IPs; needs OAuth.
- **Alerting.** A new-mention webhook/email is the natural next step, but
  needs secrets management — out of scope for a public 45-minute build.
- **Trend charting.** Mentions-over-time is one matplotlib call away, but with
  ~6 data points it would be decoration, not information.

## Provenance

Co-built with Claude (Anthropic) under my direction — the tool wrote code and
caught bugs, I made the product calls: what to build, what to cut, and why.
All linked content belongs to its authors.

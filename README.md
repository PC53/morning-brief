# morning-brief

Generates a daily one-page "morning brief" you can read locally each
morning: top stories from Hacker News plus top headlines from Google News,
rendered as a single readable HTML page — masthead: **The Daily Byte** —
with side-by-side sections and today's Shoreditch, London weather in the
header.

## What it does

Running the script:

1. Fetches the current top ~18 Hacker News stories via the official
   [HN Firebase API](https://github.com/HackerNews/API) (no key required).
2. Fetches the current top ~18 headlines from the
   [Google News RSS feed](https://news.google.com/rss) (no key required).
3. Fetches current weather for Shoreditch, London from
   [Open-Meteo](https://open-meteo.com) (free, keyless) for the masthead.
4. Renders it all into a single self-contained, styled HTML file at
   `output/YYYY-MM-DD.html` (today's date) and prints the path. The two
   sections lay out side by side on wide viewports and stack on narrow
   ones; each shows its top 5 items with a "Show more" toggle
   (plain `<details>`/`<summary>`, no JS) revealing the rest.

Each run regenerates today's file from scratch. If a source fails (or a
single item is malformed), the script logs a warning to stderr and still
produces a brief from whatever it could fetch — weather is treated the same
way and simply shows "Weather unavailable" if the fetch fails. The run only
exits with an error if *both* news sources fail entirely.

## How to run

Requires Python 3.9+ and internet access. No dependencies to install — it
only uses the standard library.

```bash
python3 generate_brief.py
```

This prints the output path, e.g. `output/2026-09-04.html`. Open it in a
browser to read.

## Out of scope (for now)

This is a first scaffolding pass, kept intentionally small:

- **Delivery / scheduling** — no email, no notifications, no cron setup.
  The script just writes a local file; running it daily (via cron, a
  launchd agent, etc.) is left to the reader.
- **AI summarization** — headlines are shown as-is, not summarized or
  ranked by an LLM.

Both are natural next steps but deliberately not part of this pass.

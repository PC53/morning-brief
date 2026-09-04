#!/usr/bin/env python3
"""Generate today's morning brief: top Hacker News + Google News headlines
as a single self-contained HTML file in output/YYYY-MM-DD.html.

Usage:
    python3 generate_brief.py

No API keys or config needed. Uses only the Python standard library.
"""

from __future__ import annotations

import datetime
import html
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"

HN_ITEM_COUNT = 18
GOOGLE_NEWS_ITEM_COUNT = 18

REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "morning-brief/1.0 (local script; https://github.com/)"


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def fetch_hacker_news(count: int = HN_ITEM_COUNT) -> list[dict]:
    """Fetch top HN stories. Skips any story id that fails to fetch/parse
    individually so one bad item doesn't sink the whole section."""
    try:
        story_ids = json.loads(fetch_url(HN_TOP_STORIES_URL))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
        print(f"warning: failed to fetch Hacker News story list: {error}", file=sys.stderr)
        return []

    stories = []
    for story_id in story_ids[: count * 2]:  # fetch extra in case some fail
        if len(stories) >= count:
            break
        try:
            item = json.loads(fetch_url(HN_ITEM_URL.format(id=story_id)))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
            print(f"warning: skipping HN item {story_id}: {error}", file=sys.stderr)
            continue

        if not item or not item.get("title"):
            continue

        stories.append(
            {
                "title": item.get("title", "(untitled)"),
                "url": item.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                "score": item.get("score", 0),
                "comments_url": f"https://news.ycombinator.com/item?id={story_id}",
            }
        )

    return stories


def fetch_google_news(count: int = GOOGLE_NEWS_ITEM_COUNT) -> list[dict]:
    """Fetch top Google News RSS headlines. Returns [] on total failure;
    skips individual <item> entries that fail to parse."""
    try:
        raw_xml = fetch_url(GOOGLE_NEWS_RSS_URL)
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"warning: failed to fetch Google News RSS: {error}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as error:
        print(f"warning: failed to parse Google News RSS: {error}", file=sys.stderr)
        return []

    headlines = []
    for item in root.findall("./channel/item"):
        if len(headlines) >= count:
            break
        title_element = item.find("title")
        link_element = item.find("link")
        pub_date_element = item.find("pubDate")

        if title_element is None or link_element is None:
            continue
        if not (title_element.text and link_element.text):
            continue

        headlines.append(
            {
                "title": title_element.text,
                "url": link_element.text,
                "published": pub_date_element.text if pub_date_element is not None else "",
            }
        )

    return headlines


def render_html(hn_stories: list[dict], news_headlines: list[dict], today: datetime.date) -> str:
    def render_hn_item(story: dict) -> str:
        title = html.escape(story["title"])
        url = html.escape(story["url"])
        comments_url = html.escape(story["comments_url"])
        score = story["score"]
        return f"""      <li class="item">
        <a class="item-title" href="{url}">{title}</a>
        <span class="item-meta">{score} pts &middot; <a href="{comments_url}">comments</a></span>
      </li>"""

    def render_news_item(headline: dict) -> str:
        title = html.escape(headline["title"])
        url = html.escape(headline["url"])
        return f"""      <li class="item">
        <a class="item-title" href="{url}">{title}</a>
      </li>"""

    hn_items_html = (
        "\n".join(render_hn_item(story) for story in hn_stories)
        if hn_stories
        else '      <li class="item empty">No Hacker News stories available today.</li>'
    )
    news_items_html = (
        "\n".join(render_news_item(headline) for headline in news_headlines)
        if news_headlines
        else '      <li class="item empty">No Google News headlines available today.</li>'
    )

    dateline = today.strftime("%A, %B %-d, %Y")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Morning Brief &mdash; {dateline}</title>
<style>
  body {{
    background: #f4f1ea;
    color: #1a1a1a;
    font-family: Georgia, "Times New Roman", serif;
    max-width: 700px;
    margin: 0 auto;
    padding: 2.5rem 1.5rem 4rem;
    line-height: 1.5;
  }}
  header {{
    text-align: center;
    border-bottom: 3px double #1a1a1a;
    padding-bottom: 1rem;
    margin-bottom: 2rem;
  }}
  header h1 {{
    font-size: 2.2rem;
    letter-spacing: 0.04em;
    margin: 0 0 0.3rem;
    text-transform: uppercase;
  }}
  header .dateline {{
    font-style: italic;
    color: #555;
    font-size: 1rem;
  }}
  section {{
    margin-bottom: 2.5rem;
  }}
  section h2 {{
    font-size: 1.3rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    border-bottom: 1px solid #1a1a1a;
    padding-bottom: 0.3rem;
    margin-bottom: 1rem;
  }}
  ul.items {{
    list-style: none;
    margin: 0;
    padding: 0;
  }}
  li.item {{
    padding: 0.6rem 0;
    border-bottom: 1px solid #ddd6c8;
  }}
  li.item:last-child {{
    border-bottom: none;
  }}
  li.item.empty {{
    color: #777;
    font-style: italic;
  }}
  .item-title {{
    display: block;
    color: #1a1a1a;
    text-decoration: none;
    font-size: 1.05rem;
  }}
  .item-title:hover {{
    text-decoration: underline;
  }}
  .item-meta {{
    display: block;
    color: #777;
    font-size: 0.85rem;
    margin-top: 0.15rem;
  }}
  .item-meta a {{
    color: #777;
  }}
  footer {{
    text-align: center;
    color: #999;
    font-size: 0.8rem;
    margin-top: 3rem;
  }}
</style>
</head>
<body>
  <header>
    <h1>The Morning Brief</h1>
    <div class="dateline">{dateline}</div>
  </header>

  <section>
    <h2>Hacker News</h2>
    <ul class="items">
{hn_items_html}
    </ul>
  </section>

  <section>
    <h2>Google News</h2>
    <ul class="items">
{news_items_html}
    </ul>
  </section>

  <footer>
    Generated locally &mdash; no delivery, no summarization. Just the headlines.
  </footer>
</body>
</html>
"""


def main() -> int:
    today = datetime.date.today()

    hn_stories = fetch_hacker_news()
    news_headlines = fetch_google_news()

    if not hn_stories and not news_headlines:
        print("error: both Hacker News and Google News fetches failed; nothing to write", file=sys.stderr)
        return 1

    output_dir = "output"
    import os

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{today.isoformat()}.html")

    page_html = render_html(hn_stories, news_headlines, today)
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(page_html)

    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

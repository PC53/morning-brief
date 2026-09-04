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

# Shoreditch, London
WEATHER_LATITUDE = 51.5265
WEATHER_LONGITUDE = -0.0787
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={WEATHER_LATITUDE}&longitude={WEATHER_LONGITUDE}"
    "&current_weather=true&temperature_unit=celsius"
)

# WMO weather interpretation codes used by Open-Meteo's current_weather.weathercode.
# https://open-meteo.com/en/docs
WMO_WEATHER_DESCRIPTIONS = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

HN_ITEM_COUNT = 18
GOOGLE_NEWS_ITEM_COUNT = 18
VISIBLE_ITEM_COUNT = 5  # items shown before the "Show more" toggle

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


def fetch_weather() -> dict | None:
    """Fetch current weather for Shoreditch, London via Open-Meteo (keyless).
    Returns None on any failure so a weather hiccup never blocks the brief."""
    try:
        data = json.loads(fetch_url(WEATHER_URL))
        current = data["current_weather"]
        return {
            "temperature_c": current["temperature"],
            "description": WMO_WEATHER_DESCRIPTIONS.get(current["weathercode"], "unknown"),
        }
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError) as error:
        print(f"warning: failed to fetch weather: {error}", file=sys.stderr)
        return None


def render_html(
    hn_stories: list[dict],
    news_headlines: list[dict],
    today: datetime.date,
    weather: dict | None,
) -> str:
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

    def render_section_items(items: list[dict], render_item, empty_message: str) -> str:
        if not items:
            return f'    <ul class="items">\n      <li class="item empty">{empty_message}</li>\n    </ul>'

        visible = items[:VISIBLE_ITEM_COUNT]
        rest = items[VISIBLE_ITEM_COUNT:]

        visible_html = "\n".join(render_item(item) for item in visible)
        block = f'    <ul class="items">\n{visible_html}\n    </ul>'

        if rest:
            rest_html = "\n".join(render_item(item) for item in rest)
            block += f"""
    <details class="more">
      <summary>Show {len(rest)} more</summary>
      <ul class="items">
{rest_html}
      </ul>
    </details>"""

        return block

    hn_section_html = render_section_items(
        hn_stories, render_hn_item, "No Hacker News stories available today."
    )
    news_section_html = render_section_items(
        news_headlines, render_news_item, "No Google News headlines available today."
    )

    dateline = today.strftime("%A, %B %-d, %Y")

    if weather is not None:
        temperature = round(weather["temperature_c"])
        description = html.escape(weather["description"])
        weather_html = f'<div class="weather">{temperature}&deg;C, {description} in Shoreditch, London</div>'
    else:
        weather_html = '<div class="weather weather-unavailable">Weather unavailable</div>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Daily Byte &mdash; {dateline}</title>
<style>
  body {{
    background: #f4f1ea;
    color: #1a1a1a;
    font-family: Georgia, "Times New Roman", serif;
    max-width: 1000px;
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
  header .weather {{
    color: #555;
    font-size: 0.95rem;
    margin-top: 0.3rem;
  }}
  header .weather-unavailable {{
    color: #999;
    font-style: italic;
  }}
  .sections {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 2rem 2.5rem;
  }}
  @media (min-width: 700px) {{
    .sections {{
      grid-template-columns: 1fr 1fr;
    }}
  }}
  section {{
    margin-bottom: 0;
    min-width: 0;
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
    overflow-wrap: break-word;
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
  details.more {{
    margin-top: 0.4rem;
  }}
  details.more summary {{
    cursor: pointer;
    color: #555;
    font-size: 0.9rem;
    padding: 0.4rem 0;
  }}
  details.more[open] summary {{
    margin-bottom: 0.3rem;
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
    <h1>The Daily Byte</h1>
    <div class="dateline">{dateline}</div>
    {weather_html}
  </header>

  <div class="sections">
    <section>
      <h2>Hacker News</h2>
{hn_section_html}
    </section>

    <section>
      <h2>Google News</h2>
{news_section_html}
    </section>
  </div>

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
    weather = fetch_weather()

    if not hn_stories and not news_headlines:
        print("error: both Hacker News and Google News fetches failed; nothing to write", file=sys.stderr)
        return 1

    output_dir = "output"
    import os

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{today.isoformat()}.html")

    page_html = render_html(hn_stories, news_headlines, today, weather)
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(page_html)

    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

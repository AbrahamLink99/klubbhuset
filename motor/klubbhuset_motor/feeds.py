"""Hämtar och tolkar RSS- och Atom-flöden."""

from __future__ import annotations

import calendar
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable

import feedparser
import httpx

from .catalog import Source
from .textutil import domain_name, html_to_text, normalize_url

_IMG_SRC = re.compile(r"""(?is)<img[^>]+src=["']([^"']+)["']""")


@dataclass
class FeedItem:
    url: str
    title: str
    published: datetime | None
    text: str
    image_url: str | None = None
    duration: str | None = None
    outlet: str | None = None


@dataclass
class FetchResult:
    source: Source
    items: list[FeedItem] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _to_datetime(struct) -> datetime | None:
    if not struct:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _longest_content(entry) -> str:
    """Välj den längsta texten. GOLF.com har till exempel artikeltexten flera gånger."""
    candidates = [c.get("value", "") for c in entry.get("content", []) or []]
    candidates += [entry.get("summary", ""), entry.get("description", "")]
    best = ""
    best_len = -1
    for candidate in candidates:
        length = len(html_to_text(candidate))
        if length > best_len:
            best, best_len = candidate or "", length
    return best


def _image(entry, content_html: str) -> str | None:
    for media in entry.get("media_content", []) or []:
        url = media.get("url")
        medium = media.get("medium", "image")
        if url and (medium == "image" or re.search(r"\.(jpe?g|png|webp)", url, re.I)):
            return url
    for thumb in entry.get("media_thumbnail", []) or []:
        if thumb.get("url"):
            return thumb["url"]
    for enclosure in entry.get("enclosures", []) or []:
        if (enclosure.get("type") or "").startswith("image/") and enclosure.get("href"):
            return enclosure["href"]
    image = entry.get("image")
    if isinstance(image, dict) and image.get("href"):
        return image["href"]
    match = _IMG_SRC.search(content_html or "")
    return match.group(1) if match else None


def _episode_link(entry) -> str | None:
    if entry.get("link"):
        return entry["link"]
    for enclosure in entry.get("enclosures", []) or []:
        if enclosure.get("href"):
            return enclosure["href"]
    return None


def _outlet(source: Source, entry, url: str) -> str:
    if source.kind == "news_search":
        bing_source = entry.get("news_source")
        if bing_source:
            return str(bing_source).strip()
        src = entry.get("source")
        if isinstance(src, dict) and src.get("title"):
            return src["title"].strip()
        return domain_name(url)
    return source.display_outlet


def parse_feed(source: Source, content: bytes) -> list[FeedItem]:
    # Rå HTML behövs för att kunna rensa bort hela sidomslag (som GOLF.com skickar).
    # Inget av detta visas som HTML – det blir ren text innan det används.
    parsed = feedparser.parse(content, sanitize_html=False)
    if parsed.get("bozo") and not parsed.entries:
        raise ValueError(f"Kunde inte tolka flödet: {parsed.get('bozo_exception')}")
    items: list[FeedItem] = []
    for entry in parsed.entries:
        link = _episode_link(entry) if source.kind == "podcast" else entry.get("link")
        url = normalize_url(link)
        title = html_to_text(entry.get("title", "")).replace("\n\n", " ").strip()
        if not url or not title:
            continue
        content_html = _longest_content(entry)
        items.append(
            FeedItem(
                url=url,
                title=title,
                published=_to_datetime(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                ),
                text=html_to_text(content_html),
                image_url=_image(entry, content_html),
                duration=entry.get("itunes_duration"),
                outlet=_outlet(source, entry, url),
            )
        )
    return items


def fetch_feed(source: Source, client: httpx.Client) -> FetchResult:
    try:
        response = client.get(source.feed)
        response.raise_for_status()
        return FetchResult(source=source, items=parse_feed(source, response.content))
    except Exception as exc:  # noqa: BLE001 – ett trasigt flöde får inte stoppa de andra
        return FetchResult(source=source, error=f"{type(exc).__name__}: {exc}"[:500])


def make_client(user_agent: str, timeout: float) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": user_agent, "Accept": "*/*"},
        timeout=timeout,
        follow_redirects=True,
    )


def fetch_all(
    sources: Iterable[Source],
    client: httpx.Client,
    workers: int = 8,
    bing_delay: float = 3.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[FetchResult]:
    """Hämtar vanliga flöden parallellt och Bing-flöden ett i taget med paus emellan."""
    sources = list(sources)
    normal = [s for s in sources if not s.is_bing]
    bing = [s for s in sources if s.is_bing]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda s: fetch_feed(s, client), normal))

    for index, source in enumerate(bing):
        if index:
            sleep(bing_delay)
        results.append(fetch_feed(source, client))
    return results

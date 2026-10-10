"""Läser en artikelsida: brödtexten och bilden.

Texten används bara som underlag för AI-sammanfattningen. Den visas aldrig i appen
och sparas inte efter att sammanfattningen är skriven. Bilden är sidans delningsbild
(og:image), som appen visar med länk tillbaka till källan.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

import httpx
import trafilatura

_META_IMAGE = re.compile(
    r"""<meta[^>]+(?:property|name)=["'](?:og:image(?::secure_url)?|twitter:image(?::src)?)["'][^>]*>""",
    re.IGNORECASE,
)
_CONTENT = re.compile(r"""content=["']([^"']+)["']""", re.IGNORECASE)


@dataclass
class ArticlePage:
    text: str | None
    image: str | None


def find_share_image(page_html: str) -> str | None:
    for tag in _META_IMAGE.findall(page_html[:200_000]):
        match = _CONTENT.search(tag)
        if match and match.group(1).startswith(("http://", "https://")):
            return html.unescape(match.group(1))
    return None


def fetch_article(url: str, client: httpx.Client) -> ArticlePage | None:
    try:
        response = client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    if "html" not in response.headers.get("content-type", "html"):
        return None
    page_html = response.text
    text = trafilatura.extract(
        page_html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        deduplicate=True,
    )
    return ArticlePage(text=text.strip() if text else None, image=find_share_image(page_html))

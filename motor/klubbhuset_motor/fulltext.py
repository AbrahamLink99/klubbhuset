"""Läser brödtexten från en artikelsida.

Texten används bara som underlag för AI-sammanfattningen. Den visas aldrig i appen
och sparas inte efter att sammanfattningen är skriven.
"""

from __future__ import annotations

import httpx
import trafilatura


def fetch_article_text(url: str, client: httpx.Client) -> str | None:
    try:
        response = client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    if "html" not in response.headers.get("content-type", "html"):
        return None
    text = trafilatura.extract(
        response.text,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        deduplicate=True,
    )
    return text.strip() if text else None

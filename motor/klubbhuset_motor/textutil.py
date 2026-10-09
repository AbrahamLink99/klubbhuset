"""Hjälpfunktioner för text och länkar."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

_WORD = re.compile(r"\w+", re.UNICODE)
_BLOCK_END = re.compile(
    r"(?i)<\s*(br\s*/?|/p|/div|/li|/h[1-6]|/blockquote|/tr|/section|/article)\s*>"
)
_DROP_BLOCKS = re.compile(r"(?is)<(script|style|head|noscript|template|svg)\b.*?</\1\s*>")
_TAG = re.compile(r"(?s)<[^>]+>")
_TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ocid")
_SENTENCE_END = re.compile(r"(?<=[.!?…»”\"])\s+")


def html_to_text(markup: str | None) -> str:
    """Gör om HTML (eller en hel HTML-sida) till ren text med stycken."""
    if not markup:
        return ""
    text = _DROP_BLOCKS.sub(" ", markup)
    text = _BLOCK_END.sub("\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.splitlines()]
    paragraphs: list[str] = []
    for line in lines:
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs)


def word_count(text: str | None) -> int:
    return len(_WORD.findall(text or ""))


def normalize_url(url: str | None) -> str:
    """Samma artikel ska ge samma adress, oavsett spårningsparametrar och omdirigeringar."""
    if not url:
        return ""
    url = url.strip()
    parts = urlsplit(url)
    host = parts.netloc.lower()

    # Bing-nyheter länkar via en omdirigering; den riktiga adressen står i url=
    if host.endswith("bing.com") and "apiclick" in parts.path.lower():
        target = parse_qs(parts.query).get("url", [""])[0]
        if target:
            return normalize_url(target)

    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(_TRACKING_PARAMS)
    ]
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ""))


def domain_name(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def summary_word_cap(source_words: int, share: float, min_words: int, max_words: int) -> int:
    """Hur många ord sammanfattningen får ha.

    Huvudregeln är en andel av originalets längd (standard en fjärdedel). Korta texter
    får ett litet golv så att det blir en läsbar sammanfattning, men aldrig mer än
    60 procent av originalet. Långa texter stoppas vid ett absolut tak.
    """
    if source_words <= 0:
        return 0
    by_share = round(source_words * share)
    floor = min(min_words, round(source_words * 0.6))
    return max(1, min(max(by_share, floor), max_words))


def enforce_word_cap(text: str, cap: int, slack: float = 1.15) -> str:
    """Kortar en text vid en meningsgräns om den är tydligt längre än taket."""
    if cap <= 0 or word_count(text) <= cap * slack:
        return text.strip()
    kept_paragraphs: list[str] = []
    total = 0
    for paragraph in [p.strip() for p in text.split("\n\n") if p.strip()]:
        sentences = _SENTENCE_END.split(paragraph)
        kept: list[str] = []
        for sentence in sentences:
            words = word_count(sentence)
            if total + words > cap:
                break
            kept.append(sentence)
            total += words
        if kept:
            kept_paragraphs.append(" ".join(kept))
        if total >= cap or len(kept) < len(sentences):
            break
    return "\n\n".join(kept_paragraphs).strip()


def make_excerpt(text: str, max_chars: int = 300) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(",;:–-") + "…"

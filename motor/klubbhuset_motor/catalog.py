"""Läser källistan (sources.yaml) och spelarlistan (players.yaml)."""

from __future__ import annotations

import unicodedata
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import yaml

KINDS = {"article", "youtube", "podcast", "news_search"}


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    kind: str
    feed: str
    outlet: str | None = None
    site: str | None = None
    language: str | None = None
    weight: float = 1.0
    paywall: bool = False
    active: bool = True
    player: str | None = None

    @property
    def item_kind(self) -> str:
        """Vilken sorts item källan ger: article, video eller podcast."""
        return {"youtube": "video", "podcast": "podcast"}.get(self.kind, "article")

    @property
    def is_bing(self) -> bool:
        return "bing.com/news" in self.feed

    @property
    def display_outlet(self) -> str:
        return self.outlet or self.name


def load_sources(path: Path) -> list[Source]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    sources: list[Source] = []
    seen: set[str] = set()
    for raw in data.get("sources", []):
        if raw["id"] in seen:
            raise ValueError(f"Källan {raw['id']} finns två gånger i {path}")
        if raw["kind"] not in KINDS:
            raise ValueError(f"Okänd kind '{raw['kind']}' för {raw['id']}")
        seen.add(raw["id"])
        sources.append(
            Source(
                id=raw["id"],
                name=raw["name"],
                kind=raw["kind"],
                feed=raw["feed"],
                outlet=raw.get("outlet"),
                site=raw.get("site"),
                language=raw.get("language"),
                weight=float(raw.get("weight", 1.0)),
                paywall=bool(raw.get("paywall", False)),
                active=bool(raw.get("active", True)),
            )
        )
    return sources


def slugify(text: str) -> str:
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    slug = "".join(c.lower() if c.isalnum() else "-" for c in ascii_text)
    return "-".join(part for part in slug.split("-") if part)


def bing_player_feed(name: str) -> str:
    query = quote_plus(f"golf {name}")
    return f"https://www.bing.com/news/search?q={query}&format=rss&setlang=sv-se&cc=se"


def load_player_sources(path: Path) -> list[Source]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    sources = []
    for raw in data.get("players", []):
        name = raw["name"]
        sources.append(
            Source(
                id=f"player-{slugify(name)}",
                name=f"Spelare: {name}",
                kind="news_search",
                feed=bing_player_feed(name),
                language="sv",
                weight=1.0,
                player=name,
            )
        )
    return sources


def load_catalog(sources_file: Path, players_file: Path) -> list[Source]:
    catalog = load_sources(sources_file)
    if Path(players_file).exists():
        catalog += load_player_sources(players_file)
    return catalog


def due_this_run(source: Source, now: datetime, every_hours: int) -> bool:
    """Spelarflöden hämtas var n:e timme, utspridda så att Bing inte får alla på en gång."""
    if not source.active:
        return False
    if source.player is None:
        return True
    bucket = zlib.crc32(source.id.encode("utf-8")) % every_hours
    return bucket == now.hour % every_hours

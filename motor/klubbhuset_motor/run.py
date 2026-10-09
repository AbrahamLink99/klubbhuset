"""Startar motorn.

    python -m klubbhuset_motor.run                 # en vanlig körning
    python -m klubbhuset_motor.run --check-feeds   # testa bara att flödena svarar
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import feeds, fulltext, pipeline
from .ai import ClaudeSummarizer
from .catalog import load_catalog
from .config import load_settings
from .store import Store


def check_feeds() -> int:
    settings = load_settings()
    catalog = [s for s in load_catalog(settings.sources_file, settings.players_file) if s.active]
    with feeds.make_client(settings.user_agent, settings.fetch_timeout) as client:
        results = feeds.fetch_all(catalog, client, settings.fetch_workers, settings.bing_delay_seconds)
    failed = 0
    for r in sorted(results, key=lambda r: (r.ok, r.source.kind, r.source.id)):
        newest = max((i.published for i in r.items if i.published), default=None)
        status = "OK " if r.ok else "FEL"
        detail = (
            f"{len(r.items):3d} poster, senaste {newest:%Y-%m-%d}" if r.ok and newest
            else f"{len(r.items):3d} poster" if r.ok
            else r.error
        )
        print(f"{status}  {r.source.kind:<11} {r.source.id:<28} {detail}")
        failed += 0 if r.ok else 1
    print(f"\n{len(results) - failed} av {len(results)} flöden svarar.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Klubbhusets motor")
    parser.add_argument("--check-feeds", action="store_true", help="testa bara flödena")
    args = parser.parse_args(argv)

    if args.check_feeds:
        return check_feeds()

    settings = load_settings()
    missing = [n for n, v in [("DATABASE_URL", settings.database_url),
                              ("ANTHROPIC_API_KEY", settings.anthropic_api_key)] if not v]
    if missing:
        print(f"Saknar hemligheter: {', '.join(missing)}", file=sys.stderr)
        return 2

    catalog = load_catalog(settings.sources_file, settings.players_file)
    store = Store(settings.database_url)
    try:
        with feeds.make_client(settings.user_agent, settings.fetch_timeout) as client:
            pipeline.run(
                settings=settings,
                store=store,
                catalog=catalog,
                fetch=lambda due: feeds.fetch_all(
                    due, client, settings.fetch_workers, settings.bing_delay_seconds
                ),
                summarizer=ClaudeSummarizer(settings.anthropic_api_key, settings.model),
                fetch_text=lambda url: fulltext.fetch_article_text(url, client),
                now=datetime.now(timezone.utc),
            )
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

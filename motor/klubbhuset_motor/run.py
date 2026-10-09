"""Startar motorn.

    python -m klubbhuset_motor.run                 # hämta, sammanfatta och bygg sidan
    python -m klubbhuset_motor.run --export-only   # bygg bara sidan från arkivet
    python -m klubbhuset_motor.run --check-feeds   # testa bara att flödena svarar

Arkivet ligger i arkiv/klubbhuset.db och sidan byggs i site/ (ändras med
KLUBBHUSET_DB och KLUBBHUSET_SITE).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from . import feeds, fulltext, pipeline
from .ai import ClaudeSummarizer
from .catalog import load_catalog
from .config import load_settings
from .export import export_site
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

    if os.environ.get("GITHUB_ACTIONS"):
        # Sammanfattning som syns i GitHub-gränssnittet
        total = Counter(r.source.kind for r in results)
        ok = Counter(r.source.kind for r in results if r.ok)
        per_kind = ", ".join(f"{kind} {ok[kind]}/{total[kind]}" for kind in sorted(total))
        print(f"::notice title=Flödestest::{len(results) - failed} av {len(results)} svarar ({per_kind})")
        for r in results:
            if not r.ok:
                print(f"::warning title={r.source.id}::{(r.error or '')[:200]}")
            elif not r.items:
                print(f"::warning title={r.source.id}::Svarar men har inga poster")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Klubbhusets motor")
    parser.add_argument("--check-feeds", action="store_true", help="testa bara flödena")
    parser.add_argument("--export-only", action="store_true", help="bygg bara sidan från arkivet")
    args = parser.parse_args(argv)

    if args.check_feeds:
        return check_feeds()

    settings = load_settings()
    now = datetime.now(timezone.utc)
    store = Store(settings.db_path)
    try:
        if not args.export_only:
            if not settings.anthropic_api_key:
                print("::warning title=AI-nyckel saknas::Lägg in ANTHROPIC_API_KEY under "
                      "Settings → Secrets and variables → Actions för att få sammanfattningar."
                      if os.environ.get("GITHUB_ACTIONS") else
                      "ANTHROPIC_API_KEY saknas – inga sammanfattningar den här gången.")
            catalog = load_catalog(settings.sources_file, settings.players_file)
            summarizer = (ClaudeSummarizer(settings.anthropic_api_key, settings.model)
                          if settings.anthropic_api_key else None)
            with feeds.make_client(settings.user_agent, settings.fetch_timeout) as client:
                pipeline.run(
                    settings=settings,
                    store=store,
                    catalog=catalog,
                    fetch=lambda due: feeds.fetch_all(
                        due, client, settings.fetch_workers, settings.bing_delay_seconds),
                    summarizer=summarizer,
                    fetch_text=lambda url: fulltext.fetch_article_text(url, client),
                    now=now,
                )
        counts = export_site(store, settings.web_dir, settings.site_dir, now)
        print(f"Sidan byggd: {counts['front']} stories på förstasidan, "
              f"{counts['stories']} i arkivet, {counts['media']} videor och avsnitt.")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

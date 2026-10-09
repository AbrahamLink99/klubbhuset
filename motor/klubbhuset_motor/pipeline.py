"""En körning av motorn: hämta → städa → sammanfatta → gruppera → rangordna."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from .ai import Summarizer
from .catalog import Source, due_this_run
from .config import Settings
from .feeds import FetchResult
from .store import Store
from .textutil import summary_word_cap, word_count


@dataclass
class RunStats:
    feeds_ok: int = 0
    feeds_failed: int = 0
    new_items: int = 0
    summarized: int = 0
    skipped: int = 0
    stories_created: int = 0
    stories_updated: int = 0
    synthesized: int = 0
    errors: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def run(
    *,
    settings: Settings,
    store: Store,
    catalog: list[Source],
    fetch: Callable[[list[Source]], list[FetchResult]],
    summarizer: Summarizer | None,
    fetch_text: Callable[[str], str | None],
    now: datetime | None = None,
    log: Callable[[str], None] = print,
    clock: Callable[[], float] = time.monotonic,
) -> RunStats:
    started = clock()
    now = now or datetime.now(timezone.utc)
    stats = RunStats()
    run_id = store.start_run(now)

    # 1. Källor
    store.sync_sources(catalog, now)
    due = [s for s in catalog if due_this_run(s, now, settings.player_feed_every_hours)]
    log(f"Hämtar {len(due)} av {len(catalog)} flöden …")

    # 2. Hämta och spara nya items
    min_published = now - timedelta(hours=settings.lookback_hours)
    for result in fetch(due):
        if result.ok:
            new = store.insert_items(result.source, result.items, min_published, now)
            store.mark_source_checked(result.source.id, None, new, now)
            stats.feeds_ok += 1
            stats.new_items += new
        else:
            store.mark_source_checked(result.source.id, result.error, 0, now)
            stats.feeds_failed += 1
            stats.errors.append({"source": result.source.id, "error": result.error})
    log(f"Flöden: {stats.feeds_ok} ok, {stats.feeds_failed} fel. Nya poster: {stats.new_items}.")

    if summarizer is None:
        log("Ingen AI-nyckel – artiklarna sparas och sammanfattas när nyckeln finns på plats.")
    else:
        _summarize(settings, store, summarizer, fetch_text, now, stats, started, clock, log)

    # 5. Rangordna
    store.update_scores(now)
    store.finish_run(run_id, stats.as_dict(), now)
    log(
        f"Klart: {stats.summarized} sammanfattade, {stats.skipped} bortsorterade, "
        f"{stats.stories_created} nya stories, {stats.stories_updated} uppdaterade, "
        f"{stats.synthesized} sammanvävda, {len(stats.errors)} fel."
    )
    return stats


def _summarize(settings, store, summarizer, fetch_text, now, stats, started, clock, log) -> None:
    # 3. Sammanfatta och gruppera artiklar
    candidates = store.candidate_stories(now, settings.story_window_hours)
    known_players = store.known_players()
    pending = store.pending_articles(settings.max_articles_per_run)
    log(f"Sammanfattar upp till {len(pending)} artiklar …")

    for item in pending:
        if clock() - started > settings.time_budget_seconds:
            log("Tidsbudgeten är slut – resten tas nästa körning.")
            break
        try:
            text = item.get("pending_text") or item.get("excerpt") or ""
            words = word_count(text)
            full = words >= settings.min_words_for_feed_text
            if not full and not item["paywall"]:
                page_text = fetch_text(item["url"])
                if page_text and word_count(page_text) > words:
                    text, words = page_text, word_count(page_text)
                    full = words >= settings.min_words_for_feed_text
            if words == 0:
                text, words = item["original_title"], word_count(item["original_title"])

            cap = summary_word_cap(
                words, settings.summary_max_share, settings.summary_min_words, settings.summary_max_words
            )
            result = summarizer.summarize_article(
                outlet=item["outlet"],
                original_title=item["original_title"],
                published=item["published_dt"],
                text=text,
                is_full_text=full,
                source_words=words,
                word_cap=cap,
                candidates=candidates,
                known_players=known_players,
            )
            if not result.relevant:
                store.mark_item_skipped(item["id"])
                stats.skipped += 1
                continue

            if result.same_story_id:
                story_id = result.same_story_id
                store.attach_to_story(story_id, item, result, now)
                stats.stories_updated += 1
            else:
                story_id = store.create_story(item, result, now)
                candidates.insert(0, {"id": story_id, "title_sv": result.title_sv,
                                      "section": result.section, "outlet_count": 1})
                stats.stories_created += 1
            store.save_article(item["id"], result, story_id, words)
            stats.summarized += 1
        except Exception as exc:  # noqa: BLE001 – en trasig artikel får inte stoppa körningen
            error = f"{type(exc).__name__}: {exc}"
            store.mark_item_failed(item["id"], error)
            stats.errors.append({"item": item["id"], "error": error[:300]})

    # 4. Väv ihop stories med flera källor
    for story in store.stories_needing_synthesis(settings.max_story_syntheses_per_run):
        if clock() - started > settings.time_budget_seconds:
            break
        items = store.story_items(story["id"])
        if len(items) < 2:
            store.clear_synthesis_flag(story["id"])
            continue
        cap = min(settings.story_summary_max_words, sum(word_count(i["summary"]) for i in items))
        try:
            store.save_story(story["id"], summarizer.synthesize_story(items=items, word_cap=cap), now)
            stats.synthesized += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors.append({"story": story["id"], "error": f"{type(exc).__name__}: {exc}"[:300]})

"""Allt som läser och skriver i databasen."""

from __future__ import annotations

from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .ai import ArticleResult, StoryResult
from .catalog import Source
from .feeds import FeedItem
from .textutil import make_excerpt, word_count


class Store:
    def __init__(self, dsn: str):
        self.conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    def close(self) -> None:
        self.conn.close()

    # --- Källor -------------------------------------------------------------
    def sync_sources(self, sources: list[Source]) -> None:
        with self.conn.cursor() as cur:
            for s in sources:
                cur.execute(
                    """
                    insert into sources (id, name, outlet, kind, site, feed, language, weight,
                                         paywall, active, player, updated_at)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    on conflict (id) do update set
                      name = excluded.name, outlet = excluded.outlet, kind = excluded.kind,
                      site = excluded.site, feed = excluded.feed, language = excluded.language,
                      weight = excluded.weight, paywall = excluded.paywall,
                      active = excluded.active, player = excluded.player, updated_at = now()
                    """,
                    (s.id, s.name, s.outlet, s.kind, s.site, s.feed, s.language, s.weight,
                     s.paywall, s.active, s.player),
                )
            cur.execute(
                "update sources set active = false, updated_at = now() where not (id = any(%s))",
                ([s.id for s in sources],),
            )

    def mark_source_checked(self, source_id: str, error: str | None, new_items: int) -> None:
        self.conn.execute(
            """
            update sources set
              last_checked_at = now(),
              last_ok_at = case when %(error)s::text is null then now() else last_ok_at end,
              last_error = %(error)s,
              last_new_item_at = case when %(new)s > 0 then now() else last_new_item_at end
            where id = %(id)s
            """,
            {"id": source_id, "error": error, "new": new_items},
        )

    # --- Items --------------------------------------------------------------
    def insert_items(self, source: Source, items: list[FeedItem], min_published: datetime) -> int:
        """Lägger in nya items. Gamla och redan kända hoppas över."""
        new = 0
        with self.conn.cursor() as cur:
            for item in items:
                if item.published and item.published < min_published:
                    continue
                is_article = source.item_kind == "article"
                cur.execute(
                    """
                    insert into items (source_id, kind, url, outlet, original_title, excerpt,
                                       image_url, duration, published_at, source_words,
                                       pending_text, status)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()), %s, %s, %s)
                    on conflict (url) do nothing
                    returning id
                    """,
                    (
                        source.id,
                        source.item_kind,
                        item.url,
                        item.outlet or source.display_outlet,
                        item.title,
                        make_excerpt(item.text) if item.text else None,
                        item.image_url,
                        item.duration,
                        item.published,
                        word_count(item.text) if is_article else None,
                        item.text if is_article else None,
                        "new" if is_article else "ready",
                    ),
                )
                if cur.fetchone():
                    new += 1
        return new

    def pending_articles(self, limit: int) -> list[dict]:
        return self.conn.execute(
            """
            select i.*, s.paywall, s.weight as source_weight
            from items i join sources s on s.id = i.source_id
            where i.kind = 'article' and i.status in ('new', 'failed') and i.attempts < 3
            order by i.published_at desc nulls last
            limit %s
            """,
            (limit,),
        ).fetchall()

    def save_article(self, item_id: int, result: ArticleResult, story_id: int, source_words: int) -> None:
        self.conn.execute(
            """
            update items set status = 'ready', title_sv = %s, ingress = %s, summary = %s,
              section = %s, tags = %s, players = %s, story_id = %s, source_words = %s,
              pending_text = null, last_error = null, attempts = attempts + 1
            where id = %s
            """,
            (result.title_sv, result.ingress, result.summary, result.section, result.tags,
             result.players, story_id, source_words, item_id),
        )

    def mark_item_skipped(self, item_id: int) -> None:
        self.conn.execute(
            "update items set status = 'skipped', pending_text = null, attempts = attempts + 1 where id = %s",
            (item_id,),
        )

    def mark_item_failed(self, item_id: int, error: str) -> None:
        self.conn.execute(
            """
            update items set status = 'failed', last_error = %s, attempts = attempts + 1,
              pending_text = case when attempts + 1 >= 3 then null else pending_text end
            where id = %s
            """,
            (error[:500], item_id),
        )

    # --- Stories ------------------------------------------------------------
    def candidate_stories(self, window_hours: int, limit: int = 150) -> list[dict]:
        return self.conn.execute(
            """
            select id, title_sv, section, outlet_count from stories
            where last_published_at > now() - make_interval(hours => %s)
            order by last_published_at desc limit %s
            """,
            (window_hours, limit),
        ).fetchall()

    def create_story(self, item: dict, result: ArticleResult) -> int:
        row = self.conn.execute(
            """
            insert into stories (section, title_sv, ingress, summary, tags, players, outlets,
                                 outlet_count, weight, image_url, first_published_at,
                                 last_published_at)
            values (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s)
            returning id
            """,
            (result.section, result.title_sv, result.ingress, result.summary, result.tags,
             result.players, [item["outlet"]], item["source_weight"], item["image_url"],
             item["published_at"], item["published_at"]),
        ).fetchone()
        return int(row["id"])

    def attach_to_story(self, story_id: int, item: dict, result: ArticleResult) -> None:
        self.conn.execute(
            """
            update stories set
              outlets = case when %(outlet)s = any(outlets) then outlets
                             else array_append(outlets, %(outlet)s) end,
              outlet_count = cardinality(case when %(outlet)s = any(outlets) then outlets
                                              else array_append(outlets, %(outlet)s) end),
              tags = (select array(select distinct unnest(tags || %(tags)s::text[]))),
              players = (select array(select distinct unnest(players || %(players)s::text[]))),
              weight = greatest(weight, %(weight)s),
              image_url = coalesce(image_url, %(image)s),
              last_published_at = greatest(last_published_at, %(published)s),
              needs_synthesis = true,
              updated_at = now()
            where id = %(id)s
            """,
            {"id": story_id, "outlet": item["outlet"], "tags": result.tags,
             "players": result.players, "weight": item["source_weight"],
             "image": item["image_url"], "published": item["published_at"]},
        )

    def stories_needing_synthesis(self, limit: int) -> list[dict]:
        return self.conn.execute(
            """
            select id from stories
            where needs_synthesis and outlet_count >= 2
            order by last_published_at desc limit %s
            """,
            (limit,),
        ).fetchall()

    def story_items(self, story_id: int, limit: int = 8) -> list[dict]:
        return self.conn.execute(
            """
            select outlet, original_title, title_sv, summary from items
            where story_id = %s and status = 'ready'
            order by published_at asc limit %s
            """,
            (story_id, limit),
        ).fetchall()

    def save_story(self, story_id: int, result: StoryResult) -> None:
        self.conn.execute(
            """
            update stories set title_sv = %s, ingress = %s, summary = %s, angles = %s,
              needs_synthesis = false, updated_at = now()
            where id = %s
            """,
            (result.title_sv, result.ingress, result.summary, Jsonb(result.angles), story_id),
        )

    def clear_synthesis_flag(self, story_id: int) -> None:
        self.conn.execute("update stories set needs_synthesis = false where id = %s", (story_id,))

    def update_scores(self) -> None:
        """Poäng = källans vikt × fler publikationer × färskhet (halveras ungefär var 17:e timme)."""
        self.conn.execute(
            """
            update stories set score = weight * (1 + ln(greatest(outlet_count, 1)))
              * exp(-extract(epoch from (now() - last_published_at)) / 3600.0 / 24.0)
            where last_published_at > now() - interval '8 days' or score > 0
            """
        )

    def known_players(self) -> list[str]:
        rows = self.conn.execute(
            "select player from sources where player is not null and active order by player"
        ).fetchall()
        return [r["player"] for r in rows]

    # --- Körningar ----------------------------------------------------------
    def start_run(self) -> int:
        return int(self.conn.execute("insert into runs default values returning id").fetchone()["id"])

    def finish_run(self, run_id: int, stats: dict) -> None:
        self.conn.execute(
            """
            update runs set finished_at = now(), feeds_ok = %s, feeds_failed = %s,
              new_items = %s, summarized = %s, stories_created = %s, stories_updated = %s,
              errors = %s
            where id = %s
            """,
            (stats["feeds_ok"], stats["feeds_failed"], stats["new_items"], stats["summarized"],
             stats["stories_created"], stats["stories_updated"],
             Jsonb(stats["errors"][:50]), run_id),
        )

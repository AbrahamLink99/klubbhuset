"""Arkivet: en SQLite-fil som motorn hämtar från grenen `arkiv`, uppdaterar och sparar tillbaka.

Hela artiklar sparas aldrig – bara rubrik, kort utdrag och AI-sammanfattning.
Flödets text ligger kvar i `pending_text` bara tills artikeln är sammanfattad.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .ai import ArticleResult, StoryResult
from .catalog import Source
from .feeds import FeedItem
from .textutil import make_excerpt, word_count

SCHEMA = """
create table if not exists sources (
  id text primary key, name text not null, outlet text, kind text not null, site text,
  feed text not null, language text, weight real not null default 1.0,
  paywall integer not null default 0, active integer not null default 1, player text,
  last_checked_at text, last_ok_at text, last_new_item_at text, last_error text, updated_at text
);
create table if not exists stories (
  id integer primary key autoincrement, section text not null, title_sv text not null,
  ingress text not null, summary text not null, angles text not null default '[]',
  tags text not null default '[]', players text not null default '[]',
  outlets text not null default '[]', outlet_count integer not null default 1,
  weight real not null default 1.0, image_url text, score real not null default 0,
  first_published_at text not null, last_published_at text not null,
  needs_synthesis integer not null default 0, created_at text not null, updated_at text not null
);
create index if not exists stories_last_published on stories (last_published_at);
create table if not exists items (
  id integer primary key autoincrement, source_id text not null, kind text not null,
  url text not null unique, outlet text not null, original_title text not null, excerpt text,
  image_url text, duration text, published_at text not null, fetched_at text not null,
  source_words integer, pending_text text, status text not null default 'new',
  attempts integer not null default 0, last_error text, title_sv text, ingress text,
  summary text, section text, tags text not null default '[]', players text not null default '[]',
  story_id integer
);
create index if not exists items_status on items (status, published_at);
create index if not exists items_kind on items (kind, published_at);
create index if not exists items_story on items (story_id);
create table if not exists runs (
  id integer primary key autoincrement, started_at text not null, finished_at text,
  feeds_ok integer not null default 0, feeds_failed integer not null default 0,
  new_items integer not null default 0, summarized integer not null default 0,
  stories_created integer not null default 0, stories_updated integer not null default 0,
  errors text not null default '[]'
);
"""

STORY_JSON_FIELDS = ("angles", "tags", "players", "outlets")
ITEM_JSON_FIELDS = ("tags", "players")


def iso(value: datetime | None) -> str | None:
    """Alla tider sparas i samma format, i UTC, så att de går att jämföra som text."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _decode(row: sqlite3.Row | None, json_fields: tuple[str, ...]) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    for key in json_fields:
        if key in data and isinstance(data[key], str):
            data[key] = json.loads(data[key])
    for key in ("paywall", "active", "needs_synthesis"):
        if key in data and data[key] is not None:
            data[key] = bool(data[key])
    return data


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.commit()
        self.conn.execute("vacuum")
        self.conn.close()

    def _rows(self, sql: str, params=(), json_fields: tuple[str, ...] = ()) -> list[dict]:
        return [_decode(r, json_fields) for r in self.conn.execute(sql, params).fetchall()]

    def _write(self, sql: str, params=()) -> sqlite3.Cursor:
        cursor = self.conn.execute(sql, params)
        self.conn.commit()
        return cursor

    # --- Källor -------------------------------------------------------------
    def sync_sources(self, sources: list[Source], now: datetime) -> None:
        for s in sources:
            self.conn.execute(
                """
                insert into sources (id, name, outlet, kind, site, feed, language, weight,
                                     paywall, active, player, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict (id) do update set
                  name = excluded.name, outlet = excluded.outlet, kind = excluded.kind,
                  site = excluded.site, feed = excluded.feed, language = excluded.language,
                  weight = excluded.weight, paywall = excluded.paywall, active = excluded.active,
                  player = excluded.player, updated_at = excluded.updated_at
                """,
                (s.id, s.name, s.outlet, s.kind, s.site, s.feed, s.language, s.weight,
                 int(s.paywall), int(s.active), s.player, iso(now)),
            )
        ids = [s.id for s in sources]
        self.conn.execute(
            f"update sources set active = 0 where id not in ({','.join('?' * len(ids))})", ids
        )
        self.conn.commit()

    def mark_source_checked(self, source_id: str, error: str | None, new_items: int, now: datetime) -> None:
        stamp = iso(now)
        self._write(
            """
            update sources set last_checked_at = ?,
              last_ok_at = case when ? is null then ? else last_ok_at end,
              last_error = ?,
              last_new_item_at = case when ? > 0 then ? else last_new_item_at end
            where id = ?
            """,
            (stamp, error, stamp, error, new_items, stamp, source_id),
        )

    def sources(self) -> list[dict]:
        return self._rows("select * from sources where active = 1 order by kind, name")

    # --- Items --------------------------------------------------------------
    def insert_items(self, source: Source, items: list[FeedItem], min_published: datetime, now: datetime) -> int:
        new = 0
        is_article = source.item_kind == "article"
        for item in items:
            if item.published and item.published < min_published:
                continue
            cursor = self.conn.execute(
                """
                insert into items (source_id, kind, url, outlet, original_title, excerpt, image_url,
                                   duration, published_at, fetched_at, source_words, pending_text, status)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict (url) do nothing
                """,
                (
                    source.id, source.item_kind, item.url, item.outlet or source.display_outlet,
                    item.title, make_excerpt(item.text) if item.text else None, item.image_url,
                    item.duration, iso(item.published or now), iso(now),
                    word_count(item.text) if is_article else None,
                    item.text if is_article else None,
                    "new" if is_article else "ready",
                ),
            )
            new += cursor.rowcount
        self.conn.commit()
        return new

    def pending_articles(self, limit: int) -> list[dict]:
        rows = self._rows(
            """
            select i.*, s.paywall as paywall, s.weight as source_weight
            from items i join sources s on s.id = i.source_id
            where i.kind = 'article' and i.status in ('new', 'failed') and i.attempts < 3
            order by i.published_at desc limit ?
            """,
            (limit,),
            ITEM_JSON_FIELDS,
        )
        for row in rows:
            row["published_dt"] = parse_iso(row["published_at"])
        return rows

    def save_article(self, item_id: int, result: ArticleResult, story_id: int, source_words: int) -> None:
        self._write(
            """
            update items set status = 'ready', title_sv = ?, ingress = ?, summary = ?, section = ?,
              tags = ?, players = ?, story_id = ?, source_words = ?, pending_text = null,
              last_error = null, attempts = attempts + 1
            where id = ?
            """,
            (result.title_sv, result.ingress, result.summary, result.section,
             json.dumps(result.tags, ensure_ascii=False), json.dumps(result.players, ensure_ascii=False),
             story_id, source_words, item_id),
        )

    def mark_item_skipped(self, item_id: int) -> None:
        self._write(
            "update items set status = 'skipped', pending_text = null, attempts = attempts + 1 where id = ?",
            (item_id,),
        )

    def mark_item_failed(self, item_id: int, error: str) -> None:
        self._write(
            """
            update items set status = 'failed', last_error = ?, attempts = attempts + 1,
              pending_text = case when attempts + 1 >= 3 then null else pending_text end
            where id = ?
            """,
            (error[:500], item_id),
        )

    def media(self, limit: int) -> list[dict]:
        return self._rows(
            """
            select id, kind, outlet, original_title, url, image_url, duration, published_at
            from items where kind in ('video', 'podcast') order by published_at desc limit ?
            """,
            (limit,),
        )

    # --- Stories ------------------------------------------------------------
    def candidate_stories(self, now: datetime, window_hours: int, limit: int = 150) -> list[dict]:
        return self._rows(
            """
            select id, title_sv, section, outlet_count from stories
            where last_published_at > ? order by last_published_at desc limit ?
            """,
            (iso(now - timedelta(hours=window_hours)), limit),
        )

    def create_story(self, item: dict, result: ArticleResult, now: datetime) -> int:
        cursor = self._write(
            """
            insert into stories (section, title_sv, ingress, summary, tags, players, outlets,
                                 outlet_count, weight, image_url, first_published_at,
                                 last_published_at, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (result.section, result.title_sv, result.ingress, result.summary,
             json.dumps(result.tags, ensure_ascii=False), json.dumps(result.players, ensure_ascii=False),
             json.dumps([item["outlet"]], ensure_ascii=False), item["source_weight"], item["image_url"],
             item["published_at"], item["published_at"], iso(now), iso(now)),
        )
        return int(cursor.lastrowid)

    def story(self, story_id: int) -> dict | None:
        return _decode(
            self.conn.execute("select * from stories where id = ?", (story_id,)).fetchone(),
            STORY_JSON_FIELDS,
        )

    def attach_to_story(self, story_id: int, item: dict, result: ArticleResult, now: datetime) -> None:
        story = self.story(story_id)
        outlets = story["outlets"] + ([item["outlet"]] if item["outlet"] not in story["outlets"] else [])
        tags = story["tags"] + [t for t in result.tags if t not in story["tags"]]
        players = story["players"] + [p for p in result.players if p not in story["players"]]
        self._write(
            """
            update stories set outlets = ?, outlet_count = ?, tags = ?, players = ?,
              weight = max(weight, ?), image_url = coalesce(image_url, ?),
              last_published_at = max(last_published_at, ?), needs_synthesis = 1, updated_at = ?
            where id = ?
            """,
            (json.dumps(outlets, ensure_ascii=False), len(outlets),
             json.dumps(tags[:12], ensure_ascii=False), json.dumps(players[:12], ensure_ascii=False),
             item["source_weight"], item["image_url"], item["published_at"], iso(now), story_id),
        )

    def stories_needing_synthesis(self, limit: int) -> list[dict]:
        return self._rows(
            """
            select id from stories where needs_synthesis = 1 and outlet_count >= 2
            order by last_published_at desc limit ?
            """,
            (limit,),
        )

    def story_items(self, story_id: int, limit: int = 8) -> list[dict]:
        return self._rows(
            """
            select outlet, original_title, title_sv, summary, url, published_at, source_words
            from items where story_id = ? and status = 'ready' order by published_at asc limit ?
            """,
            (story_id, limit),
        )

    def save_story(self, story_id: int, result: StoryResult, now: datetime) -> None:
        self._write(
            """
            update stories set title_sv = ?, ingress = ?, summary = ?, angles = ?,
              needs_synthesis = 0, updated_at = ?
            where id = ?
            """,
            (result.title_sv, result.ingress, result.summary,
             json.dumps(result.angles, ensure_ascii=False), iso(now), story_id),
        )

    def clear_synthesis_flag(self, story_id: int) -> None:
        self._write("update stories set needs_synthesis = 0 where id = ?", (story_id,))

    def update_scores(self, now: datetime) -> None:
        """Poäng = källans vikt × fler publikationer × färskhet (halveras ungefär var 17:e timme)."""
        rows = self._rows(
            "select id, weight, outlet_count, last_published_at from stories where last_published_at > ? or score > 0",
            (iso(now - timedelta(days=8)),),
        )
        for row in rows:
            age_hours = max(0.0, (now - parse_iso(row["last_published_at"])).total_seconds() / 3600)
            score = row["weight"] * (1 + math.log(max(row["outlet_count"], 1))) * math.exp(-age_hours / 24)
            self.conn.execute("update stories set score = ? where id = ?", (round(score, 6), row["id"]))
        self.conn.commit()

    def all_stories(self) -> list[dict]:
        return self._rows("select * from stories order by last_published_at desc", (), STORY_JSON_FIELDS)

    def items_for_stories(self) -> dict[int, list[dict]]:
        grouped: dict[int, list[dict]] = {}
        for row in self._rows(
            """
            select story_id, outlet, original_title, url, published_at, source_words from items
            where story_id is not null and status = 'ready' order by published_at asc
            """
        ):
            grouped.setdefault(row.pop("story_id"), []).append(row)
        return grouped

    def known_players(self) -> list[str]:
        return [r["player"] for r in self._rows(
            "select player from sources where player is not null and active = 1 order by player")]

    # --- Körningar ----------------------------------------------------------
    def start_run(self, now: datetime) -> int:
        return int(self._write("insert into runs (started_at) values (?)", (iso(now),)).lastrowid)

    def finish_run(self, run_id: int, stats: dict, now: datetime) -> None:
        self._write(
            """
            update runs set finished_at = ?, feeds_ok = ?, feeds_failed = ?, new_items = ?,
              summarized = ?, stories_created = ?, stories_updated = ?, errors = ?
            where id = ?
            """,
            (iso(now), stats["feeds_ok"], stats["feeds_failed"], stats["new_items"],
             stats["summarized"], stats["stories_created"], stats["stories_updated"],
             json.dumps(stats["errors"][:50], ensure_ascii=False), run_id),
        )

    def last_run(self) -> dict | None:
        rows = self._rows(
            "select finished_at, new_items, summarized from runs where finished_at is not null order by id desc limit 1"
        )
        return rows[0] if rows else None

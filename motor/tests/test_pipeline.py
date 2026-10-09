"""Kör hela motorn mot en riktig Postgres, med låtsasflöden och låtsas-AI."""

from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from klubbhuset_motor.ai import ArticleResult, StoryResult
from klubbhuset_motor.catalog import Source
from klubbhuset_motor.config import Settings
from klubbhuset_motor.feeds import FeedItem, FetchResult
from klubbhuset_motor.pipeline import run
from klubbhuset_motor.store import Store

NOW = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)
GOLFCOM = Source(id="golfcom", name="GOLF.com", outlet="GOLF.com", kind="article", feed="https://golf.com/feed/")
SVENSKGOLF = Source(id="svenskgolf", name="Svensk Golf", outlet="Svensk Golf", kind="article",
                    feed="https://www.svenskgolf.se/feed/", language="sv", weight=1.0)
YOUTUBE = Source(id="yt-rick", name="Rick Shiels Golf", kind="youtube", feed="https://www.youtube.com/feeds/x")
BROKEN = Source(id="broken", name="Trasig", kind="article", feed="https://broken.example/feed", weight=0.5)
CATALOG = [GOLFCOM, SVENSKGOLF, YOUTUBE, BROKEN]

LONG_TEXT = "Ryder Cup spelas på Adare Manor. " * 200  # 1 200 ord


def fake_fetch(due):
    return [
        FetchResult(GOLFCOM, [FeedItem(
            url="https://golf.com/news/ryder-cup-2027", title="Ryder Cup 2027: Everything you need to know",
            published=NOW - timedelta(hours=1), text=LONG_TEXT, image_url="https://golf.com/adare.jpg")]),
        FetchResult(SVENSKGOLF, [
            FeedItem(url="https://www.svenskgolf.se/svenskarna-adare", title="Så tar sig svenskarna till Adare Manor",
                     published=NOW - timedelta(minutes=30), text="Kort ingress om svenskarna."),
            FeedItem(url="https://www.svenskgolf.se/rea", title="Rea på golfbollar",
                     published=NOW - timedelta(minutes=40), text="Köp nu."),
            FeedItem(url="https://www.svenskgolf.se/gammal", title="Gammal nyhet",
                     published=NOW - timedelta(days=10), text="Gammalt."),
        ]),
        FetchResult(YOUTUBE, [FeedItem(
            url="https://www.youtube.com/watch?v=abc", title="Testing every new driver",
            published=NOW - timedelta(hours=2), text="Beskrivning", image_url="https://i.ytimg.com/abc.jpg")]),
        FetchResult(BROKEN, error="HTTPStatusError: 404"),
    ]


def fetch_text(url):
    return "Hela texten om svenskarna och Ryder Cup. " * 60 if "svenskgolf" in url else None  # 420 ord


class FakeSummarizer:
    def __init__(self):
        self.calls = []
        self.story_calls = []

    def summarize_article(self, *, original_title, candidates, word_cap, is_full_text, **_):
        self.calls.append({"title": original_title, "cap": word_cap, "full": is_full_text,
                           "candidates": [c["id"] for c in candidates]})
        if original_title.startswith("Rea"):
            return ArticleResult(False, "", "", "", "Utrustning")
        return ArticleResult(
            relevant=True,
            title_sv=f"Svensk rubrik: {original_title}",
            ingress="En ingress.",
            summary=" ".join(["ord"] * word_cap),
            section="Touren",
            tags=["Ryder Cup 2027"],
            players=[],
            same_story_id=candidates[0]["id"] if candidates else None,
        )

    def synthesize_story(self, *, items, word_cap):
        self.story_calls.append((len(items), word_cap))
        return StoryResult("Sammanvävd rubrik", "Sammanvävd ingress.", "Sammanvävd text.",
                           [{"outlet": i["outlet"], "angle": "En vinkel."} for i in items])


def query(url, sql, *args):
    with psycopg.connect(url, row_factory=dict_row) as conn:
        return conn.execute(sql, args).fetchall()


def test_full_run_groups_two_outlets_into_one_story(db_url):
    store = Store(db_url)
    summarizer = FakeSummarizer()
    settings = Settings(database_url=db_url, anthropic_api_key="test")

    stats = run(settings=settings, store=store, catalog=CATALOG, fetch=fake_fetch,
                summarizer=summarizer, fetch_text=fetch_text, now=NOW, log=lambda _: None)

    assert (stats.feeds_ok, stats.feeds_failed, stats.new_items) == (3, 1, 4)
    assert (stats.summarized, stats.skipped) == (2, 1)
    assert (stats.stories_created, stats.stories_updated, stats.synthesized) == (1, 1, 1)

    caps = {c["title"]: (c["cap"], c["full"]) for c in summarizer.calls}
    assert caps["Ryder Cup 2027: Everything you need to know"] == (300, True)   # 1 200 ord → en fjärdedel
    assert caps["Så tar sig svenskarna till Adare Manor"] == (105, True)        # sidan hämtades: 420 ord
    assert summarizer.story_calls == [(2, 405)]                                 # taket = summan av delarna

    [story] = query(db_url, "select * from stories")
    assert story["title_sv"] == "Sammanvävd rubrik"
    assert sorted(story["outlets"]) == ["GOLF.com", "Svensk Golf"] and story["outlet_count"] == 2
    assert len(story["angles"]) == 2 and not story["needs_synthesis"]
    assert story["image_url"] == "https://golf.com/adare.jpg" and story["score"] > 0

    statuses = {r["url"]: r["status"] for r in query(db_url, "select url, status from items")}
    assert statuses == {
        "https://golf.com/news/ryder-cup-2027": "ready",
        "https://www.svenskgolf.se/svenskarna-adare": "ready",
        "https://www.svenskgolf.se/rea": "skipped",
        "https://www.youtube.com/watch?v=abc": "ready",
    }
    assert query(db_url, "select count(*) as n from items where pending_text is not null")[0]["n"] == 0
    [broken] = query(db_url, "select last_error, last_ok_at from sources where id = 'broken'")
    assert "404" in broken["last_error"] and broken["last_ok_at"] is None

    # En andra körning med samma flöden ska inte skapa dubbletter
    stats2 = run(settings=settings, store=Store(db_url), catalog=CATALOG, fetch=fake_fetch,
                 summarizer=summarizer, fetch_text=fetch_text, now=NOW, log=lambda _: None)
    assert (stats2.new_items, stats2.summarized, stats2.stories_created) == (0, 0, 0)
    assert query(db_url, "select count(*) as n from runs where finished_at is not null")[0]["n"] == 2


def test_failed_article_is_retried_then_given_up(db_url):
    class Exploding(FakeSummarizer):
        def summarize_article(self, **kwargs):
            raise RuntimeError("API nere")

    settings = Settings(database_url=db_url, anthropic_api_key="test")
    for _ in range(4):
        run(settings=settings, store=Store(db_url), catalog=[GOLFCOM],
            fetch=lambda due: [fake_fetch(due)[0]], summarizer=Exploding(),
            fetch_text=lambda url: None, now=NOW, log=lambda _: None)
    [item] = query(db_url, "select status, attempts, pending_text, last_error from items")
    assert item["status"] == "failed" and item["attempts"] == 3
    assert item["pending_text"] is None and "API nere" in item["last_error"]

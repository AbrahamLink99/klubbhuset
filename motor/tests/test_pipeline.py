"""Kör hela motorn mot ett riktigt arkiv, med låtsasflöden och låtsas-AI."""

import json
from datetime import datetime, timedelta, timezone

from klubbhuset_motor.ai import ArticleResult, StoryResult
from klubbhuset_motor.catalog import Source
from klubbhuset_motor.config import Settings
from klubbhuset_motor.export import export_site
from klubbhuset_motor.feeds import FeedItem, FetchResult
from klubbhuset_motor.fulltext import ArticlePage
from klubbhuset_motor.pipeline import run
from klubbhuset_motor.store import Store

NOW = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)
GOLFCOM = Source(id="golfcom", name="GOLF.com", outlet="GOLF.com", kind="article", feed="https://golf.com/feed/")
SVENSKGOLF = Source(id="svenskgolf", name="Svensk Golf", outlet="Svensk Golf", kind="article",
                    feed="https://www.svenskgolf.se/feed/", language="sv", weight=1.0)
YOUTUBE = Source(id="yt-rick", name="Rick Shiels Golf", kind="youtube", feed="https://www.youtube.com/feeds/x")
BROKEN = Source(id="broken", name="Trasig", kind="article", feed="https://broken.example/feed", weight=0.5)
CATALOG = [GOLFCOM, SVENSKGOLF, YOUTUBE, BROKEN]
SETTINGS = Settings(anthropic_api_key="test")

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
    if "svenskgolf" not in url:
        return None
    return ArticlePage(text="Hela texten om svenskarna och Ryder Cup. " * 60,  # 420 ord
                       image="https://www.svenskgolf.se/bild.jpg")


class FakeSummarizer:
    def __init__(self):
        self.calls = []
        self.story_calls = []

    def summarize_article(self, *, original_title, candidates, word_cap, is_full_text, **_):
        self.calls.append({"title": original_title, "cap": word_cap, "full": is_full_text})
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


def rows(store, sql, *args):
    return [dict(r) for r in store.conn.execute(sql, args).fetchall()]


def test_full_run_groups_two_outlets_into_one_story(store):
    summarizer = FakeSummarizer()
    stats = run(settings=SETTINGS, store=store, catalog=CATALOG, fetch=fake_fetch,
                summarizer=summarizer, fetch_page=fetch_text, now=NOW, log=lambda _: None)

    assert (stats.feeds_ok, stats.feeds_failed, stats.new_items) == (3, 1, 4)
    assert (stats.summarized, stats.skipped) == (2, 1)
    assert (stats.stories_created, stats.stories_updated, stats.synthesized) == (1, 1, 1)

    caps = {c["title"]: (c["cap"], c["full"]) for c in summarizer.calls}
    assert caps["Ryder Cup 2027: Everything you need to know"] == (300, True)   # en fjärdedel av 1 200 ord
    assert caps["Så tar sig svenskarna till Adare Manor"] == (105, True)        # sidan hämtades: 420 ord
    assert summarizer.story_calls == [(2, 405)]                                 # taket = summan av delarna

    [story] = store.all_stories()
    assert story["title_sv"] == "Sammanvävd rubrik"
    assert sorted(story["outlets"]) == ["GOLF.com", "Svensk Golf"] and story["outlet_count"] == 2
    assert len(story["angles"]) == 2 and not story["needs_synthesis"]
    assert story["image_url"] == "https://www.svenskgolf.se/bild.jpg" and story["score"] > 0  # första artikelns bild

    statuses = {r["url"]: r["status"] for r in rows(store, "select url, status from items")}
    assert statuses == {
        "https://golf.com/news/ryder-cup-2027": "ready",
        "https://www.svenskgolf.se/svenskarna-adare": "ready",
        "https://www.svenskgolf.se/rea": "skipped",
        "https://www.youtube.com/watch?v=abc": "ready",
    }
    assert rows(store, "select count(*) as n from items where pending_text is not null")[0]["n"] == 0
    [sg] = rows(store, "select image_url from items where url = 'https://www.svenskgolf.se/svenskarna-adare'")
    assert sg["image_url"] == "https://www.svenskgolf.se/bild.jpg"  # bilden hämtades från artikelsidan
    [broken] = rows(store, "select last_error, last_ok_at from sources where id = 'broken'")
    assert "404" in broken["last_error"] and broken["last_ok_at"] is None

    # En andra körning med samma flöden ska inte skapa dubbletter
    stats2 = run(settings=SETTINGS, store=store, catalog=CATALOG, fetch=fake_fetch,
                 summarizer=summarizer, fetch_page=fetch_text, now=NOW, log=lambda _: None)
    assert (stats2.new_items, stats2.summarized, stats2.stories_created) == (0, 0, 0)
    assert rows(store, "select count(*) as n from runs where finished_at is not null")[0]["n"] == 2


def test_archive_survives_closing_and_reopening(tmp_path):
    path = tmp_path / "klubbhuset.db"
    first = Store(path)
    run(settings=SETTINGS, store=first, catalog=CATALOG, fetch=fake_fetch,
        summarizer=FakeSummarizer(), fetch_page=fetch_text, now=NOW, log=lambda _: None)
    first.close()
    again = Store(path)
    assert len(again.all_stories()) == 1 and again.last_run()["new_items"] == 4
    again.conn.close()


def test_without_ai_key_items_are_kept_for_later(store):
    stats = run(settings=SETTINGS, store=store, catalog=CATALOG, fetch=fake_fetch,
                summarizer=None, fetch_page=fetch_text, now=NOW, log=lambda _: None)
    assert stats.new_items == 4 and stats.summarized == 0
    assert rows(store, "select count(*) as n from items where status = 'new'")[0]["n"] == 3
    # Senare, när nyckeln finns, sammanfattas de
    stats2 = run(settings=SETTINGS, store=store, catalog=CATALOG, fetch=fake_fetch,
                 summarizer=FakeSummarizer(), fetch_page=fetch_text, now=NOW, log=lambda _: None)
    assert stats2.summarized == 2


def test_failed_article_is_retried_then_given_up(store):
    class Exploding(FakeSummarizer):
        def summarize_article(self, **kwargs):
            raise RuntimeError("API nere")

    for _ in range(4):
        run(settings=SETTINGS, store=store, catalog=[GOLFCOM], fetch=lambda due: [fake_fetch(due)[0]],
            summarizer=Exploding(), fetch_page=lambda url: None, now=NOW, log=lambda _: None)
    [item] = rows(store, "select status, attempts, pending_text, last_error from items")
    assert item["status"] == "failed" and item["attempts"] == 3
    assert item["pending_text"] is None and "API nere" in item["last_error"]


def test_export_builds_site_with_api_files(store, tmp_path):
    run(settings=SETTINGS, store=store, catalog=CATALOG, fetch=fake_fetch,
        summarizer=FakeSummarizer(), fetch_page=fetch_text, now=NOW, log=lambda _: None)
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>", encoding="utf-8")
    site = tmp_path / "site"

    counts = export_site(store, web, site, NOW)

    assert counts == {"stories": 1, "front": 1, "media": 1}
    assert (site / "index.html").exists()
    front = json.loads((site / "api" / "front.json").read_text(encoding="utf-8"))
    assert front["stories"][0]["title_sv"] == "Sammanvävd rubrik"
    assert front["media"][0]["kind"] == "video" and front["last_run"]["new_items"] == 4
    story_file = site / "api" / "stories" / f"{front['stories'][0]['id']}.json"
    detail = json.loads(story_file.read_text(encoding="utf-8"))
    assert {i["outlet"] for i in detail["items"]} == {"GOLF.com", "Svensk Golf"}
    assert detail["story"]["summary"] == "Sammanvävd text." and len(detail["story"]["angles"]) == 2
    assert json.loads((site / "api" / "sections" / "touren.json").read_text(encoding="utf-8"))[0]["id"] == detail["story"]["id"]
    health = json.loads((site / "api" / "health.json").read_text(encoding="utf-8"))
    assert {s["id"] for s in health["sources"]} == {"golfcom", "svenskgolf", "yt-rick", "broken"}
    # Hela artiklar ska aldrig hamna i det publicerade
    published = "".join(p.read_text(encoding="utf-8") for p in (site / "api").rglob("*.json"))
    assert "Ryder Cup spelas på Adare Manor. Ryder Cup" not in published


def test_thin_item_becomes_short_notice_without_summary(store):
    bing = Source(id="bing-x", name="Bing", kind="news_search", feed="https://www.bing.com/news/search?q=x")
    thin = FetchResult(bing, [FeedItem(
        url="https://www.msn.com/rahm", title="Jon Rahm leaving LIV Golf. When will he return to PGA Tour?",
        published=NOW - timedelta(hours=1), text="Jon Rahm is officially leaving LIV Golf, reports say.",
        outlet="Golfweek on MSN")])
    summarizer = FakeSummarizer()
    run(settings=SETTINGS, store=store, catalog=[bing], fetch=lambda due: [thin],
        summarizer=summarizer, fetch_page=lambda url: None, now=NOW, log=lambda _: None)
    assert summarizer.calls[0]["cap"] == 0
    [story] = store.all_stories()
    assert story["summary"] == "" and story["outlets"] == ["Golfweek on MSN"]


def test_meta_summaries_are_cleaned_when_archive_opens(tmp_path):
    path = tmp_path / "k.db"
    first = Store(path)
    first.conn.execute(
        "insert into stories (section, title_sv, ingress, summary, first_published_at, last_published_at, created_at, updated_at) "
        "values ('Touren', 'R', 'I', 'Underlaget är bara artikelns ingress.', 'x', 'x', 'x', 'x'), "
        "('Touren', 'R2', 'I2', 'Rahm lämnar LIV. Underlaget är tunt. Han siktar på PGA Tour.', 'x', 'x', 'x', 'x')")
    first.conn.commit()
    first.conn.close()
    again = Store(path)
    summaries = sorted(s["summary"] for s in again.all_stories())
    assert summaries == ["", "Rahm lämnar LIV. Han siktar på PGA Tour."]
    again.conn.close()

from datetime import datetime, timezone

from klubbhuset_motor.catalog import Source
from klubbhuset_motor.feeds import FetchResult, fetch_all, parse_feed

from fixtures import BING_NEWS, DUPLICATE_NAMESPACE, GOLFCOM_LIKE, PODCAST_RSS, YOUTUBE_ATOM


def src(kind="article", **kw):
    return Source(id=kw.pop("id", "test"), name=kw.pop("name", "Test"), kind=kind,
                  feed=kw.pop("feed", "https://example.com/feed"), **kw)


def test_picks_longest_content_and_strips_html_wrapper():
    [item] = parse_feed(src(outlet="GOLF.com"), GOLFCOM_LIKE)
    assert item.url == "https://golf.com/news/ryder-cup-2027-guide"
    assert "Adare Manor" in item.text and "Wrapper" not in item.text
    assert item.image_url == "https://golf.com/img/adare.jpg"
    assert item.outlet == "GOLF.com"
    assert item.published == datetime(2026, 10, 8, 14, 0, tzinfo=timezone.utc)


def test_tolerates_duplicate_namespace_declaration():
    items = parse_feed(src(), DUPLICATE_NAMESPACE)
    assert [i.title for i in items] == ["Review: A new putter"]


def test_youtube_entry_has_link_and_thumbnail():
    [item] = parse_feed(src("youtube", name="Rick Shiels Golf"), YOUTUBE_ATOM)
    assert item.url == "https://www.youtube.com/watch?v=abc123"
    assert item.image_url == "https://i2.ytimg.com/vi/abc123/hqdefault.jpg"
    assert item.outlet == "Rick Shiels Golf"


def test_podcast_without_link_uses_enclosure_and_duration():
    [item] = parse_feed(src("podcast", name="Klubbans fel"), PODCAST_RSS)
    assert item.url == "https://cdn.example.com/ep120.mp3"
    assert item.duration == "01:04:12"


def test_bing_item_is_unwrapped_and_credited_to_real_outlet():
    [item] = parse_feed(src("news_search", feed="https://www.bing.com/news/search?q=x"), BING_NEWS)
    assert item.url == "https://www.svt.se/sport/golf/aberg-klar"
    assert item.outlet == "SVT Sport"


def test_fetch_all_pauses_between_bing_feeds_only():
    sources = [
        src(id="a"), src(id="b"),
        src("news_search", id="bing1", feed="https://www.bing.com/news/search?q=1"),
        src("news_search", id="bing2", feed="https://www.bing.com/news/search?q=2"),
    ]

    class FakeResponse:
        content = GOLFCOM_LIKE

        def raise_for_status(self):
            return None

    class FakeClient:
        def get(self, url):
            return FakeResponse()

    sleeps = []
    results = fetch_all(sources, FakeClient(), workers=2, bing_delay=3.0, sleep=sleeps.append)
    assert sorted(r.source.id for r in results) == ["a", "b", "bing1", "bing2"]
    assert all(isinstance(r, FetchResult) and r.ok for r in results)
    assert sleeps == [3.0]


def test_broken_feed_is_reported_not_raised():
    class FailingClient:
        def get(self, url):
            raise RuntimeError("timeout")

    [result] = fetch_all([src()], FailingClient())
    assert not result.ok and "timeout" in result.error


def test_real_http_client_can_be_created_with_default_settings():
    from klubbhuset_motor.config import load_settings
    from klubbhuset_motor.feeds import make_client

    settings = load_settings()
    settings.user_agent.encode("ascii")  # HTTP-huvuden måste vara ASCII
    with make_client(settings.user_agent, settings.fetch_timeout) as client:
        assert client.headers["User-Agent"] == settings.user_agent

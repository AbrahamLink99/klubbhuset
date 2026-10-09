from collections import Counter
from datetime import datetime, timezone

from klubbhuset_motor.catalog import due_this_run, load_catalog, slugify
from klubbhuset_motor.config import REPO_ROOT


def test_real_source_list_loads_with_unique_ids():
    catalog = load_catalog(REPO_ROOT / "sources.yaml", REPO_ROOT / "players.yaml")
    ids = [s.id for s in catalog]
    assert len(ids) == len(set(ids))
    kinds = Counter(s.kind for s in catalog)
    assert kinds["article"] >= 20 and kinds["youtube"] >= 25 and kinds["podcast"] == 17
    assert sum(1 for s in catalog if s.player) == 25
    assert all(s.feed.startswith("https://") for s in catalog)


def test_player_feeds_are_spread_over_the_hours():
    catalog = load_catalog(REPO_ROOT / "sources.yaml", REPO_ROOT / "players.yaml")
    players = [s for s in catalog if s.player]
    per_hour = [
        sum(due_this_run(p, datetime(2026, 10, 9, hour, tzinfo=timezone.utc), 6) for p in players)
        for hour in range(6)
    ]
    assert sum(per_hour) == len(players)  # varje spelare exakt en gång per sex timmar
    assert max(per_hour) <= 10


def test_inactive_source_is_never_due():
    catalog = load_catalog(REPO_ROOT / "sources.yaml", REPO_ROOT / "players.yaml")
    pgatour_yt = next(s for s in catalog if s.id == "yt-pgatour")
    assert not due_this_run(pgatour_yt, datetime.now(timezone.utc), 6)


def test_slugify_handles_swedish_letters():
    assert slugify("Ludvig Åberg") == "ludvig-aberg"
    assert slugify("Tobias Edén") == "tobias-eden"

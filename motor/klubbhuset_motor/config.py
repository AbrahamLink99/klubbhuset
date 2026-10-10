"""Inställningar. Allt går att ändra med miljövariabler (till exempel i GitHub Actions)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None = None

    # AI
    model: str = "claude-haiku-5-5"

    # Sammanfattningens längd. Taket är en andel av originalets längd,
    # med ett golv för korta texter och ett absolut tak för långa.
    summary_max_share: float = 0.25
    summary_min_words: int = 60
    summary_max_words: int = 450
    story_summary_max_words: int = 600

    # Hur mycket en körning får göra
    max_articles_per_run: int = 40
    max_story_syntheses_per_run: int = 15
    time_budget_seconds: int = 13 * 60

    # Hämtning
    lookback_hours: int = 48
    story_window_hours: int = 72
    fetch_timeout: float = 20.0
    fetch_workers: int = 8
    bing_delay_seconds: float = 3.0
    player_feed_every_hours: int = 6
    min_words_for_feed_text: int = 250
    min_words_for_summary: int = 40
    # Måste vara ren ASCII – HTTP-huvuden tål inte å, ä och ö.
    user_agent: str = "Mozilla/5.0 (compatible; Klubbhuset/0.1; personal golf news reader)"

    # Filer
    sources_file: Path = REPO_ROOT / "sources.yaml"
    players_file: Path = REPO_ROOT / "players.yaml"
    db_path: Path = REPO_ROOT / "arkiv" / "klubbhuset.db"
    web_dir: Path = REPO_ROOT / "web"
    site_dir: Path = REPO_ROOT / "site"


def load_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        model=_env("KLUBBHUSET_MODEL", "claude-haiku-5-5"),
        summary_max_share=float(_env("SUMMARY_MAX_SHARE", "0.25")),
        summary_min_words=int(_env("SUMMARY_MIN_WORDS", "60")),
        summary_max_words=int(_env("SUMMARY_MAX_WORDS", "450")),
        story_summary_max_words=int(_env("STORY_SUMMARY_MAX_WORDS", "600")),
        max_articles_per_run=int(_env("MAX_ARTICLES_PER_RUN", "40")),
        time_budget_seconds=int(_env("TIME_BUDGET_SECONDS", str(13 * 60))),
        sources_file=Path(_env("SOURCES_FILE", str(REPO_ROOT / "sources.yaml"))),
        players_file=Path(_env("PLAYERS_FILE", str(REPO_ROOT / "players.yaml"))),
        db_path=Path(_env("KLUBBHUSET_DB", str(REPO_ROOT / "arkiv" / "klubbhuset.db"))),
        site_dir=Path(_env("KLUBBHUSET_SITE", str(REPO_ROOT / "site"))),
    )

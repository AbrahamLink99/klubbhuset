"""Bygger sidan: kopierar appen och skriver nyheterna som JSON-filer bredvid den.

    site/
      index.html, app.js, …        appen (från web/)
      api/front.json               förstasidan
      api/sections/<sektion>.json  de senaste stories per sektion
      api/stories/<id>.json        en story med källor och relaterade stories
      api/media.json               YouTube & Poddar
      api/search.json              sökregister för arkivet
      api/health.json              källornas hälsa
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from .store import Store, iso

SECTIONS = {
    "touren": "Touren",
    "utrustning": "Utrustning",
    "teknik": "Teknik",
    "spelare": "Spelare",
    "historia": "Historia",
}
LIST_FIELDS = (
    "id", "section", "title_sv", "ingress", "image_url", "outlets", "outlet_count", "tags",
    "last_published_at",
)
SEARCH_LIMIT = 5000


def _card(story: dict) -> dict:
    return {key: story[key] for key in LIST_FIELDS}


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _related(stories: list[dict]) -> dict[int, list[dict]]:
    """Upp till tre andra stories per story som delar ett ämne, nyast först."""
    by_tag: dict[str, list[dict]] = {}
    for story in stories:  # stories är sorterade nyast först
        for tag in story["tags"]:
            by_tag.setdefault(tag.lower(), []).append(story)
    related: dict[int, list[dict]] = {}
    for story in stories:
        picked: list[dict] = []
        for tag in story["tags"]:
            for other in by_tag.get(tag.lower(), []):
                if other["id"] != story["id"] and other not in picked:
                    picked.append(other)
                if len(picked) >= 3:
                    break
            if len(picked) >= 3:
                break
        related[story["id"]] = [_card(s) for s in picked]
    return related


def export_site(store: Store, web_dir: Path, site_dir: Path, now: datetime) -> dict:
    site_dir = Path(site_dir)
    if site_dir.exists():
        shutil.rmtree(site_dir)
    shutil.copytree(web_dir, site_dir)
    api = site_dir / "api"

    stories = store.all_stories()
    items = store.items_for_stories()
    media = store.media(60)
    last_run = store.last_run()
    recent_cutoff = iso(now - timedelta(hours=72))

    front = sorted(
        (s for s in stories if s["last_published_at"] >= recent_cutoff),
        key=lambda s: s["score"],
        reverse=True,
    )[:40]
    _write(api / "front.json", {
        "generated_at": iso(now),
        "stories": [_card(s) for s in front],
        "historia": [_card(s) for s in stories if s["section"] == "Historia"][:2],
        "media": media[:4],
        "last_run": last_run,
    })

    for slug, name in SECTIONS.items():
        _write(api / "sections" / f"{slug}.json",
               [_card(s) for s in stories if s["section"] == name][:40])

    _write(api / "media.json", media)

    related = _related(stories)
    for story in stories:
        _write(api / "stories" / f"{story['id']}.json", {
            "story": {
                **_card(story),
                "summary": story["summary"],
                "angles": story["angles"],
                "players": story["players"],
                "related": related.get(story["id"], []),
            },
            "items": items.get(story["id"], []),
        })

    _write(api / "search.json", [
        {**_card(s), "players": s["players"]} for s in stories[:SEARCH_LIMIT]
    ])

    _write(api / "health.json", {
        "generated_at": iso(now),
        "last_run": last_run,
        "sources": [
            {key: s[key] for key in ("id", "name", "kind", "last_checked_at", "last_ok_at",
                                      "last_new_item_at", "last_error")}
            for s in store.sources()
        ],
    })

    return {"stories": len(stories), "front": len(front), "media": len(media)}

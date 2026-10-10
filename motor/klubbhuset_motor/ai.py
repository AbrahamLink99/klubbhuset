"""AI-redaktionen: sammanfattar artiklar och väver ihop stories med Claude."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .textutil import enforce_word_cap

SECTIONS = ["Touren", "Utrustning", "Teknik", "Spelare", "Historia"]
MAX_INPUT_CHARS = 15_000


@dataclass
class ArticleResult:
    relevant: bool
    title_sv: str
    ingress: str
    summary: str
    section: str
    tags: list[str] = field(default_factory=list)
    players: list[str] = field(default_factory=list)
    same_story_id: int | None = None


@dataclass
class StoryResult:
    title_sv: str
    ingress: str
    summary: str
    angles: list[dict] = field(default_factory=list)


class Summarizer(Protocol):
    def summarize_article(
        self,
        *,
        outlet: str,
        original_title: str,
        published: datetime | None,
        text: str,
        is_full_text: bool,
        source_words: int,
        word_cap: int,
        candidates: list[dict],
        known_players: list[str],
    ) -> ArticleResult: ...

    def synthesize_story(self, *, items: list[dict], word_cap: int) -> StoryResult: ...


ARTICLE_SYSTEM = """Du är redaktör på Klubbhuset, en svensk golftidning med lugn och saklig ton, ungefär som New York Times. Du får en artikel från en annan publikation och skriver Klubbhusets text om den. Läsaren läser din text i appen och går sedan vidare till källan för hela artikeln.

Regler:
- Skriv på svenska, även när källan är på engelska. Behåll egennamn, tävlingsnamn och produktnamn som de stavas.
- title_sv: saklig och informativ rubrik, högst 90 tecken. Inga utropstecken, inga lockbetesfrågor, inga versaler för betoning. Säg vad som hänt eller vad texten handlar om.
- ingress: en till två meningar med det viktigaste.
- summary: återge fakta, sammanhang och slutsatser med egna ord, i två till fem korta stycken separerade med en tom rad. Använd så mycket av längdutrymmet som underlaget räcker till, men aldrig mer än det angivna taket. Hitta aldrig på något som inte står i underlaget. Kopiera inte källans formuleringar. Citera högst en mening åt gången och ange vem som sa det. Om underlaget bara är en kort ingress: skriv kort och bara det som står där.
- section: Touren (tävlingar, resultat, tourer, organisationer, regler för tävlingsspel), Utrustning (klubbor, bollar, tester, nyheter från tillverkare), Teknik (sving, närspel, puttning, banstrategi, träning, golfregler), Spelare (profiler, intervjuer, karriärer), Historia (historiska händelser, banarkitektur, långa reportage om golfens kultur).
- tags: två till sex korta ämnen som en läsare kan vilja följa, till exempel tävlingens namn, bana, märke eller modell.
- players: namn på professionella eller kända golfspelare som texten handlar om.
- relevant: false om texten inte är golfjournalistik – till exempel annonser, rabattkoder, köp och sälj, utlottningar, rena länklistor eller något som inte handlar om golf.
- same_story_id: om artikeln rapporterar om exakt samma händelse eller nyhet som en av de befintliga storyerna i listan, ange dess id. Samma ämne räcker inte, det måste vara samma händelse. Annars 0.

Tunt underlag:
- Om längdtaket för summary är 0 räcker underlaget inte till en sammanfattning. Lämna då summary tomt och skriv bara rubrik och en ingress på en mening som håller sig strikt till det som står.
- Hitta aldrig på namn, siffror, tävlingar eller händelser som inte står i underlaget. Är originalrubriken vag ska din rubrik vara lika försiktig.
- Skriv aldrig om själva underlaget, ingressen eller källan i texten (till exempel "underlaget är begränsat" eller "artikeln anger inte").
Språket:
- Skriv idiomatisk svenska som en erfaren svensk sportjournalist. Översätt aldrig ord för ord – formulera om hellre än att följa engelsk meningsbyggnad.
- Kontrollera genus och böjning: ett utslag, ett slag, ett hål, ett inspel, en runda, en putt, en birdie, en eagle, en bogey, cutten ("missade cutten"), en vinnare ("en DP World Tour-vinnares rutin").
- Använd etablerade svenska golftermer: utslag, inspel, närspel, chip, puttning, bunkerslag, slag under par, första/andra/tredje/sista rundan, ledningen, delad ledning, cutten, spelrätt, tourkort, starttider, bollar och klubbor.
- Behåll egennamn, tävlingsnamn och produktnamn som de stavas, men blanda inte in engelska ord i övrigt.
- Läs igenom rubrik och ingress en gång till och rätta grammatiken innan du svarar."""

ARTICLE_TOOL = {
    "name": "spara_artikel",
    "description": "Sparar Klubbhusets text om artikeln.",
    "input_schema": {
        "type": "object",
        "properties": {
            "relevant": {"type": "boolean"},
            "title_sv": {"type": "string"},
            "ingress": {"type": "string"},
            "summary": {"type": "string"},
            "section": {"type": "string", "enum": SECTIONS},
            "tags": {"type": "array", "items": {"type": "string"}},
            "players": {"type": "array", "items": {"type": "string"}},
            "same_story_id": {"type": "integer"},
        },
        "required": [
            "relevant",
            "title_sv",
            "ingress",
            "summary",
            "section",
            "tags",
            "players",
            "same_story_id",
        ],
    },
}

STORY_SYSTEM = """Du är redaktör på Klubbhuset, en svensk golftidning med lugn och saklig ton. Flera publikationer har skrivit om samma nyhet. Du får Klubbhusets sammanfattningar av varje artikel och väver ihop dem till en gemensam text.

Regler:
- Skriv på svenska.
- title_sv: saklig rubrik för hela nyheten, högst 90 tecken, utan utropstecken eller lockbete.
- ingress: en till två meningar med det viktigaste.
- summary: en sammanhängande text i två till sex stycken separerade med en tom rad. Väv ihop fakta från alla källor och säg tydligt när källorna skiljer sig åt. Använd bara det som står i underlaget. Håll dig under det angivna taket.
- angles: en kort mening per publikation om vad just den lyfter fram eller hur den skiljer sig från de andra.
- Skriv aldrig om själva underlaget eller sammanfattningarna, bara om nyheten.
Språket:
- Skriv idiomatisk svenska som en erfaren svensk sportjournalist. Översätt aldrig ord för ord – formulera om hellre än att följa engelsk meningsbyggnad.
- Kontrollera genus och böjning: ett utslag, ett slag, ett hål, ett inspel, en runda, en putt, en birdie, en eagle, en bogey, cutten ("missade cutten"), en vinnare ("en DP World Tour-vinnares rutin").
- Använd etablerade svenska golftermer: utslag, inspel, närspel, chip, puttning, bunkerslag, slag under par, första/andra/tredje/sista rundan, ledningen, delad ledning, cutten, spelrätt, tourkort, starttider, bollar och klubbor.
- Behåll egennamn, tävlingsnamn och produktnamn som de stavas, men blanda inte in engelska ord i övrigt.
- Läs igenom rubrik och ingress en gång till och rätta grammatiken innan du svarar."""

STORY_TOOL = {
    "name": "spara_story",
    "description": "Sparar den sammanvävda storyn.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title_sv": {"type": "string"},
            "ingress": {"type": "string"},
            "summary": {"type": "string"},
            "angles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "outlet": {"type": "string"},
                        "angle": {"type": "string"},
                    },
                    "required": ["outlet", "angle"],
                },
            },
        },
        "required": ["title_sv", "ingress", "summary", "angles"],
    },
}


_META_WORDS = ("underlag", "ingressen", "artikeln anger inte", "artikeln nämner inte", "texten anger inte")


def strip_meta(text: str) -> str:
    """Tar bort meningar där AI:n skriver om sitt underlag i stället för om nyheten."""
    paragraphs = []
    for paragraph in [p.strip() for p in str(text or "").split("\n\n") if p.strip()]:
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        kept = [x for x in sentences if not any(w in x.lower() for w in _META_WORDS)]
        if kept:
            paragraphs.append(" ".join(kept))
    return "\n\n".join(paragraphs).strip()


def _clean_list(values, limit: int) -> list[str]:
    seen: list[str] = []
    for value in values or []:
        value = str(value).strip()
        if value and value not in seen:
            seen.append(value)
    return seen[:limit]


def article_prompt(
    *,
    outlet: str,
    original_title: str,
    published: datetime | None,
    text: str,
    is_full_text: bool,
    source_words: int,
    word_cap: int,
    candidates: list[dict],
    known_players: list[str],
) -> str:
    material = "hela artikeln" if is_full_text else "bara flödets ingress"
    truncated = len(text) > MAX_INPUT_CHARS
    body = text[:MAX_INPUT_CHARS]
    story_lines = "\n".join(
        f"[{c['id']}] {c['title_sv']} ({c['section']})" for c in candidates
    ) or "(inga)"
    players = ", ".join(known_players) or "(inga)"
    return (
        f"Publikation: {outlet}\n"
        f"Originalrubrik: {original_title}\n"
        f"Publicerad: {published.isoformat() if published else 'okänt'}\n"
        f"Underlag: {material}, {source_words} ord"
        f"{' (avkortat här)' if truncated else ''}\n"
        f"Längdtak för summary: {word_cap} ord\n\n"
        f"Befintliga stories de senaste dygnen:\n{story_lines}\n\n"
        f"Svenska spelare som läsaren följer: {players}\n\n"
        f"<artikel>\n{body}\n</artikel>"
    )


class ClaudeSummarizer:
    def __init__(self, api_key: str, model: str, client=None):
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, max_retries=4)
        self.client = client
        self.model = model

    def _call_tool(self, system: str, prompt: str, tool: dict, max_tokens: int) -> dict:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                return dict(block.input)
        raise RuntimeError("Modellen svarade utan att använda verktyget")

    def summarize_article(self, *, word_cap: int, candidates: list[dict], **kwargs) -> ArticleResult:
        prompt = article_prompt(word_cap=word_cap, candidates=candidates, **kwargs)
        data = self._call_tool(ARTICLE_SYSTEM, prompt, ARTICLE_TOOL, max_tokens=2000)
        candidate_ids = {int(c["id"]) for c in candidates}
        story_id = int(data.get("same_story_id") or 0)
        section = data.get("section") if data.get("section") in SECTIONS else "Touren"
        return ArticleResult(
            relevant=bool(data.get("relevant", True)),
            title_sv=str(data.get("title_sv", "")).strip()[:140],
            ingress=strip_meta(str(data.get("ingress", ""))),
            summary="" if word_cap <= 0 else enforce_word_cap(strip_meta(str(data.get("summary", ""))), word_cap),
            section=section,
            tags=_clean_list(data.get("tags"), 8),
            players=_clean_list(data.get("players"), 10),
            same_story_id=story_id if story_id in candidate_ids else None,
        )

    def synthesize_story(self, *, items: list[dict], word_cap: int) -> StoryResult:
        parts = []
        for item in items:
            parts.append(
                f"<artikel publikation=\"{item['outlet']}\">\n"
                f"Originalrubrik: {item['original_title']}\n"
                f"Klubbhusets rubrik: {item['title_sv']}\n"
                f"Sammanfattning:\n{item['summary'] or '(kort notis, bara rubriken finns)'}\n</artikel>"
            )
        prompt = f"Längdtak för summary: {word_cap} ord\n\n" + "\n\n".join(parts)
        data = self._call_tool(STORY_SYSTEM, prompt, STORY_TOOL, max_tokens=2500)
        angles = [
            {"outlet": str(a.get("outlet", "")).strip(), "angle": str(a.get("angle", "")).strip()}
            for a in data.get("angles", []) or []
            if a.get("outlet") and a.get("angle")
        ]
        return StoryResult(
            title_sv=str(data.get("title_sv", "")).strip()[:140],
            ingress=strip_meta(str(data.get("ingress", ""))),
            summary=enforce_word_cap(strip_meta(str(data.get("summary", ""))), word_cap),
            angles=angles,
        )

from types import SimpleNamespace

from klubbhuset_motor.ai import ClaudeSummarizer, strip_meta
from klubbhuset_motor.textutil import word_count


class FakeMessages:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=self.payload)])


def summarizer_with(payload):
    messages = FakeMessages(payload)
    return ClaudeSummarizer("key", "claude-haiku-5-5", client=SimpleNamespace(messages=messages)), messages


ARGS = dict(outlet="Golf Monthly", original_title="Title", published=None, text="Text " * 400,
            is_full_text=True, source_words=400, known_players=["Ludvig Åberg"])


def test_unknown_story_id_and_section_are_cleaned_and_summary_capped():
    summarizer, messages = summarizer_with({
        "relevant": True, "title_sv": "Rubrik", "ingress": "Ingress.",
        "summary": "Mening med fem ord här. " * 60,  # 300 ord
        "section": "Okänd", "tags": ["Ryder Cup", "Ryder Cup", " "], "players": [], "same_story_id": 999,
    })
    result = summarizer.summarize_article(word_cap=100, candidates=[{"id": 7, "title_sv": "X", "section": "Touren"}], **ARGS)
    assert result.same_story_id is None
    assert result.section == "Touren"
    assert result.tags == ["Ryder Cup"]
    assert word_count(result.summary) <= 100

    request = messages.requests[0]
    assert request["model"] == "claude-haiku-5-5"
    assert request["tool_choice"] == {"type": "tool", "name": "spara_artikel"}
    prompt = request["messages"][0]["content"]
    assert "Längdtak för summary: 100 ord" in prompt and "[7] X (Touren)" in prompt


def test_known_story_id_is_kept():
    summarizer, _ = summarizer_with({
        "relevant": True, "title_sv": "R", "ingress": "I", "summary": "S.", "section": "Spelare",
        "tags": [], "players": ["Ludvig Åberg"], "same_story_id": 7,
    })
    result = summarizer.summarize_article(word_cap=100, candidates=[{"id": 7, "title_sv": "X", "section": "Touren"}], **ARGS)
    assert result.same_story_id == 7 and result.section == "Spelare"


def test_zero_cap_gives_empty_summary_and_meta_is_removed():
    summarizer, messages = summarizer_with({
        "relevant": True, "title_sv": "Rahm lämnar LIV Golf", "ingress": "Jon Rahm lämnar LIV Golf. Underlaget är kort.",
        "summary": "Något.", "section": "Touren", "tags": [], "players": [], "same_story_id": 0,
    })
    result = summarizer.summarize_article(word_cap=0, candidates=[], **ARGS)
    assert result.summary == "" and result.ingress == "Jon Rahm lämnar LIV Golf."
    assert "ett utslag" in messages.requests[0]["system"]  # språkreglerna följer med


def test_strip_meta_keeps_real_content():
    text = "Åberg slog 66.\n\nUnderlaget är begränsat. Han leder."
    assert strip_meta(text) == "Åberg slog 66.\n\nHan leder."

from klubbhuset_motor.textutil import (
    enforce_word_cap,
    html_to_text,
    make_excerpt,
    normalize_url,
    summary_word_cap,
    word_count,
)


def test_normalize_url_strips_tracking_and_trailing_slash():
    url = "https://WWW.Golf.com/news/article-name/?utm_source=rss&utm_medium=x&id=5#comments"
    assert normalize_url(url) == "https://www.golf.com/news/article-name?id=5"


def test_normalize_url_unwraps_bing_redirect():
    url = (
        "http://www.bing.com/news/apiclick.aspx?ref=FexRss&aid=&tid=abc"
        "&url=https%3a%2f%2fwww.svenskgolf.se%2ftournytt%2faberg-klar%2f%3futm_campaign%3dx&c=123"
    )
    assert normalize_url(url) == "https://www.svenskgolf.se/tournytt/aberg-klar"


def test_html_to_text_keeps_paragraphs_and_drops_head_and_scripts():
    html = (
        "<!DOCTYPE html><html><head><title>Sidtitel</title><style>p{}</style></head>"
        "<body><p>Första stycket.</p><script>var x=1;</script><p>Andra &amp; sista.</p></body></html>"
    )
    assert html_to_text(html) == "Första stycket.\n\nAndra & sista."


def test_summary_cap_is_a_quarter_of_long_texts():
    assert summary_word_cap(1200, 0.25, 60, 450) == 300


def test_summary_cap_has_absolute_ceiling():
    assert summary_word_cap(4000, 0.25, 60, 450) == 450


def test_summary_cap_floor_never_exceeds_sixty_percent_of_short_texts():
    assert summary_word_cap(40, 0.25, 60, 450) == 24
    assert summary_word_cap(200, 0.25, 60, 450) == 60


def test_enforce_word_cap_cuts_at_sentence_boundary():
    text = "Ett två tre fyra. Fem sex sju åtta. Nio tio elva tolv.\n\nTretton fjorton."
    capped = enforce_word_cap(text, cap=8, slack=1.0)
    assert capped == "Ett två tre fyra. Fem sex sju åtta."
    assert word_count(capped) == 8


def test_enforce_word_cap_leaves_text_within_slack_untouched():
    text = "Ett två tre fyra fem sex sju åtta nio."
    assert enforce_word_cap(text, cap=8) == text


def test_excerpt_cuts_at_word():
    excerpt = make_excerpt("ord " * 200, max_chars=30)
    assert excerpt.endswith("…") and len(excerpt) <= 31

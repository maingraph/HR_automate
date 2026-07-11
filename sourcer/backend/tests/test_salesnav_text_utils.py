"""Tests for Sales Navigator text utilities (sanitize_text, fuzzy_match)."""
from app.scrapers.salesnav_text_utils import fuzzy_match, sanitize_text


class TestSanitizeText:
    def test_none_returns_empty(self):
        assert sanitize_text(None) == ""

    def test_empty_returns_empty(self):
        assert sanitize_text("") == ""

    def test_collapses_whitespace(self):
        assert sanitize_text("foo   bar\t\nbaz") == "foo bar baz"

    def test_strips_edges(self):
        assert sanitize_text("  hello  ") == "hello"

    def test_removes_zero_width_space(self):
        assert sanitize_text("a​b") == "ab"

    def test_replaces_nbsp_with_space(self):
        # non-breaking space becomes regular space, then collapsed
        assert sanitize_text("a\xa0b") == "a b"


class TestFuzzyMatch:
    def test_exact_match(self):
        assert fuzzy_match("John Smith", "John Smith") is True

    def test_case_insensitive(self):
        assert fuzzy_match("JOHN SMITH", "john smith") is True

    def test_none_inputs_false(self):
        assert fuzzy_match(None, "x") is False
        assert fuzzy_match("x", None) is False

    def test_empty_inputs_false(self):
        assert fuzzy_match("", "x") is False

    def test_substring_contains_match(self):
        assert fuzzy_match("John", "John Smith") is True

    def test_word_overlap_above_threshold(self):
        # 2 shared of 3 union words ≈ 0.66 — below default 0.8 → false
        assert fuzzy_match("John Adam Smith", "John Adam Jones") is False

    def test_high_overlap_true(self):
        # share all words, different order via token set
        assert fuzzy_match("John Smith", "John Smith Jr") is True

    def test_unrelated_false(self):
        assert fuzzy_match("Alice Cooper", "Bob Dylan") is False

    def test_custom_threshold_loosens(self):
        # 0.5 overlap passes when threshold lowered
        assert fuzzy_match("John Adam", "John Eve", threshold=0.3) is True

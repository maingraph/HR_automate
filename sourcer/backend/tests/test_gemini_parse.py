"""Tests for Gemini response-parsing helpers.

Pure parsing logic only — no API calls. Covers code-fence stripping,
lenient JSON extraction, score clamping, and batch validation.
"""
import pytest

from app.scoring.gemini import (
    _json_from_text,
    _parse_batch_score_response,
    _parse_score_response,
    _strip_code_fences,
)


class TestStripCodeFences:
    def test_plain_json_untouched(self):
        assert _strip_code_fences('{"a":1}') == '{"a":1}'

    def test_strips_json_fence(self):
        assert _strip_code_fences('```json\n{"a":1}\n```') == '{"a":1}'

    def test_strips_bare_fence(self):
        assert _strip_code_fences('```\n{"a":1}\n```') == '{"a":1}'

    def test_strips_surrounding_whitespace(self):
        assert _strip_code_fences('   {"a":1}   ') == '{"a":1}'


class TestJsonFromText:
    def test_plain_object(self):
        assert _json_from_text('{"score": 80}') == {"score": 80}

    def test_fenced_object(self):
        assert _json_from_text('```json\n{"score": 80}\n```') == {"score": 80}

    def test_object_embedded_in_prose(self):
        # falls back to regex extraction of trailing {...}
        out = _json_from_text('Here is your result: {"score": 42}')
        assert out == {"score": 42}

    def test_invalid_raises(self):
        with pytest.raises(Exception):
            _json_from_text("not json at all")


class TestParseScoreResponse:
    def test_basic_fields(self):
        out = _parse_score_response(
            {"score": 75, "dimensions": {"x": 1}, "reasoning": "ok", "red_flags": ["a"]}
        )
        assert out == {
            "score": 75,
            "dimensions": {"x": 1},
            "reasoning": "ok",
            "red_flags": ["a"],
        }

    def test_overall_score_alias(self):
        assert _parse_score_response({"overall_score": 60})["score"] == 60

    def test_clamp_high(self):
        assert _parse_score_response({"score": 150})["score"] == 100

    def test_clamp_low(self):
        assert _parse_score_response({"score": -10})["score"] == 0

    def test_missing_defaults(self):
        out = _parse_score_response({})
        assert out["score"] == 0
        assert out["dimensions"] == {}
        assert out["reasoning"] == ""
        assert out["red_flags"] == []


class TestParseBatchScoreResponse:
    def test_valid_batch(self):
        out = _parse_batch_score_response(
            {"scores": [{"id": "0", "score": 50}, {"id": "1", "score": 90}]}, 2
        )
        assert len(out) == 2
        assert out[0]["score"] == 50
        assert out[1]["score"] == 90

    def test_clamps_each_score(self):
        out = _parse_batch_score_response({"scores": [{"id": "0", "score": 999}]}, 1)
        assert out[0]["score"] == 100

    def test_count_mismatch_raises(self):
        with pytest.raises(ValueError):
            _parse_batch_score_response({"scores": [{"id": "0", "score": 1}]}, 2)

    def test_scores_not_list_raises(self):
        with pytest.raises(ValueError):
            _parse_batch_score_response({"scores": "nope"}, 1)

    def test_id_mismatch_tolerated(self):
        # mismatched id logs a warning but does not raise
        out = _parse_batch_score_response({"scores": [{"id": "9", "score": 30}]}, 1)
        assert out[0]["score"] == 30

    def test_missing_fields_defaulted(self):
        out = _parse_batch_score_response({"scores": [{"id": "0"}]}, 1)
        assert out[0]["score"] == 0
        assert out[0]["dimensions"] == {}
        assert out[0]["red_flags"] == []

"""Tests for Gemini response-parsing helpers.

No live API calls. Covers response parsing and current google-genai adapter behavior.
"""
from types import SimpleNamespace

import pytest

import app.scoring.gemini as gemini
from app.scoring.gemini import (
    _generate_gemini,
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


class TestGoogleGenAIAdapter:
    def test_generate_uses_current_client_api(self, monkeypatch):
        calls = []

        class Models:
            def generate_content(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(text='{"ok": true}')

        client = SimpleNamespace(models=Models())
        monkeypatch.setattr(gemini, "_init_keys", lambda: client)
        monkeypatch.setattr(gemini, "_rate_limit", lambda: None)

        result = _generate_gemini(
            "Return JSON",
            "ping",
            temperature=0.2,
            model="gemini-test-model",
        )

        assert result == '{"ok": true}'
        assert calls[0]["model"] == "gemini-test-model"
        assert calls[0]["contents"] == "ping"
        assert calls[0]["config"].system_instruction == "Return JSON"
        assert calls[0]["config"].response_mime_type == "application/json"

    def test_generate_rejects_empty_response(self, monkeypatch):
        client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text=None)
            )
        )
        monkeypatch.setattr(gemini, "_init_keys", lambda: client)
        monkeypatch.setattr(gemini, "_rate_limit", lambda: None)

        with pytest.raises(RuntimeError, match="empty response"):
            _generate_gemini(None, "ping")

    def test_embeddings_use_values_from_new_response_shape(self, monkeypatch):
        calls = []

        class Models:
            def embed_content(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    embeddings=[SimpleNamespace(values=[0.25] * gemini.EMBED_DIM)]
                )

        monkeypatch.setattr(gemini, "_init_keys", lambda: SimpleNamespace(models=Models()))
        monkeypatch.setattr(gemini, "_rate_limit", lambda: None)

        vectors = gemini.embed_texts(["candidate profile"])

        assert len(vectors) == 1
        assert len(vectors[0]) == gemini.EMBED_DIM
        assert calls[0]["model"] == gemini.settings.gemini_embed_model
        assert calls[0]["config"].task_type == "RETRIEVAL_DOCUMENT"

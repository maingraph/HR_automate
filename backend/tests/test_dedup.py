"""Tests for cross-source dedup service.

Covers strict dedup by identity key (linkedin/telegram/email),
field-merge on collision, and fuzzy name-match pass.
"""
from app.services.dedup import _normalize_name, dedup


class TestNormalizeName:
    def test_none_becomes_empty(self):
        assert _normalize_name(None) == ""

    def test_lower_and_strip(self):
        assert _normalize_name("  John SMITH ") == "john smith"


class TestStrictDedup:
    def test_unique_candidates_preserved(self):
        out = dedup(
            [
                {"full_name": "A", "linkedin_url": "https://lnkd.in/a"},
                {"full_name": "B", "linkedin_url": "https://lnkd.in/b"},
            ]
        )
        assert len(out) == 2

    def test_same_linkedin_merged(self):
        out = dedup(
            [
                {"full_name": "John", "linkedin_url": "https://lnkd.in/x"},
                {"full_name": "John", "linkedin_url": "https://lnkd.in/x", "email": "j@x.com"},
            ]
        )
        assert len(out) == 1
        # merge fills empty fields from newcomer
        assert out[0]["email"] == "j@x.com"

    def test_same_email_merged(self):
        out = dedup(
            [
                {"full_name": "Jane", "email": "jane@x.com"},
                {"full_name": "Jane", "email": "jane@x.com", "headline": "Eng"},
            ]
        )
        assert len(out) == 1
        assert out[0]["headline"] == "Eng"

    def test_username_key_used_when_no_url_or_email(self):
        out = dedup(
            [
                {"full_name": "Bob", "username": "bobby"},
                {"full_name": "Bob", "username": "bobby", "headline": "Dev"},
            ]
        )
        assert len(out) == 1
        assert out[0]["headline"] == "Dev"

    def test_merge_records_source_provenance(self):
        out = dedup(
            [
                {"full_name": "C", "linkedin_url": "https://lnkd.in/c", "source": "apify"},
                {"full_name": "C", "linkedin_url": "https://lnkd.in/c", "source": "salesnav"},
            ]
        )
        assert len(out) == 1
        assert "salesnav" in out[0]["raw"]["merged_from"]

    def test_dedup_key_attached(self):
        out = dedup([{"full_name": "D", "email": "d@x.com"}])
        assert out[0]["dedup_key"] == "d@x.com"


class TestFuzzyNamePass:
    def test_near_identical_names_merged(self):
        # different identity keys so strict pass keeps both,
        # then fuzzy name pass collapses them
        out = dedup(
            [
                {"full_name": "Jonathan Smith", "email": "a@x.com"},
                {"full_name": "Jonathan Smith", "email": "b@x.com", "headline": "PM"},
            ]
        )
        assert len(out) == 1
        assert out[0]["headline"] == "PM"

    def test_distinct_names_not_merged(self):
        out = dedup(
            [
                {"full_name": "Alice Cooper", "email": "a@x.com"},
                {"full_name": "Bob Dylan", "email": "b@x.com"},
            ]
        )
        assert len(out) == 2

    def test_missing_name_not_merged(self):
        out = dedup(
            [
                {"email": "a@x.com"},
                {"email": "b@x.com"},
            ]
        )
        assert len(out) == 2

    def test_empty_input(self):
        assert dedup([]) == []

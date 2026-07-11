"""Tests for utils/text: contact extraction, OTW detection, resume heuristic, dedup_key."""
from app.utils.text import (
    detect_open_to_work,
    dedup_key,
    extract_contacts,
    looks_like_resume,
)


class TestExtractContacts:
    def test_empty_text(self):
        out = extract_contacts("")
        assert out == {
            "emails": [],
            "phones": [],
            "telegram": [],
            "linkedin": [],
            "urls": [],
        }

    def test_email_found(self):
        out = extract_contacts("reach me at jane.doe@example.com please")
        assert "jane.doe@example.com" in out["emails"]

    def test_telegram_handle(self):
        out = extract_contacts("ping @cooldev or t.me/anotherdev")
        assert "cooldev" in out["telegram"]
        assert "anotherdev" in out["telegram"]

    def test_linkedin_url(self):
        out = extract_contacts("profile: https://www.linkedin.com/in/john-smith")
        assert any("linkedin.com/in/john-smith" in u for u in out["linkedin"])

    def test_generic_url(self):
        out = extract_contacts("portfolio https://johnsmith.dev/work")
        assert "https://johnsmith.dev/work" in out["urls"]


class TestDetectOpenToWork:
    def test_empty(self):
        assert detect_open_to_work("") == (False, None)

    def test_english_open_to_work(self):
        found, _ = detect_open_to_work("I am open to work right now")
        assert found is True

    def test_hashtag(self):
        found, _ = detect_open_to_work("status: #opentowork")
        assert found is True

    def test_russian_signal(self):
        found, _ = detect_open_to_work("сейчас в поиске работы")
        assert found is True

    def test_no_signal(self):
        found, match = detect_open_to_work("happily employed senior engineer")
        assert found is False
        assert match is None


class TestLooksLikeResume:
    def test_empty_false(self):
        assert looks_like_resume("") is False

    def test_hardcoded_keyword(self):
        assert looks_like_resume("My resume and experience") is True

    def test_extra_keyword_match(self):
        assert looks_like_resume("expert in widgets", extra_keywords=["widgets"]) is True

    def test_contact_info_triggers(self):
        assert looks_like_resume("contact me: dev@example.com") is True

    def test_long_text_with_job_pattern(self):
        text = "I have many " + "x " * 60 + "years of developer experience building things"
        assert looks_like_resume(text) is True

    def test_short_irrelevant_false(self):
        assert looks_like_resume("hello world") is False


class TestDedupKey:
    def test_deterministic(self):
        a = dedup_key(email="J@X.com")
        b = dedup_key(email="j@x.com  ")
        assert a == b  # normalized lower + strip

    def test_linkedin_trailing_slash_normalized(self):
        a = dedup_key(linkedin_url="https://lnkd.in/abc/")
        b = dedup_key(linkedin_url="https://lnkd.in/abc")
        assert a == b

    def test_telegram_at_stripped(self):
        a = dedup_key(telegram_username="@bob")
        b = dedup_key(telegram_username="bob")
        assert a == b

    def test_different_inputs_differ(self):
        assert dedup_key(email="a@x.com") != dedup_key(email="b@x.com")

    def test_is_sha1_hex(self):
        k = dedup_key(full_name="John Smith")
        assert len(k) == 40
        int(k, 16)  # raises if not hex

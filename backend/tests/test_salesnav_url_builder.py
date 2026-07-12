"""Tests for Sales Navigator URL builder.

Pure logic — no network, no DB. Covers build/parse round-trip,
location + seniority URN resolution, years-of-experience bucketing,
keyword fallback, and structure validation.
"""
from app.scrapers.salesnav_url_builder import (
    LOCATION_URNS,
    SENIORITY_URNS,
    _resolve_location_urn,
    _resolve_seniority_urn,
    build_sales_nav_url,
    parse_sales_nav_url,
    validate_url_structure,
)


def _filters(url: str) -> dict:
    """Helper: parse URL back to {filter_type: values}."""
    return parse_sales_nav_url(url)


class TestBuildBasic:
    def test_returns_sales_search_url(self):
        url = build_sales_nav_url(title="Engineer")
        assert url.startswith("https://www.linkedin.com/sales/search/people?query=")

    def test_empty_inputs_produce_no_filters(self):
        url = build_sales_nav_url()
        assert _filters(url) == {}

    def test_title_adds_keywords_and_current_title(self):
        url = build_sales_nav_url(title="Product Manager")
        f = _filters(url)
        assert f["keywords"] == ["Product Manager"]
        assert f["currentTitle"] == ["Product Manager"]

    def test_company_filter(self):
        url = build_sales_nav_url(company="Stripe")
        assert _filters(url)["currentCompany"] == ["Stripe"]


class TestKeywordsComposition:
    def test_keywords_title_and_skills_combine(self):
        url = build_sales_nav_url(
            keywords="growth", title="PM", skills=["SQL", "Python", "Go"]
        )
        # keywords + title + top-3 skills joined by space
        assert _filters(url)["keywords"] == ["growth PM SQL Python Go"]

    def test_only_top_3_skills_used(self):
        url = build_sales_nav_url(skills=["a", "b", "c", "d", "e"])
        assert _filters(url)["keywords"] == ["a b c"]


class TestLocationResolution:
    def test_known_location_becomes_geo_urn(self):
        url = build_sales_nav_url(location="United States")
        assert _filters(url)["geoUrn"] == [LOCATION_URNS["united states"]]

    def test_unknown_location_falls_back_to_keywords(self):
        url = build_sales_nav_url(location="Atlantis")
        f = _filters(url)
        assert "geoUrn" not in f
        assert f["keywords"] == ["Atlantis"]

    def test_unknown_location_appends_to_existing_keywords(self):
        url = build_sales_nav_url(title="Engineer", location="Atlantis")
        # title set keywords already → location appended to it
        assert _filters(url)["keywords"] == ["Engineer Atlantis"]

    def test_resolve_location_direct(self):
        assert _resolve_location_urn("UK") == LOCATION_URNS["uk"]

    def test_resolve_location_case_insensitive(self):
        assert _resolve_location_urn("UNITED KINGDOM") == LOCATION_URNS["uk"]

    def test_resolve_location_fuzzy_contains(self):
        # "san francisco" is substring of mapped "san francisco bay area"
        assert _resolve_location_urn("san francisco") == LOCATION_URNS[
            "san francisco bay area"
        ]

    def test_resolve_location_unknown_returns_none(self):
        assert _resolve_location_urn("Narnia") is None


class TestSeniorityResolution:
    def test_known_seniority_becomes_urn(self):
        url = build_sales_nav_url(seniority="director")
        assert _filters(url)["seniority"] == [
            f"urn:li:fs_salesSeniorityLevel:{SENIORITY_URNS['director']}"
        ]

    def test_aliases_map_to_same_urn(self):
        assert _resolve_seniority_urn("vp") == _resolve_seniority_urn("director")
        assert _resolve_seniority_urn("senior") == _resolve_seniority_urn("mid-senior")

    def test_unknown_seniority_returns_none(self):
        assert _resolve_seniority_urn("intern-overlord") is None

    def test_unknown_seniority_adds_no_filter(self):
        url = build_sales_nav_url(title="X", seniority="intern-overlord")
        assert "seniority" not in _filters(url)


class TestYearsOfExperience:
    def test_bucket_entry(self):
        url = build_sales_nav_url(years_experience=(0, 1))
        assert _filters(url)["yearsOfExperience"] == ["1"]

    def test_bucket_2_to_5(self):
        url = build_sales_nav_url(years_experience=(2, 5))
        assert _filters(url)["yearsOfExperience"] == ["2"]

    def test_bucket_6_to_10(self):
        url = build_sales_nav_url(years_experience=(6, 10))
        assert _filters(url)["yearsOfExperience"] == ["3"]

    def test_bucket_11_plus(self):
        url = build_sales_nav_url(years_experience=(11, 20))
        assert _filters(url)["yearsOfExperience"] == ["4"]


class TestParseAndValidate:
    def test_round_trip_preserves_filters(self):
        url = build_sales_nav_url(
            title="Data Scientist",
            location="London",
            seniority="mid-senior",
            company="DeepMind",
        )
        f = _filters(url)
        assert f["currentTitle"] == ["Data Scientist"]
        assert f["geoUrn"] == [LOCATION_URNS["london"]]
        assert f["currentCompany"] == ["DeepMind"]

    def test_parse_bad_url_returns_empty(self):
        assert parse_sales_nav_url("https://example.com/not-a-search") == {}

    def test_validate_good_url(self):
        url = build_sales_nav_url(title="Engineer")
        assert validate_url_structure(url) is True

    def test_validate_wrong_host(self):
        assert validate_url_structure("https://evil.com/sales/search/people?query=x") is False

    def test_validate_empty_filters_is_false(self):
        # right host but no parseable filters
        assert validate_url_structure(build_sales_nav_url()) is False

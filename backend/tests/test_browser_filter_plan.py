from app.api.routes_workflow import _job_filter_plan


def test_media_buyer_uses_marketing_not_engineering() -> None:
    plan = _job_filter_plan({
        "title": "iGaming Media Buyer",
        "skills": ["iGaming", "Media Buying"],
    })

    assert plan["current_title"] == "iGaming Media Buyer"
    assert plan["function"] == "Marketing"
    assert plan["industries"] == ["Gambling Facilities and Casinos"]
    assert plan["geography"] == ""
    assert "Engineering" not in plan["keywords"]


def test_backend_role_keeps_engineering_mapping() -> None:
    plan = _job_filter_plan({"title": "Senior Python Backend Engineer", "geo": "Europe remote"})

    assert plan["current_title"] == "Back End Developer"
    assert plan["function"] == "Engineering"
    assert plan["geography"] == "Europe"

from app.scrapers.linkedin_public_profile import merge_public_profile


def test_public_profile_merge_maps_sections_without_overwriting_salesnav() -> None:
    merged = merge_public_profile(
        {
            "full_name": "Maya Hristova",
            "headline": "Media Buyer",
            "bio": "SalesNav bio",
            "skills": ["Meta Ads"],
            "positions": [],
            "educations": [],
            "languages": [],
        },
        {
            "linkedin_url": "https://www.linkedin.com/in/maya-example",
            "raw_text": "Public profile summary",
            "sections": {"experience": "full section text"},
            "section_items": {
                "experience": [
                    {"lines": ["Media Buyer", "PowerPlay", "Jan 2022 – Present · 2 yrs 6 mos", "Sofia, Bulgaria"]},
                    {"lines": ["Assistant", "Swedbank", "авг. 2018 г. – февр. 2019 г. · 7 мес.", "Рига, Латвия"]},
                    {"lines": ["О компании"]},
                ],
                "education": [{"lines": ["Sofia University", "Bachelor of Marketing", "2017 – 2021"]}],
                "skills": [{"lines": ["Meta Ads", "Campaign Management", "View all skills"]}, {"lines": ["О компании"]}],
                "languages": [{"lines": ["English", "Full professional proficiency", "Bulgarian", "Native or bilingual proficiency"]}],
            },
        },
    )

    assert merged["linkedin_url"] == "https://www.linkedin.com/in/maya-example"
    assert merged["bio"] == "SalesNav bio"
    assert len(merged["positions"]) == 2
    assert merged["positions"][0]["duration"] == "Jan 2022 – Present · 2 yrs 6 mos"
    assert merged["positions"][0]["location"] == "Sofia, Bulgaria"
    assert merged["positions"][1]["duration"] == "авг. 2018 г. – февр. 2019 г. · 7 мес."
    assert merged["years_experience"] > 2
    assert merged["educations"][0]["school"] == "Sofia University"
    assert merged["skills"] == ["Meta Ads", "Campaign Management"]
    assert merged["languages"] == [
        "English — Full professional proficiency",
        "Bulgarian — Native or bilingual proficiency",
    ]
    assert merged["raw"]["public_profile_sections"] == {"experience": "full section text"}


def test_grouped_employer_and_undated_role_are_preserved() -> None:
    grouped = merge_public_profile(
        {"positions": [], "skills": ["View all skills"]},
        {
            "sections": {
                "experience": "\n".join([
                    "Опыт работы", "LCO Casino", "Полный рабочий день · 24 г. 4 мес.", "Гибралтар", "Media Buyer",
                    "июнь 2011 г. – настоящее время · 15 лет 2 мес.", "Навыки: Media Buying и еще 3 навыка",
                    "Slot Operations Floor Supervisor", "Полный рабочий день",
                    "апр. 2006 г. – июнь 2011 г. · 5 лет 3 мес.",
                    "Recruitment Consultant", "Pentasia",
                    "сент. 2005 г. – март 2006 г. · 7 мес.", "О компании",
                ]),
                "education": "\n".join([
                    "Образование", "UNOPAR", "Bachelor of Marketing",
                    "С 2015 г. по 2018 г.", "О компании",
                ]),
                "skills": "\n".join([
                    "Навыки", "Пока нет контента для отображения",
                    "Здесь будут отображаться навыки, добавляемые участником Cory.", "О компании",
                ]),
            },
            "section_items": {},
        },
    )
    assert [(role["title"], role["company"]) for role in grouped["positions"]] == [
        ("Media Buyer", "LCO Casino"),
        ("Slot Operations Floor Supervisor", "LCO Casino"),
        ("Recruitment Consultant", "Pentasia"),
    ]
    assert grouped["skills"] == []
    assert grouped["educations"][0]["years"] == "С 2015 г. по 2018 г."

    undated = merge_public_profile(
        {"positions": []},
        {
            "sections": {
                "experience": "Опыт работы\nMedia Buyer\nFirst Casino · Полный рабочий день\nО компании",
            },
            "section_items": {},
        },
    )
    assert undated["positions"] == [{
        "title": "Media Buyer",
        "company": "First Casino",
        "duration": "",
        "raw": "Media Buyer | First Casino · Полный рабочий день",
    }]

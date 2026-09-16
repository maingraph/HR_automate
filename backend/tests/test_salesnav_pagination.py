import asyncio

from app.scrapers.linkedin_salesnav import SalesNavScraper
from app.scrapers.salesnav_card_extractor import CardExtractor
from app.scrapers.salesnav_sidebar_extractor import SidebarExtractor
from app.tasks.pipeline import _salesnav_seniority, _salesnav_years_experience


class _Link:
    def __init__(self, href: str) -> None:
        self.href = href

    async def get_attribute(self, _: str) -> str:
        return self.href


class _Card:
    def __init__(self, href: str) -> None:
        self.href = href

    async def query_selector(self, _: str) -> _Link:
        return _Link(self.href)

    async def text_content(self) -> str:
        return self.href


class _Page:
    def __init__(self) -> None:
        self.url = "https://www.linkedin.com/sales/search/people?page=1"
        self.polls = 0
        self.waits = 0

    async def query_selector_all(self, _: str) -> list[_Card]:
        self.polls += 1
        href = "/sales/lead/old" if self.polls == 1 else "/sales/lead/new"
        return [_Card(href)]

    async def wait_for_timeout(self, _: int) -> None:
        self.waits += 1


def test_next_page_waits_for_new_result_card_not_network_idle() -> None:
    scraper = SalesNavScraper(li_at_cookie="")
    page = _Page()

    asyncio.run(
        scraper._wait_for_next_results(
            page,
            previous_url=page.url,
            previous_signature="/sales/lead/old",
            timeout_ms=1_000,
        )
    )

    assert page.waits == 1


def test_card_experience_uses_rendered_company_title_and_duration() -> None:
    parsed = SalesNavScraper._parse_card_experience(
        "2022 – 2023\n(10 mos)\n·\nSmart IT-Center\n·\nAds specialist"
    )

    assert parsed == [{
        "title": "Ads specialist",
        "company": "Smart IT-Center",
        "duration": "2022 – 2023 (10 mos)",
        "raw": "2022 – 2023 (10 mos) Smart IT-Center Ads specialist",
    }]


class _VisibleCard:
    async def evaluate(self, _: str) -> dict[str, object]:
        return {
            "about": "Campaign specialist",
            "experience": "",
            "salesnav_url": "https://www.linkedin.com/sales/lead/abc",
            "linkedin_url": "",
            "links": [{"href": "https://www.linkedin.com/sales/lead/abc", "text": "Candidate"}],
        }


def test_card_details_preserve_all_rendered_links() -> None:
    details = asyncio.run(CardExtractor().extract_visible_details(_VisibleCard()))

    assert details["salesnav_url"] == "https://www.linkedin.com/sales/lead/abc"
    assert details["links"] == [{"href": "https://www.linkedin.com/sales/lead/abc", "text": "Candidate"}]


class _ActionsButton:
    def __init__(self) -> None:
        self.clicked = False

    async def click(self) -> None:
        self.clicked = True


class _Keyboard:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def press(self, key: str) -> None:
        self.keys.append(key)


class _SidebarActionsPage:
    def __init__(self) -> None:
        self.actions = _ActionsButton()
        self.keyboard = _Keyboard()
        self.waited_for = ""

    async def query_selector(self, selector: str):
        if selector == 'button[aria-label="Open actions overflow menu"]':
            return self.actions
        if selector == 'a[href*="linkedin.com/in/"]':
            return _Link("https://www.linkedin.com/in/example-person")
        return None

    async def wait_for_selector(self, selector: str, timeout: int) -> None:
        self.waited_for = selector


def test_sidebar_actions_menu_yields_public_profile_url() -> None:
    page = _SidebarActionsPage()

    url = asyncio.run(SidebarExtractor()._extract_public_url_from_actions_menu(page))

    assert url == "https://www.linkedin.com/in/example-person"
    assert page.actions.clicked is True
    assert page.waited_for == 'a[href*="linkedin.com/in/"]'
    assert page.keyboard.keys == ["Escape"]


def test_salesnav_derives_seniority_and_experience_years() -> None:
    positions = [{"title": "Media Buyer Team Lead", "duration": "2021 – Present"}]

    assert _salesnav_seniority("Media Buyer", positions) == "Manager"
    assert _salesnav_years_experience(positions) == 5


class _ViewportScrollPage:
    def __init__(self) -> None:
        self.viewport = None
        self.script = ""
        self.waited = 0

    async def set_viewport_size(self, viewport: dict[str, int]) -> None:
        self.viewport = viewport

    async def evaluate(self, script: str) -> None:
        self.script = script

    async def wait_for_timeout(self, milliseconds: int) -> None:
        self.waited = milliseconds


def test_salesnav_scrolls_virtualized_results_container() -> None:
    page = _ViewportScrollPage()

    asyncio.run(SalesNavScraper(li_at_cookie="")._scroll_to_load_all(page))

    assert page.viewport is None
    assert "#search-results-container" in page.script
    assert "container.scrollTop" in page.script

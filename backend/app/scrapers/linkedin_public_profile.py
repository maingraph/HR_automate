"""Conservative normalisation for authenticated LinkedIn public-profile pages."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


_DATE_RE = re.compile(
    r"(?:19|20)\d{2}[^\n]{0,40}[–—-][^\n]{0,60}(?:present|настоящее\s+время|(?:19|20)\d{2})",
    re.I,
)
_EDUCATION_DATE_RE = re.compile(
    r"(?:\b(?:19|20)\d{2}\b.*(?:[–—-]|\bпо\b).*\b(?:19|20)\d{2}\b)"
    r"|(?:\b(?:19|20)\d{2}\b\s*(?:г\.)?$)",
    re.I,
)
_DURATION_RE = re.compile(r"\b\d+\s*(?:yr|yrs|year|years|mo|mos|month|months)\b", re.I)
_PROFICIENCY_RE = re.compile(r"(?:elementary|limited|professional|native|bilingual|full professional)", re.I)
_RU_PROFICIENCY_RE = re.compile(
    r"(?:родн(?:ой|ая)|свободн|профессиональн|владение|элементарн|средн(?:ий|ее)|базов|начальн|ограниченн)",
    re.I,
)
_FOOTER_MARKERS = {
    "about", "о компании", "accessibility", "специальные возможности",
    "talent solutions", "решения для найма", "community guidelines", "правила сообщества",
    "careers", "карьера", "marketing solutions", "решения для маркетинга",
    "privacy & terms", "условия", "advertising", "размещение рекламы",
    "sales solutions", "решения для продаж", "mobile", "мобильная версия",
    "small business", "для малого бизнеса", "safety center", "центр безопасности",
}
_SKILL_SENTINELS = {
    "view all skills", "show all skills", "показать все навыки", "посмотреть все навыки",
}
_CONTAMINATED_LOCATION_RE = re.compile(
    r"(?:mutual connections?|you both know|viewed|months? in role|years? in (?:role|company)|recent post)",
    re.I,
)
_GROUP_DURATION_RE = re.compile(
    r"\b\d+\s*(?:yrs?|years?|mos?|months?|г\.?|лет|год|года|мес\.?|месяц(?:а|ев)?)",
    re.I,
)
_EMPLOYMENT_TYPE_RE = re.compile(
    r"^(?:full[- ]time|part[- ]time|contract|freelance|self[- ]employed|internship|apprenticeship|seasonal"
    r"|полный рабочий день|частичная занятость|контракт|фриланс|самозанятый|стажировка|ученичество|сезонная работа)$",
    re.I,
)
_TITLE_RE = re.compile(
    r"\b(?:buyer|manager|director|consultant|analyst|executive|specialist|owner|lead|head|officer"
    r"|developer|designer|coordinator|assistant|representative|supervisor|agent|dealer|planner"
    r"|associate|editor|engineer|producer|administrator|marketing|acquisition|affiliate|media"
    r"|support|sales|customer|recruitment|crm|csr"
    r"|менеджер|директор|руководитель|аналитик|специалист|консультант|баер|байер)\b",
    re.I,
)
_MONTHS = {
    "jan": 1, "january": 1, "янв": 1,
    "feb": 2, "february": 2, "фев": 2,
    "mar": 3, "march": 3, "март": 3, "мар": 3,
    "apr": 4, "april": 4, "апр": 4,
    "may": 5, "май": 5, "мая": 5,
    "jun": 6, "june": 6, "июн": 6,
    "jul": 7, "july": 7, "июл": 7,
    "aug": 8, "august": 8, "авг": 8,
    "sep": 9, "sept": 9, "september": 9, "сент": 9, "сен": 9,
    "oct": 10, "october": 10, "окт": 10,
    "nov": 11, "november": 11, "нояб": 11, "ноя": 11,
    "dec": 12, "december": 12, "дек": 12,
}


def _lines(value: Any) -> list[str]:
    return [" ".join(str(line).split()) for line in (value or []) if " ".join(str(line).split())]


def _items(profile: dict[str, Any], section: str) -> list[dict[str, Any]]:
    raw = (profile.get("section_items") or {}).get(section) or []
    items: list[dict[str, Any]] = []
    for item in raw:
        lines = _lines(item.get("lines")) if isinstance(item, dict) else []
        if not lines or lines[0].lower() in _FOOTER_MARKERS:
            continue
        items.append(item)
    return items


def _section_lines(profile: dict[str, Any], section: str) -> list[str]:
    lines = [line.strip() for line in str((profile.get("sections") or {}).get(section) or "").splitlines()]
    lines = [" ".join(line.split()) for line in lines if " ".join(line.split())]
    for index, line in enumerate(lines):
        if line.lower() in _FOOTER_MARKERS:
            lines = lines[:index]
            break
    return lines


def _looks_like_location(line: str) -> bool:
    lower = line.lower()
    return bool(
        len(line) <= 90
        and (
            "," in line
            or lower in {"remote", "удаленная работа", "удалённая работа"}
            or "работа в офисе" in lower
            or "гибридный формат" in lower
        )
        and "навык" not in lower
        and "skill" not in lower
    )


def _looks_like_title(line: str) -> bool:
    lower = line.lower().strip()
    return bool(
        len(line) <= 80
        and len(line.split()) <= 12
        and not lower.startswith(("-", "•", "·", "навыки:", "skills:", "«"))
        and " и еще " not in lower
        and _TITLE_RE.search(line)
    )


def _experience(profile: dict[str, Any]) -> list[dict[str, str]]:
    lines = _section_lines(profile, "experience")
    date_indexes = [index for index, line in enumerate(lines) if _DATE_RE.search(line)]
    fallback: list[dict[str, str]] = []
    current_company = ""
    previous_date = -1
    for offset, date_index in enumerate(date_indexes):
        if date_index < 2:
            continue
        next_date = date_indexes[offset + 1] if offset + 1 < len(date_indexes) else len(lines)
        before = lines[previous_date + 1:date_index]
        immediate = lines[date_index - 1]
        prior = lines[date_index - 2] if date_index >= 2 else ""
        group_index = next(
            (
                index for index in range(len(before) - 1, 0, -1)
                if _GROUP_DURATION_RE.search(before[index]) and not _DATE_RE.search(before[index])
            ),
            -1,
        )
        if group_index > 0:
            current_company = before[group_index - 1]
        if _EMPLOYMENT_TYPE_RE.match(immediate):
            title = prior
            company = current_company
        elif " · " in immediate and not _GROUP_DURATION_RE.search(immediate):
            title = prior
            company = re.split(r"\s+·\s+", immediate, maxsplit=1)[0]
            current_company = company
        elif group_index > 0:
            title = immediate
            company = current_company
        elif len(before) >= 2 and _looks_like_title(prior):
            title = prior
            company = immediate
            current_company = company
        elif current_company:
            title = immediate
            company = current_company
        else:
            title = prior
            company = immediate
            current_company = company
        location = (
            lines[date_index + 1]
            if date_index + 1 < next_date and _looks_like_location(lines[date_index + 1])
            else ""
        )
        description_start = date_index + (2 if location else 1)
        description_end = max(description_start, next_date - 2)
        description = " ".join(
            line for line in lines[description_start:description_end]
            if "навык" not in line.lower() and "skill" not in line.lower()
        )
        fallback.append({
            "title": title,
            "company": company,
            "duration": lines[date_index],
            "location": location,
            "description": description,
            "raw": " | ".join(lines[max(0, date_index - 2):description_end]),
        })
        previous_date = date_index
    if fallback:
        return fallback
    records: list[dict[str, str]] = []
    for item in _items(profile, "experience"):
        item_lines = _lines(item.get("lines"))
        if not item_lines:
            continue
        item_date_index = next((i for i, line in enumerate(item_lines) if _DATE_RE.search(line)), -1)
        record = {
            "title": item_lines[0],
            "company": item_lines[1] if len(item_lines) > 1 else "",
            "duration": item_lines[item_date_index] if item_date_index >= 0 else "",
            "raw": " | ".join(item_lines),
        }
        if item_date_index >= 0 and item_date_index + 1 < len(item_lines) and "," in item_lines[item_date_index + 1]:
            record["location"] = item_lines[item_date_index + 1]
        records.append(record)
    if records:
        return records
    # Some members intentionally omit all employment dates. Preserve the
    # visible title/company pair rather than returning an empty history.
    content = lines[1:] if lines and lines[0].lower() in {"experience", "опыт работы"} else lines
    if len(content) >= 2:
        return [{
            "title": content[0],
            "company": re.split(r"\s+·\s+", content[1], maxsplit=1)[0],
            "duration": "",
            "raw": " | ".join(content[:2]),
        }]
    return []


def _education(profile: dict[str, Any]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for item in _items(profile, "education"):
        lines = _lines(item.get("lines"))
        if not lines:
            continue
        date = next((line for line in lines if _DATE_RE.search(line) or _EDUCATION_DATE_RE.search(line)), "")
        records.append({
            "school": lines[0],
            "degree": lines[1] if len(lines) > 1 else "",
            "years": date,
            "raw": " | ".join(lines),
        })
    if any(record.get("years") for record in records):
        return records
    lines = _section_lines(profile, "education")
    for date_index, line in enumerate(lines):
        if date_index < 2 or not (_DATE_RE.search(line) or _EDUCATION_DATE_RE.search(line)):
            continue
        records.append({
            "school": lines[date_index - 2],
            "degree": lines[date_index - 1],
            "years": line,
            "raw": " | ".join(lines[date_index - 2:date_index + 1]),
        })
    if records:
        return records
    content = lines[1:] if lines and lines[0].lower() in {"education", "образование"} else lines
    if content and (
        content[0].lower() == "пока нет контента для отображения"
        or content[0].lower().startswith("здесь будут отображаться")
        or content[0].lower().startswith("nothing to see")
    ):
        return []
    if content:
        return [{
            "school": content[0],
            "degree": content[1] if len(content) > 1 else "",
            "years": "",
            "raw": " | ".join(content[:2]),
        }]
    return records


def _skills(profile: dict[str, Any]) -> list[str]:
    ignored = {
        "skills", "навыки", "show more", "show less", "показать еще", "свернуть",
        "все", "отраслевые знания", "инструменты и технологии", "коммуникабельность", "языки",
        "пока нет контента для отображения",
    } | _SKILL_SENTINELS
    values: list[str] = []
    for item in _items(profile, "skills"):
        for line in _lines(item.get("lines")):
            lower = line.lower()
            if lower in ignored or "endorsement" in lower or len(line) > 120:
                continue
            if line not in values:
                values.append(line)
    if len(values) > 2:
        return values
    for line in _section_lines(profile, "skills"):
        lower = line.lower()
        if (
            lower in ignored
            or "подтвержд" in lower
            or lower == "подтвердить"
            or lower.startswith("здесь будут отображаться навыки")
            or lower.startswith("показать все сведения")
            or lower.startswith("show all details")
            or "endorsement" in lower
            or " в компании " in lower
            or re.search(r"\bat\s+(?:company|self|[A-Z])", line)
            or len(line) > 120
        ):
            continue
        if line not in values:
            values.append(line)
    return values


def _languages(profile: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in _items(profile, "languages"):
        lines = _lines(item.get("lines"))
        for index, line in enumerate(lines):
            if line.lower() == "languages" or len(line) > 120:
                continue
            if _PROFICIENCY_RE.search(line) or _RU_PROFICIENCY_RE.search(line):
                continue
            proficiency = (
                lines[index + 1]
                if index + 1 < len(lines)
                and (_PROFICIENCY_RE.search(lines[index + 1]) or _RU_PROFICIENCY_RE.search(lines[index + 1]))
                else ""
            )
            value = f"{line} — {proficiency}" if proficiency else line
            if value not in values:
                values.append(value)
    if values:
        return values
    lines = _section_lines(profile, "languages")
    ignored = {
        "languages", "языки", "show all languages", "показать все языки",
        "пока нет контента для отображения",
    }
    for index, line in enumerate(lines):
        lower = line.lower()
        if lower in ignored or lower.startswith("здесь будут отображаться") or len(line) > 120:
            continue
        if _PROFICIENCY_RE.search(line) or _RU_PROFICIENCY_RE.search(line):
            continue
        proficiency = (
            lines[index + 1]
            if index + 1 < len(lines)
            and (_PROFICIENCY_RE.search(lines[index + 1]) or _RU_PROFICIENCY_RE.search(lines[index + 1]))
            else ""
        )
        value = f"{line} — {proficiency}" if proficiency else line
        if value not in values:
            values.append(value)
    return values


def _profile_location(profile: dict[str, Any]) -> str:
    headline = " ".join(str(profile.get("headline") or "").split())
    full_name = " ".join(str(profile.get("full_name") or "").split())
    lines = [
        " ".join(line.split())
        for line in str(profile.get("raw_text") or "").splitlines()
        if " ".join(line.split())
    ][:20]
    try:
        start = lines.index(full_name) + 1
    except ValueError:
        start = 1
    ignored = {"·", "contact info", "контактные сведения", "contact details"}
    header = [line for line in lines[start:start + 7] if line.lower() not in ignored and not line.startswith("·")]
    if len(header) >= 2:
        return header[1]
    explicit = " ".join(str(profile.get("location") or "").split())
    if explicit and explicit.casefold() not in {headline.casefold(), full_name.casefold()}:
        return explicit
    return ""


def _month_index(value: str, *, present_end: bool = False) -> int | None:
    clean = " ".join(value.lower().replace("г.", "").split())
    if re.search(r"\b(?:present|настоящее время|по настоящее время)\b", clean):
        now = datetime.now(timezone.utc)
        return now.year * 12 + now.month - 1
    year_match = re.search(r"\b((?:19|20)\d{2})\b", clean)
    if not year_match:
        return None
    year = int(year_match.group(1))
    month = 12 if present_end else 1
    prefix = clean[:year_match.start()].strip(" .")
    token = prefix.split()[-1].rstrip(".") if prefix else ""
    for name, number in _MONTHS.items():
        if token.startswith(name):
            month = number
            break
    return year * 12 + month - 1


def _years_experience(positions: list[dict[str, str]]) -> float | None:
    occupied: set[int] = set()
    for position in positions:
        title = str(position.get("title") or "")
        company = str(position.get("company") or "")
        if re.search(r"(?:career break|перерыв в карьере)", f"{title} {company}", re.I):
            continue
        duration = str(position.get("duration") or position.get("dates") or "")
        date_range = duration.split("·", 1)[0].strip()
        parts = re.split(r"\s+[–—-]\s+", date_range, maxsplit=1)
        if len(parts) != 2:
            continue
        start = _month_index(parts[0])
        end = _month_index(parts[1], present_end=True)
        if start is None or end is None or end < start or end - start > 1000:
            continue
        occupied.update(range(start, end + 1))
    return round(len(occupied) / 12, 1) if occupied else None


def _prefer_structured(base: Any, public: list[Any], *, duration: bool = False) -> list[Any]:
    existing = base if isinstance(base, list) else []
    if not public:
        return existing
    if not existing:
        return public
    if duration:
        existing_dates = sum(bool(item.get("duration")) for item in existing if isinstance(item, dict))
        public_dates = sum(bool(item.get("duration")) for item in public if isinstance(item, dict))
        if public_dates > existing_dates:
            return public
    return public if len(public) > len(existing) else existing


def _merge_strings(base: Any, public: list[str], *, drop_skill_sentinels: bool = False) -> list[str]:
    existing = base if isinstance(base, list) else []
    values: list[str] = []
    for value in [*existing, *public]:
        clean = " ".join(str(value).split())
        if not clean:
            continue
        if drop_skill_sentinels and clean.lower() in _SKILL_SENTINELS:
            continue
        if clean not in values:
            values.append(clean)
    return values


def merge_public_profile(base: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Merge public profile facts without overwriting richer SalesNav fields."""
    positions = _experience(profile)
    educations = _education(profile)
    skills = _skills(profile)
    languages = _languages(profile)
    sections = profile.get("sections") or {}
    public_bio = " ".join(str(profile.get("bio") or "").split())
    base_bio = " ".join(str(base.get("bio") or "").split())
    public_location = _profile_location(profile)
    base_location = " ".join(str(base.get("location") or "").split())
    merged_positions = _prefer_structured(base.get("positions"), positions, duration=True)
    calculated_experience = _years_experience(merged_positions)
    merged = {
        **base,
        "linkedin_url": profile.get("linkedin_url") or base.get("linkedin_url"),
        "full_name": base.get("full_name") or profile.get("full_name"),
        "headline": base.get("headline") or profile.get("headline"),
        "location": (
            public_location
            if public_location and (not base_location or _CONTAMINATED_LOCATION_RE.search(base_location))
            else base_location
        ),
        "bio": public_bio if len(public_bio) > len(base_bio) else base_bio,
        "positions": merged_positions,
        "educations": _prefer_structured(base.get("educations"), educations),
        "skills": skills or _merge_strings(base.get("skills"), [], drop_skill_sentinels=True),
        "languages": languages or _merge_strings(base.get("languages"), []),
        "years_experience": calculated_experience if calculated_experience is not None else base.get("years_experience"),
        "scan_depth": 2,
    }
    merged["raw"] = {
        **(base.get("raw") or {}),
        "public_profile_sections": sections,
        "public_profile_source": "authenticated_linkedin_profile",
    }
    return merged

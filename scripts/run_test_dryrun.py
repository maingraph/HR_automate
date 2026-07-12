"""High-quality dry-run end-to-end test — no Supabase persistence.

Run (from repo root):
    cd backend && .venv/bin/python ../scripts/run_test_dryrun.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.scoring.gemini import generate_plan
from app.scoring.pipeline import stage1_embed_filter, stage2_gemini_score
from app.scrapers.linkedin_apify import scrape_linkedin, scrape_sales_navigator
from app.scrapers.telegram import scrape_channels
from app.services.dedup import dedup
from app.utils.geo_filter import build_ukraine_exclude, is_geo_excluded

JOB = {
    "title": "Facebook Media Buyer",
    "description": (
        "Ищем FB Middle+/Senior Media Buyer, который активно льёт сейчас. "
        "Рассматриваем ребят из РБ и РФ. "
        "Что нужно делать: работа с FB воронками, оптимизация и удержание ROI, "
        "адаптация стратегий под Tier-1 / Tier-2 / Tier-3 GEO. "
        "Требования: 1+ год в закупке трафика именно Facebook; "
        "генерация идей по крео и составление ТЗ; "
        "актуальный залив за последние 3–5 месяцев в iGaming; "
        "опыт работы с CPA-моделью, управление бюджетами от 70к$. "
        "Нужны скрины из трекеров или кабинетов FB (CPA/Спенд, можно скрыть оффер). "
        "Команда: новая команда, вся выстроенная инфраструктура, свой биздев/тех саппорт/дизайнер, "
        "команда опытных баеров middle+/senior. Нет ограничений в бюджете. "
        "Также рассматриваем команды. "
        "Условия: удалённая работа 9:00–18:00 GMT+3, тестовый залив 1 неделя, "
        "испытательный срок 2 месяца, оплата $500 фикс + бонус 15–35% при ROI ≥ 50% + 2% на всю сумму. "
        "После ИС фикс убирается. Оффер + NDA. "
        "ГЕО: любое кроме Украины (включая украинцев по паспорту). "
        "ВАЖНО: нужен именно Middle+/Senior IC исполнитель, НЕ Head/CMO/Director. "
        "Поиск бесконечный — именно FB Media Buyer."
    ),
    "skills": [
        "Facebook Ads Manager", "Facebook", "Meta Ads", "campaign optimization",
        "ROAS", "pixel setup", "retargeting", "CPA model", "iGaming",
        "traffic arbitrage", "creatives briefing",
    ],
    "geo": "Remote / Belarus / Russia (no Ukraine)",
    "geo_exclude": build_ukraine_exclude(),  # hard-filter: reject any Ukraine geo signal
    "seniority": "Mid-Senior",
    "budget_min": 70000,
    "budget_max": 100000,
    "tg_channels": [
        "https://t.me/hr_breakfast_emergency",
        "https://t.me/igaming_offer",
    ],
}

# ── Hard-filter constants ────────────────────────────────────────────────────

_OVERQUALIFIED_TITLES = {
    "head", "chief", "cmo", "ceo", "cto", "vp", "vice president",
    "директор", "руководитель",
}
_NON_FB_TITLES = {
    "seo", "smm", "content", "google ads", "google media", "programmatic",
    "motion design", "graphic design", "video editor", "copywriter",
    "дизайнер", "контент", "монтаж", "видеограф",
}
_RECRUITER_SIGNALS = {
    "#vacancy", "#вакансия", "ищем кандидата", "we are hiring",
    "открыта вакансия", "требуется специалист", "приглашаем на роль",
}

# Score thresholds for output grouping
TIER1_MIN = 65   # TOP LEADS — shortlist immediately
TIER2_MIN = 40   # OTHER FINDS — worth a look


def _is_hard_disqualified(c: dict, job: dict | None = None) -> tuple[bool, str]:
    """Fast pre-filter before burning LLM quota."""
    title    = (c.get("headline") or "").lower()
    raw_text = (c.get("raw_text") or c.get("bio") or "").lower()
    source   = c.get("source", "")

    # ── Geo exclusion (generalizable to any vacancy) ──
    if job:
        geo_excl = job.get("geo_exclude") or []
        geo_hit, geo_reason = is_geo_excluded(c, geo_excl)
        if geo_hit:
            return True, geo_reason

    # ── Seniority / role filters ──
    if c.get("overqualified_signal"):
        return True, "overqualified: Head/CMO/Director title"
    if any(t in title for t in _OVERQUALIFIED_TITLES):
        return True, "overqualified: title contains Head/CMO/Director"
    if source == "telegram" and any(sig in raw_text for sig in _RECRUITER_SIGNALS):
        return True, "recruiter post: vacancy announcement, not a candidate"
    if source == "linkedin" and not c.get("facebook_signal"):
        return True, "no Facebook/Meta Ads signal in profile"
    if any(t in title for t in _NON_FB_TITLES):
        return True, "non-FB role: design/content/SEO/Google"

    return False, ""


# ── Output helpers ────────────────────────────────────────────────────────────

def _print_candidate(c: dict, idx: int) -> None:
    name      = (c.get("full_name") or c.get("username") or "?")[:40]
    score     = c.get("gemini_score")
    score_str = f"{score}" if score is not None else "?"
    otw       = "🟢 OTW" if c.get("open_to_work") else ""
    ig        = "🎰 iGaming" if c.get("igaming_signal") else ""
    fb        = "📘 FB" if c.get("facebook_signal") else ""
    tags      = "  ".join(t for t in [otw, ig, fb] if t)
    headline  = (c.get("headline") or "")[:60]
    location  = (c.get("location") or "")[:30]

    print(f"  {idx:>2}. [{score_str:>3}]  {name}")
    if headline:
        print(f"       {headline}  |  {location}")
    if tags:
        print(f"       {tags}")
    if c.get("linkedin_url"):
        print(f"       🔗 {c['linkedin_url']}")
    if c.get("telegram_url"):
        print(f"       📱 {c['telegram_url']}")
    if c.get("gemini_reasoning"):
        print(f"       ↳ {c['gemini_reasoning'][:150]}")
    if c.get("red_flags"):
        print(f"       ⚑ {', '.join(c['red_flags'])[:100]}")
    print()


def _print_group(title: str, border: str, candidates: list[dict]) -> None:
    width = 72
    print(f"\n{'━' * width}")
    print(f"  {border}  {title}  ({len(candidates)} candidates)")
    print(f"{'━' * width}\n")
    if not candidates:
        print("  (none)\n")
        return
    for i, c in enumerate(candidates, 1):
        _print_candidate(c, i)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n=== [1/5] Plan generation ===")
    plan = generate_plan(JOB)
    JOB["linkedin_boolean"] = plan.get("linkedin_boolean", "")
    JOB["linkedin_queries"] = plan.get("linkedin_queries", [JOB["linkedin_boolean"]])
    JOB["tg_keywords"]      = plan["tg_keywords"]
    JOB["rubric"]           = plan["rubric"]
    print("LI queries:")
    for i, q in enumerate(JOB["linkedin_queries"], 1):
        print(f"  [{i}] {q}")
    print("Hard filters:", plan.get("hard_filters", []))
    print("Rubric weights:", {k: v.get("weight") for k, v in plan["rubric"].items()})
    print("TG keywords (first 20):", ", ".join(plan["tg_keywords"][:20]))

    print("\n=== [2/5] LinkedIn scrape ===")
    # Primary: Sales Navigator via PhantomBuster (100 results/query, full profiles)
    li = scrape_sales_navigator(queries=JOB["linkedin_queries"], max_results=100)
    if li:
        print(f"sales navigator (phantombuster): {len(li)} unique profiles")
    else:
        # Fallback: regular LinkedIn search via Apify (Short mode, ~25/query)
        print("PhantomBuster not ready — falling back to Apify Short mode")
        li = scrape_linkedin(
            boolean_query=JOB["linkedin_boolean"],
            queries=JOB["linkedin_queries"],
            geo=None,
            max_results=25,
            profile_mode="Short",
        )
        print(f"linkedin (apify fallback): {len(li)} unique profiles")

    print("\n=== [3/5] Telegram scrape ===")
    try:
        tg = scrape_channels(
            channels=JOB["tg_channels"],
            keywords=plan["tg_keywords"],
            days_back=90,
            per_channel_limit=1000,
        )
    except Exception as e:
        print("telegram scrape failed:", e)
        tg = []
    print(f"telegram: {len(tg)} posts")

    candidates = li + tg
    print(f"total raw: {len(candidates)}")

    print("\n=== [4/5] Dedup + hard filter + similarity filter ===")
    deduped = dedup(candidates)
    print(f"after dedup: {len(deduped)}")

    filtered, disqualified = [], []
    for c in deduped:
        bad, reason = _is_hard_disqualified(c, job=JOB)
        if bad:
            c["red_flags"] = [reason]
            disqualified.append(c)
        else:
            filtered.append(c)

    reasons = ", ".join(set(c["red_flags"][0] for c in disqualified)) if disqualified else "none"
    print(f"hard disqualified: {len(disqualified)}  ({reasons[:100]})")
    print(f"remaining for scoring: {len(filtered)}")

    if not filtered:
        print("no candidates after filter — exiting")
        return

    survivors = stage1_embed_filter(JOB, filtered, drop_bottom_pct=0.3)
    print(f"kept after similarity filter: {len(survivors)}")

    print("\n=== [5/5] Scoring ===")
    scored = stage2_gemini_score(JOB, JOB["rubric"], survivors)

    for c in disqualified:
        c.setdefault("gemini_score", 0)
    all_results = scored + disqualified

    # ── Tiered output ─────────────────────────────────────────────────────────
    top_leads    = [c for c in scored if (c.get("gemini_score") or 0) >= TIER1_MIN]
    other_finds  = [c for c in scored if TIER2_MIN <= (c.get("gemini_score") or 0) < TIER1_MIN]
    low_score    = [c for c in scored if (c.get("gemini_score") or 0) < TIER2_MIN]

    _print_group("★  TOP LEADS  —  shortlist these now", "🔥", top_leads)
    _print_group("OTHER FINDS  —  worth reviewing", "👀", other_finds)

    # Disqualified: brief one-liner list, no clutter
    if low_score or disqualified:
        print(f"{'─' * 72}")
        print(f"  LOW SCORE / DISQUALIFIED  ({len(low_score) + len(disqualified)} total — not recommended)\n")
        for c in low_score + disqualified:
            name  = (c.get("full_name") or c.get("username") or "?")[:35]
            score = c.get("gemini_score") or 0
            flag  = (c.get("red_flags") or [""])[0][:60]
            print(f"    [{score:>3}]  {name:<36}  {flag}")
        print()

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = {
        "linkedin_raw":       len(li),
        "telegram_raw":       len(tg),
        "deduped":            len(deduped),
        "hard_disqualified":  len(disqualified),
        "stage1_kept":        len(survivors),
        "stage2_scored":      len(scored),
        "top_leads":          len(top_leads),
        "other_finds":        len(other_finds),
        "top_score":          scored[0].get("gemini_score") if scored else None,
        "open_to_work":       sum(1 for c in all_results if c.get("open_to_work")),
        "igaming_signal":     sum(1 for c in all_results if c.get("igaming_signal")),
    }

    print(f"{'━' * 72}")
    print("  SUMMARY")
    print(f"{'━' * 72}")
    print(json.dumps(summary, indent=2))

    # ── JSON export ───────────────────────────────────────────────────────────
    def _serialisable(c: dict) -> dict:
        return {k: v for k, v in c.items() if k != "embedding" and _json_safe(v)}

    output = {
        "job":         JOB,
        "summary":     summary,
        "top_leads":   [_serialisable(c) for c in top_leads],
        "other_finds": [_serialisable(c) for c in other_finds],
        "low_score":   [_serialisable(c) for c in low_score],
        "disqualified":[_serialisable(c) for c in disqualified],
    }
    out_path = Path(__file__).parent / "results.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n✓  Results saved → {out_path}")
    print(f"   Top leads: {len(top_leads)}  |  Other finds: {len(other_finds)}")

    # ── Frontend option ───────────────────────────────────────────────────────
    print(f"""
{'━' * 72}
  TO VIEW IN THE FRONTEND (with Supabase persistence):
{'━' * 72}
  Open 4 terminal tabs from the sourcer/ root:

  Tab 1 — Redis (if not running as a service):
    redis-server

  Tab 2 — Celery worker:
    cd backend && .venv/bin/celery -A app.core.celery_app worker --loglevel=info

  Tab 3 — FastAPI backend:
    cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

  Tab 4 — Next.js frontend:
    cd frontend && npm run dev

  Then open http://localhost:3000
  The vacancy form is pre-filled — just hit "Create & run sourcing".
  Results auto-refresh every 4 s.
{'━' * 72}
""")


def _json_safe(v) -> bool:
    try:
        json.dumps(v)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()

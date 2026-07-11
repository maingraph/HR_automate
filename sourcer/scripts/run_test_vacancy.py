"""End-to-end smoke test with the Facebook Media Buyer vacancy.

Usage (from repo root):
    cd backend && python ../scripts/run_test_vacancy.py

Requires:
    - .env filled in
    - Supabase schema applied
    - Redis running (for Celery, though this script runs the pipeline inline)
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.db import get_supabase  # noqa: E402
from app.schemas.job import JobCreate  # noqa: E402
from app.services.jobs import create_job_with_plan, list_candidates  # noqa: E402
from app.tasks.pipeline import run_pipeline  # noqa: E402


VACANCY = JobCreate(
    title="Facebook Media Buyer",
    description=(
        "Ищем FB Middle+/Senior Media Buyer, который активно льёт сейчас. "
        "Работа с FB воронками, оптимизация и удержание ROI, "
        "адаптация стратегий под Tier-1 / Tier-2 / Tier-3 GEO. "
        "Требования: 1+ год закупки трафика (Facebook / TikTok / UAC / In-App); "
        "генерация идей по крео и ТЗ; актуальный залив за последние 3–5 месяцев в iGaming; "
        "опыт работы с высокими спендами от 70к$."
    ),
    skills=[
        "Facebook Ads Manager",
        "campaign optimization",
        "ROAS",
        "pixel setup",
        "retargeting",
        "iGaming",
        "traffic arbitrage",
    ],
    geo="Remote / CIS",
    seniority="Mid-Senior",
    budget_min=10000,
    budget_max=100000,
    tg_channels=[
        "https://t.me/hr_breakfast_emergency",
        "https://t.me/igaming_offer",
    ],
)


async def main() -> None:
    print("→ creating job with Gemini plan…")
    job = await create_job_with_plan(VACANCY)
    job_id = job["id"]
    print(f"  job id: {job_id}")
    print(f"  linkedin_boolean: {job.get('linkedin_boolean')}")
    print(f"  tg_keywords: {job.get('tg_keywords')}")
    print(f"  rubric: {json.dumps(job.get('rubric'), indent=2, ensure_ascii=False)}")

    print("→ running pipeline inline…")
    result = run_pipeline.apply(args=(job_id,)).get()
    print(f"  stats: {result.get('stats')}")

    print("→ fetching top candidates…")
    cands = await list_candidates(job_id, min_score=0, limit=50)
    for c in cands[:20]:
        print(
            f"  [{c.get('gemini_score')}] {c.get('full_name') or c.get('username')} "
            f"({c.get('source')}) — {c.get('headline') or ''}"
        )
        if c.get("linkedin_url"):
            print(f"     LI: {c['linkedin_url']}")
        if c.get("telegram_url"):
            print(f"     TG: {c['telegram_url']}")
        if c.get("gemini_reasoning"):
            print(f"     ↳ {c['gemini_reasoning']}")
    print(f"\ntotal candidates stored: {len(cands)}")


if __name__ == "__main__":
    asyncio.run(main())

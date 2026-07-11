from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CandidateBase(BaseModel):
    source: str
    source_id: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    raw_text: Optional[str] = None
    location: Optional[str] = None
    geo_normalized: Optional[str] = None
    seniority: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    linkedin_url: Optional[str] = None
    telegram_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    other_links: list[dict[str, Any]] = Field(default_factory=list)
    open_to_work: bool = False
    otw_signal: Optional[str] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CandidateOut(CandidateBase):
    id: str
    job_id: str
    gemini_score: Optional[int] = None
    gemini_reasoning: Optional[str] = None
    gemini_dimensions: Optional[dict[str, Any]] = None
    red_flags: list[str] = Field(default_factory=list)
    embed_similarity: Optional[float] = None
    status: str = "new"
    scan_depth: int = 1
    educations: list[dict[str, Any]] = Field(default_factory=list)
    positions: list[dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None

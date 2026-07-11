from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str
    description: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    geo: Optional[str] = None
    # Geo exclusions: keywords/locations to hard-disqualify (e.g. ["ukraine", "ukrainian", "Киев"])
    geo_exclude: list[str] = Field(default_factory=list)
    seniority: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    tg_channels: list[str] = Field(default_factory=list)
    # Which sources to scrape: linkedin | telegram | apollo | xlsx
    sources: list[str] = Field(default_factory=lambda: ["linkedin", "telegram"])


class JobOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    geo: Optional[str] = None
    geo_exclude: list[str] = Field(default_factory=list)
    seniority: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    tg_channels: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=lambda: ["linkedin", "telegram"])
    status: str
    linkedin_boolean: Optional[str] = None
    tg_keywords: list[str] = Field(default_factory=list)
    rubric: Optional[dict[str, Any]] = None
    stats: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JobRunResponse(BaseModel):
    job_id: str
    task_id: str
    status: str

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


StageType = Literal[
    "salesnav_extract",
    "telegram_extract",
    "apollo_extract",
    "file_import",
    "merge_dedup",
    "profile_enrich",
    "rules_filter",
    "similarity_analyze",
    "ai_grade",
]

DatasetState = Literal["draft", "sealed", "partial", "failed"]


class StageRunCreate(BaseModel):
    stage_type: StageType
    input_dataset_ids: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    start: bool = True


class StageRunOut(BaseModel):
    id: str
    job_id: str
    stage_type: StageType
    status: str
    input_dataset_ids: list[str] = Field(default_factory=list)
    output_dataset_id: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    attempt: int = 1
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class DatasetOut(BaseModel):
    id: str
    job_id: str
    name: str
    kind: str
    schema_version: int = 1
    capabilities: list[str] = Field(default_factory=list)
    parent_ids: list[str] = Field(default_factory=list)
    state: DatasetState
    row_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    sealed_at: Optional[str] = None


class CandidateRecordPatch(BaseModel):
    payload: Optional[dict[str, Any]] = None
    tags: Optional[list[str]] = None
    included: Optional[bool] = None


class DatasetImportOptions(BaseModel):
    job_id: str
    name: Optional[str] = None
    kind: str = "imported"
    parent_ids: list[str] = Field(default_factory=list)


class BrowserSessionCreate(BaseModel):
    job_id: str


class BrowserOpenSearch(BaseModel):
    url: Optional[str] = None

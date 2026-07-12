"""Versioned candidate datasets and portable interchange formats."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import pandas as pd

from app.core.db import get_supabase
from app.utils.text import dedup_key


SCHEMA_VERSION = 1
CANONICAL_COLUMNS = [
    "full_name", "first_name", "last_name", "headline", "bio", "location",
    "seniority", "years_experience", "skills", "languages", "linkedin_url",
    "telegram_url", "email", "phone", "source", "source_id", "open_to_work",
    "positions", "educations", "gemini_score", "gemini_reasoning",
    "gemini_dimensions", "embed_similarity", "red_flags", "raw_text", "raw",
]
NESTED_COLUMNS = {
    "skills", "languages", "positions", "educations", "gemini_dimensions",
    "red_flags", "raw",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def candidate_key(payload: dict[str, Any]) -> str:
    key = dedup_key(
        linkedin_url=payload.get("linkedin_url"),
        telegram_username=payload.get("username") or payload.get("telegram_url"),
        email=payload.get("email"),
        full_name=payload.get("full_name"),
    )
    if key:
        return key
    stable = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(stable.encode()).hexdigest()


def get_dataset(dataset_id: str, org_id: str) -> Optional[dict[str, Any]]:
    result = (
        get_supabase().table("candidate_datasets").select("*")
        .eq("id", dataset_id).eq("org_id", org_id).maybe_single().execute()
    )
    return result.data


def list_datasets(job_id: str, org_id: str) -> list[dict[str, Any]]:
    result = (
        get_supabase().table("candidate_datasets").select("*")
        .eq("job_id", job_id).eq("org_id", org_id)
        .order("created_at", desc=True).execute()
    )
    return result.data or []


def create_dataset(
    *, org_id: str, job_id: str, name: str, kind: str,
    capabilities: Optional[list[str]] = None,
    parent_ids: Optional[list[str]] = None,
    state: str = "draft",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    row = {
        "org_id": org_id,
        "job_id": job_id,
        "name": name,
        "kind": kind,
        "schema_version": SCHEMA_VERSION,
        "capabilities": capabilities or ["normalized"],
        "parent_ids": parent_ids or [],
        "state": state,
        "metadata": metadata or {},
    }
    result = get_supabase().table("candidate_datasets").insert(row).execute()
    if not result.data:
        raise RuntimeError("Failed to create dataset")
    return result.data[0]


def _update_row_count(dataset_id: str, org_id: str) -> int:
    sb = get_supabase()
    result = (
        sb.table("candidate_records").select("id", count="exact")
        .eq("dataset_id", dataset_id).eq("org_id", org_id).execute()
    )
    count = result.count if result.count is not None else len(result.data or [])
    sb.table("candidate_datasets").update({"row_count": count}).eq(
        "id", dataset_id
    ).eq("org_id", org_id).execute()
    return count


def append_records(
    dataset_id: str,
    org_id: str,
    payloads: Iterable[dict[str, Any]],
    *,
    start_position: int = 0,
) -> int:
    dataset = get_dataset(dataset_id, org_id)
    if not dataset or dataset["state"] not in ("draft", "partial"):
        raise ValueError("Dataset is not editable")
    rows = []
    for offset, payload in enumerate(payloads):
        source_payload = payload.get("raw") if isinstance(payload.get("raw"), dict) else {}
        rows.append({
            "org_id": org_id,
            "dataset_id": dataset_id,
            "candidate_key": candidate_key(payload),
            "payload": payload,
            "source_payload": source_payload,
            "included": bool(payload.get("included", True)),
            "position": start_position + offset,
        })
    sb = get_supabase()
    for index in range(0, len(rows), 250):
        sb.table("candidate_records").upsert(
            rows[index:index + 250], on_conflict="dataset_id,candidate_key"
        ).execute()
    _update_row_count(dataset_id, org_id)
    return len(rows)


def list_records(
    dataset_id: str,
    org_id: str,
    *,
    offset: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    included: Optional[bool] = None,
) -> dict[str, Any]:
    if not get_dataset(dataset_id, org_id):
        raise LookupError("Dataset not found")
    query = (
        get_supabase().table("candidate_records").select("*", count="exact")
        .eq("dataset_id", dataset_id).eq("org_id", org_id)
    )
    if included is not None:
        query = query.eq("included", included)
    # PostgREST JSON search differs across versions; filter bounded page in Python.
    fetch_limit = min(2000, max(limit, 500 if search else limit))
    result = query.order("position").range(offset, offset + fetch_limit - 1).execute()
    rows = result.data or []
    if search:
        needle = search.casefold()
        rows = [
            row for row in rows
            if needle in json.dumps(row.get("payload") or {}, ensure_ascii=False).casefold()
        ]
    rows = rows[:limit]
    return {"records": rows, "total": result.count or len(rows), "offset": offset, "limit": limit}


def _clone_dataset(dataset: dict[str, Any], org_id: str) -> dict[str, Any]:
    clone = create_dataset(
        org_id=org_id,
        job_id=dataset["job_id"],
        name=f"{dataset['name']} — edited",
        kind=dataset["kind"],
        capabilities=dataset.get("capabilities") or [],
        parent_ids=[dataset["id"]],
        state="draft",
        metadata={**(dataset.get("metadata") or {}), "forked_from": dataset["id"]},
    )
    source = list_records(dataset["id"], org_id, limit=2000)["records"]
    rows = [{**row, "dataset_id": clone["id"], "id": None} for row in source]
    for row in rows:
        row.pop("id", None)
        row.pop("created_at", None)
        row.pop("updated_at", None)
    if rows:
        get_supabase().table("candidate_records").insert(rows).execute()
    _update_row_count(clone["id"], org_id)
    return clone


def patch_record(
    dataset_id: str,
    record_id: str,
    org_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    dataset = get_dataset(dataset_id, org_id)
    if not dataset:
        raise LookupError("Dataset not found")
    target_dataset = dataset
    target_record_id = record_id
    if dataset["state"] == "sealed":
        target_dataset = _clone_dataset(dataset, org_id)
        original = (
            get_supabase().table("candidate_records").select("candidate_key")
            .eq("id", record_id).eq("dataset_id", dataset_id).maybe_single().execute().data
        )
        if not original:
            raise LookupError("Record not found")
        clone_record = (
            get_supabase().table("candidate_records").select("id")
            .eq("dataset_id", target_dataset["id"])
            .eq("candidate_key", original["candidate_key"]).maybe_single().execute().data
        )
        target_record_id = clone_record["id"]
    elif dataset["state"] not in ("draft", "partial"):
        raise ValueError("Dataset is not editable")

    allowed = {key: value for key, value in updates.items() if key in {"payload", "tags", "included"}}
    result = (
        get_supabase().table("candidate_records").update(allowed)
        .eq("id", target_record_id).eq("dataset_id", target_dataset["id"])
        .eq("org_id", org_id).execute()
    )
    if not result.data:
        raise LookupError("Record not found")
    return {"dataset": target_dataset, "record": result.data[0]}


def delete_record(dataset_id: str, record_id: str, org_id: str) -> dict[str, Any]:
    dataset = get_dataset(dataset_id, org_id)
    if not dataset:
        raise LookupError("Dataset not found")
    if dataset["state"] not in ("draft", "partial"):
        raise ValueError("Dataset is not editable")
    result = (
        get_supabase().table("candidate_records").delete()
        .eq("id", record_id).eq("dataset_id", dataset_id).eq("org_id", org_id).execute()
    )
    if not result.data:
        raise LookupError("Record not found")
    _update_row_count(dataset_id, org_id)
    return get_dataset(dataset_id, org_id)


def seal_dataset(dataset_id: str, org_id: str) -> dict[str, Any]:
    dataset = get_dataset(dataset_id, org_id)
    if not dataset:
        raise LookupError("Dataset not found")
    if dataset["state"] == "sealed":
        return dataset
    if dataset["state"] not in ("draft", "partial"):
        raise ValueError("Dataset cannot be sealed")
    result = (
        get_supabase().table("candidate_datasets")
        .update({"state": "sealed", "sealed_at": utcnow()})
        .eq("id", dataset_id).eq("org_id", org_id).execute()
    )
    return result.data[0]


def mark_dataset(dataset_id: str, org_id: str, state: str) -> None:
    get_supabase().table("candidate_datasets").update({"state": state}).eq(
        "id", dataset_id
    ).eq("org_id", org_id).execute()


def _flat_payload(payload: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key in CANONICAL_COLUMNS:
        value = payload.get(key)
        row[key] = json.dumps(value, ensure_ascii=False) if key in NESTED_COLUMNS else value
    return row


def export_dataset(dataset_id: str, org_id: str, fmt: str) -> tuple[bytes, str, str]:
    dataset = get_dataset(dataset_id, org_id)
    if not dataset:
        raise LookupError("Dataset not found")
    records = list_records(dataset_id, org_id, limit=2000)["records"]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "dataset": dataset,
        "record_count": len(records),
        "exported_at": utcnow(),
    }
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in dataset["name"])
    if fmt == "json":
        body = json.dumps(
            {"manifest": manifest, "records": records}, ensure_ascii=False, indent=2, default=str
        ).encode()
        return body, "application/json", f"{safe_name}.json"
    flat = [_flat_payload(record.get("payload") or {}) for record in records]
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(flat)
        return output.getvalue().encode("utf-8-sig"), "text/csv", f"{safe_name}.csv"
    if fmt == "xlsx":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame(flat, columns=CANONICAL_COLUMNS).to_excel(
                writer, sheet_name="Candidates", index=False
            )
            pd.DataFrame([
                {"key": key, "value": json.dumps(value, ensure_ascii=False, default=str)}
                for key, value in manifest.items()
            ]).to_excel(writer, sheet_name="Metadata", index=False)
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{safe_name}.xlsx"
    raise ValueError("format must be xlsx, csv, or json")


def _decode_nested(row: dict[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in row.items() if value not in (None, "")}
    for key in NESTED_COLUMNS:
        value = payload.get(key)
        if isinstance(value, str):
            try:
                payload[key] = json.loads(value)
            except json.JSONDecodeError:
                payload[key] = [item.strip() for item in value.split(",") if item.strip()]
    return payload


def parse_import(content: bytes, filename: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "json":
        parsed = json.loads(content.decode("utf-8-sig"))
        if isinstance(parsed, dict) and "records" in parsed:
            payloads = [record.get("payload", record) for record in parsed["records"]]
            return payloads, parsed.get("manifest") or {}
        if isinstance(parsed, list):
            return parsed, {}
        raise ValueError("JSON must contain records or a list")
    if suffix == "csv":
        frame = pd.read_csv(io.BytesIO(content))
        return [_decode_nested(row) for row in frame.where(pd.notnull(frame), None).to_dict("records")], {}
    if suffix in ("xlsx", "xls"):
        frame = pd.read_excel(io.BytesIO(content), sheet_name="Candidates")
        return [_decode_nested(row) for row in frame.where(pd.notnull(frame), None).to_dict("records")], {}
    raise ValueError("Only .xlsx, .xls, .csv, and .json are accepted")

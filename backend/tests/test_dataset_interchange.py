import io
import json

import pandas as pd

from app.services.datasets import candidate_key, parse_import


SAMPLE = {
    "full_name": "Ada Lovelace",
    "linkedin_url": "https://www.linkedin.com/in/ada",
    "skills": ["Python", "Mathematics"],
    "positions": [{"title": "Engineer", "company": "Analytical Engines"}],
}


def test_candidate_key_is_stable():
    assert candidate_key(SAMPLE) == candidate_key(dict(SAMPLE))


def test_lossless_json_import():
    body = json.dumps({"manifest": {"schema_version": 1}, "records": [{"payload": SAMPLE}]}).encode()
    rows, manifest = parse_import(body, "dataset.json")
    assert rows == [SAMPLE]
    assert manifest["schema_version"] == 1


def test_csv_decodes_nested_fields():
    frame = pd.DataFrame([{**SAMPLE, "skills": json.dumps(SAMPLE["skills"]), "positions": json.dumps(SAMPLE["positions"])}])
    content = frame.to_csv(index=False).encode()
    rows, _ = parse_import(content, "dataset.csv")
    assert rows[0]["skills"] == SAMPLE["skills"]
    assert rows[0]["positions"] == SAMPLE["positions"]


def test_xlsx_candidates_sheet_import():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([{**SAMPLE, "skills": json.dumps(SAMPLE["skills"]), "positions": json.dumps(SAMPLE["positions"])}]).to_excel(
            writer, sheet_name="Candidates", index=False
        )
    rows, _ = parse_import(output.getvalue(), "dataset.xlsx")
    assert rows[0]["full_name"] == SAMPLE["full_name"]
    assert rows[0]["skills"] == SAMPLE["skills"]

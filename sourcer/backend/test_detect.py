import asyncio
from app.api.routes_outreach import _detect_columns

columns = ["First Name", "Last Name", "LinkedIn", "Company", "Role"]
sample_rows = [
    {"First Name": "Artem", "Last Name": "Naumchik", "LinkedIn": "https://linkedin.com/in/artem-naumchik-a3079a328", "Company": "Sourcer", "Role": "Engineer"},
    {"First Name": "Stanis", "Last Name": "Khan", "LinkedIn": "https://www.linkedin.com/in/staniskhan/", "Company": "Sourcer", "Role": "Engineer"}
]

mapping = _detect_columns(columns, sample_rows)
print("Detected mapping:", mapping)

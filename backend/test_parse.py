import asyncio
from app.api.routes_outreach import _parse_xlsx_bytes

# Simulating the user's CSV upload
csv_data = b"First Name\tLast Name\tLinkedIn\tCompany\tRole\nArtem\tNaumchik\thttps://linkedin.com/in/artem-naumchik-a3079a328\tSourcer\tEngineer\nStanis\tKhan\thttps://www.linkedin.com/in/staniskhan/\tSourcer\tEngineer"

cols, rows = _parse_xlsx_bytes(csv_data, "test.csv")
print("Columns:", cols)
print("Rows:", rows)

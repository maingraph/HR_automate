"""Pytest config: ensure `app` package importable from backend root."""
import sys
from pathlib import Path

# backend/ is parent of tests/ — add to path so `import app...` works
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

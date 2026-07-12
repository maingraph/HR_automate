"""Apply ordered Supabase migrations through supported Supabase CLI."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if not shutil.which("supabase"):
        print("Supabase CLI missing. Install it, run `supabase link`, then retry.", file=sys.stderr)
        return 2
    result = subprocess.run(["supabase", "db", "push"], cwd=ROOT, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

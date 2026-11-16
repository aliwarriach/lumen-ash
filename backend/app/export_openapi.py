"""Writes the OpenAPI schema to stdout so the app can generate its typed client.

Usage (from backend/): uv run python -m app.export_openapi > ../app/src/api/openapi.json
"""

import json
import os
import sys

# The schema doesn't need real credentials.
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")

from app.main import app  # noqa: E402

json.dump(app.openapi(), sys.stdout, indent=2)
sys.stdout.write("\n")

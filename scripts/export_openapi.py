"""Export the live OpenAPI schema to openapi.yaml at the project root.

Run from the project root:
    python scripts/export_openapi.py

The committed openapi.yaml must match the running service exactly (Integration
Standard point 2). The test backend/tests/test_openapi.py enforces this: if the
file drifts from the live schema, the test fails and tells you to re-run this
script.
"""
from __future__ import annotations

import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND)

from app.main import app  # noqa: E402


def main() -> None:
    schema = app.openapi()
    out_path = os.path.join(PROJECT_ROOT, "openapi.yaml")
    with open(out_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(schema, fh, sort_keys=False, allow_unicode=True)
    print(
        f"Wrote {out_path} "
        f"(OpenAPI {schema.get('openapi')}, {len(schema.get('paths', {}))} paths)"
    )


if __name__ == "__main__":
    main()

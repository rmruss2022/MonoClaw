"""CLI script that exports labeled ML feedback samples to artifacts/feedback_export.json.

Usage:
    python scripts/export_feedback_to_file.py \
        --db-url postgresql+psycopg://payme:payme@localhost:5432/payme

The script calls export_labeled_samples() directly via SQLAlchemy (no HTTP),
writes the result to artifacts/feedback_export.json, and prints a summary.
"""

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Allow running from the repo root without installing the package:
#   python scripts/export_feedback_to_file.py ...
# ---------------------------------------------------------------------------
_repo_root = Path(__file__).resolve().parents[1]
_api_src = _repo_root / "apps" / "api"
if str(_api_src) not in sys.path:
    sys.path.insert(0, str(_api_src))

from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.db import Base  # noqa: E402  (ensures all models are registered)
from app.services.ml.feedback import export_labeled_samples  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export labeled ML feedback samples from the PayMe database."
    )
    parser.add_argument(
        "--db-url",
        default="postgresql+psycopg://payme:payme@localhost:5432/payme",
        help="SQLAlchemy database URL (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default="artifacts/feedback_export.json",
        help="Output file path (default: %(default)s)",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="PostgreSQL schema to use (default: public / server default)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    engine = create_engine(args.db_url, future=True)

    # Optionally pin a non-default schema (useful for dev/test isolation)
    if args.schema:
        schema = args.schema

        @event.listens_for(engine, "checkout")
        def _set_search_path(dbapi_connection, _record, _proxy):
            cursor = dbapi_connection.cursor()
            cursor.execute(f'SET search_path TO "{schema}"')
            cursor.close()

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()

    try:
        print(f"Connecting to: {args.db_url}")
        samples = export_labeled_samples(db)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(samples, indent=2, default=str), encoding="utf-8")

    labeled = [s for s in samples if s.get("label") is not None]
    positive = [s for s in labeled if s.get("label") == 1]
    print(
        f"Exported {len(samples)} samples "
        f"({len(labeled)} labeled, {len(positive)} positive) "
        f"to {out_path}"
    )


if __name__ == "__main__":
    main()

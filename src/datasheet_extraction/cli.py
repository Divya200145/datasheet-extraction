"""Command line: python -m datasheet_extraction extract FILE.pdf [FILE.pdf ...] [--out out.json]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import extract_pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="datasheet_extraction")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract", help="extract fields from one or more datasheet PDFs")
    ex.add_argument("pdfs", nargs="+", type=Path)
    ex.add_argument("--out", type=Path, help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    records = [r for pdf in args.pdfs for r in extract_pdf(pdf)]
    payload = json.dumps([r.model_dump(mode="json") for r in records], indent=2, ensure_ascii=False, sort_keys=True)
    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    review = sum(r.status == "needs_review" for r in records)
    print(f"{len(records)} record(s), {review} need review", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

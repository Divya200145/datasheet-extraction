"""Run the pipeline over every page of every PDF in a folder and print a one-line summary per page.

Usage: python scripts/try_real_pdfs.py path/to/folder [--max-pages 5]

This produces no accuracy figure; it shows what the pipeline recognises and what it routes to review.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pdfplumber  # noqa: E402

from datasheet_extraction.pipeline import extract_page  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--max-pages", type=int, default=5)
    args = ap.parse_args()

    for pdf_path in sorted(args.folder.glob("*.pdf")):
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages[: args.max_pages], start=1):
                    r = extract_page(page, pdf_path.name, i)
                    print(f"{pdf_path.name} p{i}: {r.status} tag={r.tag} P={r.design_pressure_barg} "
                          f"T={r.design_temp_c} material={r.material} warnings={len(r.warnings)}")
        except Exception as exc:  # keep going if one file is unreadable
            print(f"{pdf_path.name}: could not be read ({exc})")


if __name__ == "__main__":
    main()

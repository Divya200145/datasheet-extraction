"""Extraction pipeline: layout analysis -> label vocabulary -> unit normalisation -> validation.

Design choices:
  * deterministic first: no model is involved unless an `LLMFallback` is passed in;
  * never guess: an unknown label leaves the field empty and the record goes to review;
  * every value carries provenance (method, label, bounding box, raw text);
  * output is canonicalised (sorted keys, rounded numbers) so repeated runs are byte-identical.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Optional

import pdfplumber

from .layout import Pair, find_pairs, page_lines
from .llm import LLMFallback
from .normalize import (
    Parsed,
    normalise_material,
    parse_power,
    parse_pressure,
    parse_temperature,
)
from .schema import NON_TAG_PREFIXES, TAG_RE, DatasheetRecord, is_valid_tag

REQUIRED = ("tag", "design_pressure_barg", "design_temp_c")
OPTIONAL = ("service", "material", "power_kw")

# canonical label-field -> record field
_FIELD_MAP = {
    "tag": "tag",
    "service": "service",
    "design_pressure": "design_pressure_barg",
    "design_temperature": "design_temp_c",
    "material": "material",
    "power": "power_kw",
}
_PARSERS = {
    "design_pressure_barg": parse_pressure,
    "design_temp_c": parse_temperature,
    "power_kw": parse_power,
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _scan_for_tag(lines) -> tuple[Optional[str], Optional[str]]:
    """Fallback: look for a single unambiguous tag-shaped token anywhere on the page."""
    found = set()
    for line in lines:
        for cell in line:
            for token in re.split(r"[\s,;()]+", cell.text):
                token = token.strip(".:").upper()
                if is_valid_tag(token) and token.split("-")[0] not in NON_TAG_PREFIXES:
                    found.add(token)
    if len(found) == 1:
        return next(iter(found)), None
    if not found:
        return None, "no tag-shaped token found on page"
    return None, f"ambiguous tag candidates: {sorted(found)}"


def extract_page(page, source: str, page_no: int, llm: Optional[LLMFallback] = None) -> DatasheetRecord:
    lines = page_lines(page)
    pairs = find_pairs(lines)

    chosen: dict[str, Pair] = {}
    warnings: list[str] = []
    reasons: list[str] = []
    for p in pairs:
        key = _FIELD_MAP[p.field]
        if key in chosen:
            if _clean(chosen[key].value_text) != _clean(p.value_text):
                warnings.append(f"conflicting values for {key}: kept {chosen[key].value_text!r}, ignored {p.value_text!r}")
            continue
        chosen[key] = p

    values: dict[str, object] = {}
    provenance: dict[str, dict] = {}

    def prov(field: str, p: Pair, method: Optional[str] = None) -> None:
        provenance[field] = {
            "method": method or p.method,
            "label": _clean(p.label_text),
            "raw": _clean(p.value_text),
            "bbox": p.bbox,
        }

    for key, p in chosen.items():
        raw = _clean(p.value_text)
        if key == "tag":
            tag = raw.upper()
            if is_valid_tag(tag):
                values["tag"] = tag
                prov("tag", p)
            else:
                warnings.append(f"tag value {raw!r} does not look like an equipment tag")
        elif key == "service":
            values["service"] = raw
            prov("service", p)
        elif key == "material":
            mat = normalise_material(raw)
            if mat:
                values["material"] = mat
                prov("material", p)
            else:
                warnings.append(f"unrecognised material {raw!r}")
        else:
            parsed: Parsed = _PARSERS[key](raw, p.unit_hint)
            if parsed.error:
                warnings.append(parsed.error)
            if parsed.warning:
                warnings.append(parsed.warning)
            if parsed.value is not None:
                values[key] = parsed.value
                prov(key, p)

    if "tag" not in values:
        tag, note = _scan_for_tag(lines)
        if tag:
            values["tag"] = tag
            provenance["tag"] = {"method": "pattern_scan", "label": None, "raw": tag, "bbox": None}
            warnings.append("tag found by pattern scan, not by label")
        elif note:
            warnings.append(note)

    if llm is not None:
        missing = [f for f in (*REQUIRED, *OPTIONAL) if f not in values]
        if missing:
            page_text = "\n".join("   ".join(c.text for c in line) for line in lines)
            for key, raw in sorted(llm.extract(page_text, missing).items()):
                if key not in missing or key in values:
                    continue  # the model may never override or add unrequested fields
                raw = _clean(str(raw))
                if key == "tag":
                    ok = is_valid_tag(raw.upper())
                    val: object = raw.upper() if ok else None
                elif key == "service":
                    val = raw or None
                elif key == "material":
                    val = normalise_material(raw)
                else:
                    parsed = _PARSERS[key](raw, None)
                    val = parsed.value
                    if parsed.error:
                        warnings.append(f"llm fallback: {parsed.error}")
                if val is not None:
                    values[key] = val
                    provenance[key] = {"method": "llm_fallback", "label": None, "raw": raw, "bbox": None}
                    warnings.append(f"{key} came from the LLM fallback; verify before use")

    for field in REQUIRED:
        if field not in values:
            reasons.append(f"missing required field: {field}")

    return DatasheetRecord(
        source_file=source,
        page=page_no,
        status="needs_review" if reasons else "ok",
        review_reasons=reasons,
        warnings=warnings,
        provenance=provenance,
        **values,
    )


def extract_pdf(path: str | Path, llm: Optional[LLMFallback] = None) -> list[DatasheetRecord]:
    """One record per page; each page is treated as one equipment datasheet."""
    path = Path(path)
    with pdfplumber.open(path) as pdf:
        return [extract_page(page, path.name, i, llm) for i, page in enumerate(pdf.pages, start=1)]


def canonical_json(records: Iterable[DatasheetRecord]) -> str:
    """Stable serialisation: identical input must give byte-identical output."""
    return json.dumps(
        [r.model_dump(mode="json") for r in records],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

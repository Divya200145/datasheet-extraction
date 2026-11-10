"""Output schema and tag validation."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ISA-style equipment tags: P-101, P-101A, PSV-1204, 10-P-101
TAG_RE = re.compile(r"^(?:\d{1,3}-)?[A-Z]{1,4}-\d{2,4}[A-Z]?$")

# Prefixes that look like tags but are document identifiers (used only by the pattern-scan fallback).
NON_TAG_PREFIXES = frozenset({"DS", "DOC", "REV", "ISO", "PO", "REF", "DWG", "SO"})


def is_valid_tag(value: str) -> bool:
    return bool(TAG_RE.match(value))


class DatasheetRecord(BaseModel):
    """One equipment datasheet (one PDF page) in canonical units: barg, degC, kW."""

    source_file: str
    page: int
    tag: Optional[str] = None
    service: Optional[str] = None
    design_pressure_barg: Optional[float] = None
    design_temp_c: Optional[float] = None
    material: Optional[str] = None
    power_kw: Optional[float] = None
    status: Literal["ok", "needs_review"]
    review_reasons: list[str] = Field(default_factory=list)  # why a human should look
    warnings: list[str] = Field(default_factory=list)  # non-blocking notes
    provenance: dict[str, dict[str, Any]] = Field(default_factory=dict)  # field -> how/where it was read

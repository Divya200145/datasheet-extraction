"""Label vocabulary: maps the many ways vendors name a field onto one canonical field.

Matching is exact on a normalised label (no fuzzy matching) so behaviour is reproducible.
A label that is not in this vocabulary is deliberately *not* guessed; the pipeline will
report the field as missing and route the record to review.
"""

from __future__ import annotations

import re
from typing import Optional

LABEL_SYNONYMS: dict[str, list[str]] = {
    "tag": ["tag number", "tag no", "tag", "equipment tag", "equipment id", "equipment no", "item code", "item no", "item number"],
    "service": ["service", "duty", "fluid service"],
    "design_pressure": ["design pressure", "design press", "max pressure", "maximum pressure", "mawp"],
    "design_temperature": ["design temperature", "design temp", "max temp", "maximum temperature"],
    "material": ["material of construction", "material", "body material", "shell material", "moc"],
    "power": ["motor power", "rated power", "power"],
}

_PAREN = re.compile(r"\(([^)]*)\)")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


_LOOKUP: dict[str, str] = {_norm(s): field for field, syns in LABEL_SYNONYMS.items() for s in syns}


def match_label(text: str) -> Optional[tuple[str, Optional[str]]]:
    """Return (canonical_field, unit_hint) if `text` is a known label, else None.

    The unit hint comes from a parenthesised unit in the label, e.g. "Max Pressure (psig)".
    """
    hint_match = _PAREN.search(text)
    hint = hint_match.group(1).strip() if hint_match else None
    field = _LOOKUP.get(_norm(_PAREN.sub(" ", text)))
    return (field, hint) if field else None


def split_inline(text: str) -> Optional[tuple[str, Optional[str], str]]:
    """For "Label: value" cells. Returns (field, unit_hint, value_text) or None."""
    if ":" not in text:
        return None
    before, after = text.split(":", 1)
    matched = match_label(before)
    if matched and after.strip():
        return matched[0], matched[1], after.strip()
    return None

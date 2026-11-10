"""Optional LLM fallback interface.

The deterministic path never calls a model. If you want a fallback for layouts the label
vocabulary does not cover, implement this protocol and pass it to `extract_pdf(..., llm=...)`.

Rules the pipeline enforces around any implementation:
  * it is only asked for fields that the deterministic path left empty (it can never override);
  * every value it returns goes through the same unit parsing, range checks and tag validation;
  * values that come from it are tagged in `provenance` and get a warning for human verification.

If you implement it with a hosted model, set temperature to 0 and request schema-constrained
JSON, but note that this reduces rather than removes run-to-run variation.

No concrete implementation is included, and the evaluation in this repo does not exercise one.
"""

from __future__ import annotations

from typing import Protocol


class LLMFallback(Protocol):
    def extract(self, page_text: str, fields: list[str]) -> dict[str, str]:
        """Return raw strings (with units) keyed by canonical field name for the requested fields."""
        ...

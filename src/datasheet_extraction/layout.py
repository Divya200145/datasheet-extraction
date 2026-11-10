"""Layout analysis on top of pdfplumber word boxes.

Instead of relying on ruling lines, words are grouped into visual lines and then split into
"cells" wherever there is a wide horizontal gap. Label/value pairs are then recovered from
three patterns seen across vendors:

  * inline_colon : "Design temp.: 250 C"           (label and value in one cell)
  * same_row     : [Design Pressure]   [16.0 barg]   (value is the next cell on the line)
  * below        : [Max Pressure (psig)]            (value sits under the label, same columns)
                   [232]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .templates import match_label, split_inline

LINE_TOL = 3.0  # pt: words whose vertical centres differ by less belong to the same line
CELL_GAP = 10.0  # pt: horizontal gap that separates two cells on one line
BELOW_MAX_DY = 30.0  # pt: how far below a label a value may sit
MIN_OVERLAP = 0.4  # fraction of the narrower cell that must overlap horizontally


@dataclass(frozen=True)
class Cell:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float

    @property
    def yc(self) -> float:
        return (self.top + self.bottom) / 2

    def bbox(self) -> list[float]:
        return [round(v, 1) for v in (self.x0, self.top, self.x1, self.bottom)]


@dataclass(frozen=True)
class Pair:
    field: str
    label_text: str
    unit_hint: Optional[str]
    value_text: str
    method: str
    bbox: list[float]


def page_lines(page) -> list[list[Cell]]:
    """Return the page as a list of lines, each a left-to-right list of cells."""
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
    words = sorted(words, key=lambda w: ((w["top"] + w["bottom"]) / 2, w["x0"]))
    groups: list[list[dict]] = []
    ref_y = None
    for w in words:
        yc = (w["top"] + w["bottom"]) / 2
        if not groups or abs(yc - ref_y) > LINE_TOL:
            groups.append([])
            ref_y = yc
        groups[-1].append(w)

    lines: list[list[Cell]] = []
    for group in groups:
        group.sort(key=lambda w: w["x0"])
        cells: list[list[dict]] = [[group[0]]]
        for prev, w in zip(group, group[1:]):
            if w["x0"] - prev["x1"] > CELL_GAP:
                cells.append([w])
            else:
                cells[-1].append(w)
        lines.append(
            [
                Cell(
                    text=" ".join(w["text"] for w in c),
                    x0=c[0]["x0"],
                    x1=c[-1]["x1"],
                    top=min(w["top"] for w in c),
                    bottom=max(w["bottom"] for w in c),
                )
                for c in cells
            ]
        )
    return lines


def _overlap(a: Cell, b: Cell) -> float:
    inter = min(a.x1, b.x1) - max(a.x0, b.x0)
    narrower = min(a.x1 - a.x0, b.x1 - b.x0)
    return inter / narrower if narrower > 0 and inter > 0 else 0.0


def find_pairs(lines: list[list[Cell]]) -> list[Pair]:
    """Recover label/value pairs in reading order (top-to-bottom, left-to-right)."""
    pairs: list[Pair] = []
    for li, line in enumerate(lines):
        for ci, cell in enumerate(line):
            inline = split_inline(cell.text)
            if inline:
                field, hint, value = inline
                pairs.append(Pair(field, cell.text.split(":", 1)[0], hint, value, "inline_colon", cell.bbox()))
                continue

            matched = match_label(cell.text)
            if not matched:
                continue
            field, hint = matched

            # same_row: next cell on the line, unless it is itself a label.
            if ci + 1 < len(line) and not match_label(line[ci + 1].text) and not split_inline(line[ci + 1].text):
                nxt = line[ci + 1]
                pairs.append(Pair(field, cell.text, hint, nxt.text, "same_row", nxt.bbox()))
                continue

            # below: nearest cell on the next line that overlaps horizontally and is not a label.
            if li + 1 < len(lines) and lines[li + 1][0].yc - cell.yc <= BELOW_MAX_DY:
                candidates = [
                    (c, _overlap(cell, c))
                    for c in lines[li + 1]
                    if _overlap(cell, c) >= MIN_OVERLAP and not match_label(c.text) and not split_inline(c.text)
                ]
                if candidates:
                    best = max(candidates, key=lambda t: (t[1], -t[0].x0))[0]
                    pairs.append(Pair(field, cell.text, hint, best.text, "below", best.bbox()))
    return pairs

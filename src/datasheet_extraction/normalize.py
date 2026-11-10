"""Unit parsing and value normalisation to canonical units (barg, degC, kW)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_QTY = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)\s*(.*?)\s*$")

# Multipliers to canonical units.
_PRESSURE_TO_BARG = {
    "barg": 1.0,
    "bar": 1.0,  # gauge is assumed; a warning is attached
    "psig": 0.0689476,
    "psi": 0.0689476,
    "kpa": 0.01,
    "kpag": 0.01,
    "mpa": 10.0,
    "mpag": 10.0,
}
_POWER_TO_KW = {"kw": 1.0, "w": 0.001, "hp": 0.7457}

# Plausibility limits; values outside are dropped and the record goes to review.
LIMITS = {
    "design_pressure_barg": (-1.0, 1500.0),
    "design_temp_c": (-273.0, 1500.0),
    "power_kw": (0.0, 100000.0),
}


@dataclass(frozen=True)
class Parsed:
    value: Optional[float]
    warning: Optional[str] = None
    error: Optional[str] = None


def _norm_unit(unit: str) -> str:
    u = re.sub(r"[\s°().]", "", unit.lower())
    return {"degc": "c", "degf": "f", "celsius": "c", "fahrenheit": "f"}.get(u, u)


def _split_qty(text: str, unit_hint: Optional[str]) -> Optional[tuple[float, str]]:
    m = _QTY.match(text)
    if not m:
        return None
    rest = m.group(2).split()[0] if m.group(2) else ""
    unit = rest or (unit_hint or "")
    return float(m.group(1)), _norm_unit(unit)


def _check(field: str, value: float) -> Parsed:
    lo, hi = LIMITS[field]
    if not lo <= value <= hi:
        return Parsed(None, error=f"{field}={value} outside plausible range [{lo}, {hi}]")
    return Parsed(round(value, 2))


def parse_pressure(text: str, unit_hint: Optional[str] = None) -> Parsed:
    q = _split_qty(text, unit_hint)
    if q is None:
        return Parsed(None, error=f"could not parse pressure from {text!r}")
    value, unit = q
    if unit not in _PRESSURE_TO_BARG:
        return Parsed(None, error=f"unknown or missing pressure unit {unit!r} in {text!r}")
    result = _check("design_pressure_barg", value * _PRESSURE_TO_BARG[unit])
    if unit == "bar" and result.value is not None:
        return Parsed(result.value, warning="unit 'bar' assumed to be gauge (barg)")
    return result


def parse_temperature(text: str, unit_hint: Optional[str] = None) -> Parsed:
    q = _split_qty(text, unit_hint)
    if q is None:
        return Parsed(None, error=f"could not parse temperature from {text!r}")
    value, unit = q
    if unit == "c":
        celsius = value
    elif unit == "f":
        celsius = (value - 32.0) * 5.0 / 9.0
    elif unit == "k":
        celsius = value - 273.15
    else:
        return Parsed(None, error=f"unknown or missing temperature unit {unit!r} in {text!r}")
    return _check("design_temp_c", celsius)


def parse_power(text: str, unit_hint: Optional[str] = None) -> Parsed:
    q = _split_qty(text, unit_hint)
    if q is None:
        return Parsed(None, error=f"could not parse power from {text!r}")
    value, unit = q
    if unit not in _POWER_TO_KW:
        return Parsed(None, error=f"unknown or missing power unit {unit!r} in {text!r}")
    return _check("power_kw", value * _POWER_TO_KW[unit])


def normalise_material(text: str) -> Optional[str]:
    """Map free-text material descriptions to a small canonical set; None if not recognised."""
    t = text.lower()
    if "316l" in t:
        return "SS316L"
    if "316" in t:
        return "SS316"
    if "304" in t:
        return "SS304"
    if "carbon" in t or re.search(r"\bcs\b", t) or re.search(r"\ba10[56]\b", t):
        return "CS"
    return None

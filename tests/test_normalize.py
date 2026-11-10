import pytest

from datasheet_extraction.normalize import (
    normalise_material,
    parse_power,
    parse_pressure,
    parse_temperature,
)
from datasheet_extraction.schema import is_valid_tag
from datasheet_extraction.templates import match_label, split_inline


@pytest.mark.parametrize(
    "text,hint,expected",
    [("16.0 barg", None, 16.0), ("232", "psig", 15.99), ("1.65 MPa", None, 16.5), ("250 kPa", None, 2.5)],
)
def test_pressure_units(text, hint, expected):
    assert parse_pressure(text, hint).value == pytest.approx(expected, abs=0.01)


def test_bar_is_assumed_gauge_with_warning():
    p = parse_pressure("25 bar")
    assert p.value == 25.0 and "gauge" in p.warning


def test_missing_unit_is_an_error_not_a_guess():
    p = parse_pressure("232")
    assert p.value is None and p.error


@pytest.mark.parametrize("text,hint,expected", [("120 °C", None, 120.0), ("248", "°F", 120.0), ("250 C", None, 250.0), ("393.15 K", None, 120.0)])
def test_temperature_units(text, hint, expected):
    assert parse_temperature(text, hint).value == pytest.approx(expected, abs=0.01)


def test_out_of_range_is_dropped():
    assert parse_temperature("99999 C").value is None


@pytest.mark.parametrize("text,hint,expected", [("15 kW", None, 15.0), ("20", "hp", 14.91), ("500 W", None, 0.5)])
def test_power_units(text, hint, expected):
    assert parse_power(text, hint).value == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize(
    "text,expected",
    [("Stainless Steel 316L", "SS316L"), ("316 stainless", "SS316"), ("SS304", "SS304"), ("Carbon steel (A105)", "CS"), ("Hastelloy", None)],
)
def test_material(text, expected):
    assert normalise_material(text) == expected


@pytest.mark.parametrize("tag,ok", [("P-101A", True), ("PSV-1204", True), ("10-P-101", True), ("p-101", False), ("P101", False), ("DS-0042x", False)])
def test_tag_validation(tag, ok):
    assert is_valid_tag(tag) is ok


def test_label_vocabulary():
    assert match_label("Item Code") == ("tag", None)
    assert match_label("Max Pressure (psig)") == ("design_pressure", "psig")
    assert match_label("Position No.") is None  # unknown labels are never guessed
    assert split_inline("Design temp.: 250 C") == ("design_temperature", None, "250 C")
    assert split_inline("Note 1: something") is None

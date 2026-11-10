import json

import pytest

from datasheet_extraction import canonical_json, extract_pdf
from datasheet_extraction.synth import generate_dataset


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    d = tmp_path_factory.mktemp("synth")
    truth = generate_dataset(d, n_per_layout=5, seed=11)
    return d, truth


def test_known_layouts_extract_correctly(dataset):
    d, truth = dataset
    for item in truth:
        if item["layout"] == "D":
            continue
        rec = extract_pdf(d / item["file"])[0]
        assert rec.status == "ok", (item["file"], rec.review_reasons)
        assert rec.tag == item["tag"]
        assert rec.material == item["material"]
        assert rec.design_pressure_barg == pytest.approx(item["design_pressure_barg"], abs=0.05)
        assert rec.design_temp_c == pytest.approx(item["design_temp_c"], abs=0.5)
        if item["power_kw"] is None:
            assert rec.power_kw is None
        else:
            assert rec.power_kw == pytest.approx(item["power_kw"], abs=0.5)


def test_unseen_labels_go_to_review_and_are_not_guessed(dataset):
    d, truth = dataset
    for item in (t for t in truth if t["layout"] == "D"):
        rec = extract_pdf(d / item["file"])[0]
        assert rec.status == "needs_review"
        assert rec.design_pressure_barg is None and rec.design_temp_c is None
        assert rec.provenance["tag"]["method"] == "pattern_scan"


def test_output_is_deterministic(dataset):
    d, truth = dataset
    for item in truth[::3]:
        outputs = {canonical_json(extract_pdf(d / item["file"])) for _ in range(5)}
        assert len(outputs) == 1


def test_provenance_is_recorded(dataset):
    d, truth = dataset
    rec = extract_pdf(d / next(t["file"] for t in truth if t["layout"] == "B"))[0]
    assert rec.provenance["design_pressure_barg"]["method"] == "below"
    assert rec.provenance["design_pressure_barg"]["label"] == "Max Pressure (psig)"
    json.dumps(rec.model_dump(mode="json"))  # serialisable


class FakeLLM:
    def extract(self, page_text, fields):
        # tries to override a deterministic value and to add an unrequested field
        return {"design_pressure_barg": "999 barg", "design_temp_c": "100 C", "power_kw": "5 kW", "bogus": "x"}


def test_llm_fallback_only_fills_gaps_and_is_marked(dataset):
    d, truth = dataset
    item = next(t for t in truth if t["layout"] == "C")  # has pressure and temp, no power
    rec = extract_pdf(d / item["file"], llm=FakeLLM())[0]
    assert rec.design_pressure_barg == pytest.approx(item["design_pressure_barg"], abs=0.05)  # not overridden
    assert rec.power_kw == 5.0 and rec.provenance["power_kw"]["method"] == "llm_fallback"
    assert any("LLM fallback" in w for w in rec.warnings)

    item_d = next(t for t in truth if t["layout"] == "D")
    rec_d = extract_pdf(d / item_d["file"], llm=FakeLLM())[0]
    assert rec_d.design_pressure_barg == 999.0  # accepted from llm but flagged...
    assert any("verify" in w for w in rec_d.warnings)  # ...so a human is told to check it

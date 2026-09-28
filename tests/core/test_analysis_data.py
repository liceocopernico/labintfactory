import math

import pytest

from labdaemon.core.analysis import LinearFit, Measured, absorbance, linear_fit
from labdaemon.core.calibration import Calibration, CalibrationLibrary
from labdaemon.core.data import Channel, Dataset
from labdaemon.core.errors import ExperimentError, LabError
from labdaemon.core.session import Session

DESIGN_POINTS = ([0.0, 0.02, 0.04, 0.06], [0.0, 0.138, 0.268, 0.409])  # the design's calibration example


def test_linear_fit_matches_the_design_example():
    fit = linear_fit(*DESIGN_POINTS, x_unit="mol/L")
    assert fit.slope.value == pytest.approx(6.785)
    assert fit.slope.stderr == pytest.approx(0.0712, abs=1e-4)
    assert fit.intercept.value == pytest.approx(0.0002, abs=1e-6)
    assert fit.r2 == pytest.approx(0.99978, abs=1e-5)
    assert str(fit.slope) == "6.785 ± 0.071 L/mol"
    assert fit.formula("c", "A") == "A = 6.785·c + 0.0002"


def test_inverse_gives_concentration_with_uncertainty():
    fit = linear_fit(*DESIGN_POINTS)
    c = fit.inverse(0.543)
    assert c.value == pytest.approx((0.543 - fit.intercept.value) / fit.slope.value)
    assert 0 < c.stderr < 0.01
    # further from the centre of the calibration, the uncertainty grows
    assert fit.inverse(1.0).stderr > fit.inverse(0.2).stderr


def test_fit_through_origin_and_round_trip():
    fit = linear_fit([0.01, 0.02, 0.03], [0.07, 0.135, 0.205], through_origin=True)
    assert fit.intercept.value == 0 and fit.formula() == "y = 6.821·x"  # Σxy / Σx²
    again = LinearFit.from_dict(fit.to_dict())
    assert again.inverse(0.1).value == pytest.approx(fit.inverse(0.1).value)


def test_fit_and_absorbance_refuse_impossible_input():
    with pytest.raises(ExperimentError):
        linear_fit([0.1], [0.5])
    with pytest.raises(ExperimentError):
        linear_fit([0.1, 0.1], [0.5, 0.6])
    with pytest.raises(ExperimentError, match="blank"):
        absorbance(0.0, 1.0)
    with pytest.raises(ExperimentError, match="No light"):
        absorbance(100.0, 0.0)
    assert absorbance(100.0, 10.0) == pytest.approx(1.0)


def test_measured_rounding():
    assert str(Measured(0.0441183, 0.0000362, "mol/L")) == "0.044118 ± 0.000036 mol/L"
    assert str(Measured(412.35)) == "412.4"


def test_dataset_csv_presets_round_trip():
    ds = Dataset("standards", [Channel("c", "Concentration", "mol/L"), Channel("A", "Absorbance", "")])
    changes = []
    ds.changed.connect(lambda: changes.append(1))
    ds.append(c=0.02, A=0.138)
    ds.append(c=0.04)
    assert math.isnan(ds.row(1)["A"]) and len(changes) == 2
    italian = ds.to_csv(preset="excel-it")
    assert italian.splitlines()[1] == "0,02;0,138"
    copy = Dataset("standards", ds.channels)
    copy.read_csv(italian, preset="excel-it")
    assert copy.rows()[0] == {"c": 0.02, "A": 0.138}
    with pytest.raises(KeyError):
        ds.append(zzz=1)


def test_session_save_and_load(tmp_path):
    s = Session("absorbance", title="Copper sulfate", group="3B Rossi")
    s.dataset("standards", [Channel("c", "Concentration", "mol/L"), Channel("A", "Absorbance", "")]).append(
        c=0.02, A=0.138)
    s.results["fit"] = {"slope": 6.785}
    s.note("blank measured")
    path = s.save(tmp_path / s.default_filename())
    assert path.name.endswith("_absorbance_copper-sulfate_3b-rossi.labint") and ":" not in path.name
    loaded = Session.load(path)
    assert loaded.title == "Copper sulfate" and loaded.results["fit"]["slope"] == 6.785
    assert loaded.datasets["standards"].rows() == [{"c": 0.02, "A": 0.138}]
    assert loaded.log[0].endswith("blank measured")
    (tmp_path / "bad.labint").write_bytes(b"not a zip")
    with pytest.raises(LabError):
        Session.load(tmp_path / "bad.labint")


def test_calibration_library(tmp_path):
    lib = CalibrationLibrary(tmp_path / "cal")
    fit = linear_fit(*DESIGN_POINTS)
    points = [list(p) for p in zip(*DESIGN_POINTS, strict=True)]
    cal = Calibration("absorbance.linear", "CuSO₄ · red LED", fit.to_dict(), points,
                      {"led_color": "red", "led_power": 1850}, units={"x": "mol/L", "y": ""})
    lib.save(cal)
    (tmp_path / "cal" / "junk.json").write_text("{", encoding="utf-8")
    found = lib.list("absorbance.linear")
    assert [c.label for c in found] == ["CuSO₄ · red LED"]
    assert found[0].linear_fit().slope.value == pytest.approx(6.785)
    assert found[0].differences({"led_color": "red", "led_power": 2000}) == {"led_power": (1850, 2000)}
    lib.delete(found[0])
    assert lib.list() == []

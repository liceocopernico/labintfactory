import pytest

from labdaemon import Lab
from labdaemon.core.calibration import CalibrationLibrary
from labdaemon.core.errors import ExperimentError, NotReady
from labdaemon.core.session import Session


@pytest.fixture
def lab(settings):
    with Lab(settings=settings) as lab:
        yield lab


@pytest.fixture
def rig(lab):
    board = lab.simulate("tsl2591_photometer")
    photo = board["photometer"]
    photo.set_output("red", 1850)
    exp = lab.experiment("absorbance", sensor=photo, source=photo)

    def cuvette(a):
        lab.manager.run_on_board(board._board.key,
                                 lambda wire: wire.query("SIM", f"absorbance={a}", fn="photometer")).result(1)

    return exp, cuvette, photo


def test_full_lab(rig, tmp_path):
    exp, cuvette, _photo = rig
    with pytest.raises(NotReady, match="blank"):
        exp.run_operation("measure_standard", 0.02)
    cuvette(0.0)
    assert exp.run_operation("measure_blank") == pytest.approx(412.4, rel=0.01)
    for c in (0.02, 0.04, 0.06):
        cuvette(6.785 * c)
        exp.run_operation("measure_standard", c)
    assert exp.count_standards() == 3
    assert exp.fit.slope.value == pytest.approx(6.785, rel=0.01)
    assert exp.epsilon().unit == "L·mol⁻¹·cm⁻¹"
    cuvette(0.3)
    c = exp.run_operation("measure_unknown", "X")
    assert c.value == pytest.approx(0.3 / 6.785, rel=0.02) and c.stderr > 0
    labels = dict(exp.summary())
    assert labels["X"].endswith("mol/L") and labels["Standards"] == "3"
    exp.set_parameter("solution", "copper sulfate")
    path = exp.session.save(tmp_path / exp.session.default_filename())
    assert "copper-sulfate" in path.name
    assert Session.load(path).results["formula"].startswith("A = ")


def test_new_blank_recomputes_standards(rig):
    exp, cuvette, _photo = rig
    cuvette(0.0)
    exp.run_operation("measure_blank")
    cuvette(0.2)
    exp.run_operation("measure_standard", 0.03)
    a_before = exp.standards.row(1)["A"]
    cuvette(0.0)
    exp.run_operation("measure_blank")  # the same light again: A of the standard should barely change
    assert exp.standards.row(1)["A"] == pytest.approx(a_before, abs=0.01)
    with pytest.raises(ExperimentError, match="blank stays"):
        exp.run_operation("remove_standard", 0)


def test_saturation_is_refused(rig):
    exp, cuvette, photo = rig
    photo.set_parameter("gain", 428)
    with pytest.raises(ExperimentError, match="saturated"):
        exp.run_operation("measure_blank")


def test_saved_calibration_is_reused(rig, settings):
    exp, cuvette, photo = rig
    cuvette(0.0)
    exp.run_operation("measure_blank")
    for c in (0.02, 0.04):
        cuvette(6.785 * c)
        exp.run_operation("measure_standard", c)
    exp.run_operation("save_calibration", "CuSO₄ red")
    photo.set_parameter("led_power", 2500)  # someone changed the LED power since
    cal = CalibrationLibrary(settings.paths.data_dir / "calibrations").list()[0]
    fresh_session = Session("absorbance")
    exp2 = type(exp)({"sensor": photo, "source": photo}, fresh_session)
    differences = exp2.apply_calibration(cal)
    assert differences == {"led_power": (1850, 2500)}
    assert photo.params.values()["led_power"] == 1850  # conditions restored, colour before power
    with pytest.raises(NotReady, match="blank"):
        exp2.run_operation("measure_unknown")  # I₀ is measured again every day
    cuvette(0.0)
    exp2.run_operation("measure_blank")
    cuvette(0.2)
    assert exp2.run_operation("measure_unknown").value == pytest.approx(0.2 / 6.785, rel=0.03)


def test_check_light_guides_the_setup(rig):
    exp, _cuvette, _photo = rig
    assert exp.check_light({}) is not None
    assert "saturated" in exp.check_light({"saturated": 1.0, "ch0": 40000})
    assert "Too little light" in exp.check_light({"ch0": 50})
    assert exp.check_light({"ch0": 5000, "saturated": 0.0}) is None

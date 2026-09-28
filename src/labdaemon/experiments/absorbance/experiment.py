"""Absorbance and concentration (Beer–Lambert): A = ε·l·c.

1. Measure the blank (the solvent): its light I₀ is the zero of the absorbance scale.
2. Measure standards of known concentration: A = log₁₀(I₀/I); a straight line through them is the calibration.
3. Measure unknown samples: their concentration comes from the line, with its uncertainty.
"""

import math
from pathlib import Path
from typing import Any

from labdaemon.core.analysis import LinearFit, Measured, absorbance, linear_fit
from labdaemon.core.calibration import Calibration
from labdaemon.core.capabilities import LightReading, LightSensor, LightSource
from labdaemon.core.data import Channel
from labdaemon.core.errors import ExperimentError, NotReady
from labdaemon.core.experiment import Experiment, PlotData, Requirement, Series, action
from labdaemon.core.i18n import N_, _
from labdaemon.core.parameters import Parameter
from labdaemon.core.wizard import ActionStep, DevicesStep, InstructionStep, ParametersStep, ResultStep, Step, TableStep

UNITS = ("mol/L", "mmol/L", "g/L", "mg/L")
CONDITION_KEYS = ("led_color", "led_power", "integration_time", "gain")
KIND = "absorbance.linear"


class Absorbance(Experiment):
    id = "absorbance"
    name = N_("Absorbance and concentration")
    category = "chemistry"
    description = N_("Calibrate with standard solutions, then find the concentration of an unknown sample "
                     "(Beer–Lambert).")
    requires = {
        "sensor": Requirement(LightSensor, N_("Light sensor")),
        "source": Requirement(LightSource, N_("Light source")),
    }
    parameters = [
        Parameter("samples", N_("Readings per measurement"), int, 3, minimum=1, maximum=15,
                  help=N_("Each measurement is the mean of this many sensor readings.")),
        Parameter("unit", N_("Concentration unit"), str, "mol/L", choices=UNITS),
        Parameter("solution", N_("Solution"), str, "",
                  help=N_("What you are measuring, e.g. copper sulfate. Used to name files and calibrations.")),
        Parameter("path_length", N_("Cuvette path length"), float, 1.0, unit="cm", minimum=0.01, maximum=10.0,
                  step=0.1, advanced=True),
        Parameter("through_origin", N_("Force the line through the origin"), bool, False, advanced=True),
    ]
    device_keys = CONDITION_KEYS

    # ── state ──
    def setup(self) -> None:
        unit = self.params["unit"]
        self.standards = self.session.dataset("standards", [
            Channel("c", N_("Concentration"), unit, "c"), Channel("lux", N_("Illuminance"), "lx", "I"),
            Channel("T", N_("Transmittance"), "", "T"), Channel("A", N_("Absorbance"), "", "A")])
        self.unknowns = self.session.dataset("unknowns", [
            Channel("sample", N_("Sample"), ""), Channel("lux", N_("Illuminance"), "lx", "I"),
            Channel("T", N_("Transmittance"), "", "T"), Channel("A", N_("Absorbance"), "", "A"),
            Channel("c", N_("Concentration"), unit, "c"), Channel("c_err", N_("Uncertainty"), unit, "u(c)")])
        self.session.title = self.session.title or self.params["solution"]
        results = self.session.results
        self.blank: float | None = results.get("blank_lux")
        self.fit: LinearFit | None = LinearFit.from_dict(results["fit"], unit) if results.get("fit") else None

    def set_parameter(self, key: str, value: Any) -> None:
        super().set_parameter(key, value)
        if key == "solution":
            self.session.title = self.params["solution"]
        if key == "unit":
            for ds in (self.standards, self.unknowns):
                ds.channels = [Channel(c.key, c.label, self.params["unit"], c.symbol) if c.key in ("c", "c_err") else c
                               for c in ds.channels]
        if key in ("through_origin", "unit"):
            self._refit()

    def conditions(self) -> dict[str, Any]:
        """The settings a calibration is only valid for."""
        values: dict[str, Any] = {}
        for role in ("source", "sensor"):
            dev = self.devices.get(role)
            if dev is not None and hasattr(dev, "params"):
                values |= {k: v for k, v in dev.params.values().items() if k in CONDITION_KEYS}
        values["path_length_cm"] = self.params["path_length"]
        return values

    def _read(self) -> LightReading:
        reading = self.device("sensor").read_light(self.params["samples"])
        if reading.saturated:
            raise ExperimentError(_("The sensor is saturated: lower the LED power (or the gain) and measure again."))
        return reading

    # ── operations ──
    @action(N_("Measure blank"), help=N_("The solvent alone: the zero of the absorbance scale."))
    def measure_blank(self) -> float:
        reading = self._read()
        if reading.lux <= 0:
            raise ExperimentError(_("No light reaches the sensor. Turn the LED on, or raise its power."))
        self.blank = reading.lux
        results = self.session.results
        results["blank_lux"] = reading.lux
        results["conditions"] = self.conditions()
        rows = self.standards.rows()
        blank_row = next((i for i, r in enumerate(rows) if r["c"] == 0), None)
        if blank_row is None:
            self.standards.append(c=0.0, lux=reading.lux, T=1.0, A=0.0)
        else:
            self.standards.update(blank_row, lux=reading.lux, T=1.0, A=0.0)
        # standards measured earlier are recomputed against the new blank
        for i, r in enumerate(self.standards.rows()):
            if r["c"] > 0 and math.isfinite(r["lux"]):
                self.standards.update(i, T=r["lux"] / reading.lux, A=absorbance(reading.lux, r["lux"]))
        self._refit()
        self.session.note(f"blank {reading.lux:.2f} lx")
        return reading.lux

    @action(N_("Measure standard"), help=N_("A solution of known concentration."))
    def measure_standard(self, concentration: float) -> dict[str, Any]:
        if self.blank is None:
            raise NotReady(_("Measure the blank first."))
        if not concentration > 0:
            raise ExperimentError(_("A standard needs a concentration above zero: the blank is the zero point."))
        reading = self._read()
        index = self.standards.append(c=float(concentration), lux=reading.lux, T=reading.lux / self.blank,
                                      A=absorbance(self.blank, reading.lux))
        self._refit()
        self.session.note(f"standard {concentration} {self.params['unit']}: {reading.lux:.2f} lx")
        return self.standards.row(index)

    @action(N_("Remove standard"))
    def remove_standard(self, index: int) -> None:
        if self.standards.row(index)["c"] == 0:
            raise ExperimentError(_("The blank stays in the table. Measure it again to replace it."))
        self.standards.remove(index)
        self._refit()

    @action(N_("Measure unknown"), help=N_("A sample of unknown concentration, measured against the calibration."))
    def measure_unknown(self, sample: str = "") -> Measured:
        if self.blank is None:
            raise NotReady(_("Measure the blank first."))
        if self.fit is None:
            raise NotReady(_("Measure at least two standards first."))
        reading = self._read()
        a = absorbance(self.blank, reading.lux)
        c = self.fit.inverse(a, unit=self.params["unit"])
        name = sample.strip() or f"#{len(self.unknowns) + 1}"
        self.unknowns.append(sample=name, lux=reading.lux, T=reading.lux / self.blank, A=a, c=c.value,
                             c_err=c.stderr)
        top = max((r["c"] for r in self.standards.rows()), default=0.0)
        if c.value > top * 1.05:
            self.session.note(f"{name} is above the highest standard: extrapolated")
        self.session.results["unknowns"] = self.unknowns.rows()
        self.session.note(f"unknown {name}: A={a:.4f} c={c}")
        return c

    def _refit(self) -> None:
        rows = [r for r in self.standards.rows() if math.isfinite(r["A"])]
        self.fit = None
        if len({r["c"] for r in rows}) >= 2:
            self.fit = linear_fit([r["c"] for r in rows], [r["A"] for r in rows],
                                  through_origin=self.params["through_origin"], x_unit=self.params["unit"])
        if self.fit is None:
            self.session.results.pop("fit", None)
        else:
            self.session.results["fit"] = self.fit.to_dict()
            self.session.results["formula"] = self.fit.formula("c", "A")

    # ── calibrations ──
    def calibration(self) -> Calibration:
        if self.fit is None:
            raise NotReady(_("Measure at least two standards first."))
        sensor = self.devices.get("sensor")
        board = getattr(sensor, "board", None)
        device = {"plugin": getattr(sensor, "id", ""), "serial": getattr(board, "serial", ""),
                  "name": getattr(board, "name", "")}
        points = [[r["c"], r["A"]] for r in self.standards.rows() if math.isfinite(r["A"])]
        label = self.params["solution"] or _("Calibration")
        return Calibration(KIND, label, self.fit.to_dict(), points, self.conditions(), device,
                           {"x": self.params["unit"], "y": ""})

    @action(N_("Save calibration"), help=N_("Keep this calibration to reuse it on another day."))
    def save_calibration(self, label: str = "") -> Path:
        if self.calibrations is None:
            raise NotReady(_("No calibration library is available."))
        cal = self.calibration()
        if label.strip():
            cal.label = label.strip()
        path = self.calibrations.save(cal)
        self.session.calibrations.append(cal.to_dict())
        self.session.note(f"calibration saved: {cal.label}")
        return path

    def apply_calibration(self, cal: Calibration) -> dict[str, tuple[Any, Any]]:
        """Use a saved calibration: set its conditions (colour before power), load its line and points.

        Returns what differed before applying. The blank must still be measured: I₀ depends on the day.
        """
        before = cal.differences(self.conditions())
        for role, keys in (("source", ("led_color", "led_power")), ("sensor", ("integration_time", "gain"))):
            dev = self.devices.get(role)
            for key in keys:
                if dev is not None and key in cal.conditions:
                    dev.set_parameter(key, cal.conditions[key])
        if cal.units.get("x") in UNITS:
            super().set_parameter("unit", cal.units["x"])
        if "path_length_cm" in cal.conditions:
            super().set_parameter("path_length", cal.conditions["path_length_cm"])
        self.standards.clear()
        for c, a in cal.points:
            self.standards.append(c=c, A=a)
        self.fit = cal.linear_fit()
        self.blank = None
        self.session.results.pop("blank_lux", None)
        self.session.results["fit"] = self.fit.to_dict()
        self.session.calibrations.append(cal.to_dict())
        self.session.note(f"calibration applied: {cal.label}")
        self.changed.emit()
        return before

    # ── what the views show ──
    def count_standards(self) -> int:
        return sum(1 for r in self.standards.rows() if r["c"] > 0)

    def epsilon(self) -> Measured | None:
        if self.fit is None:
            return None
        unit = self.params["unit"]
        per = "L·mol⁻¹·cm⁻¹" if unit == "mol/L" else f"({unit})⁻¹·cm⁻¹"
        path = self.params["path_length"]
        return Measured(self.fit.slope.value / path, self.fit.slope.stderr / path, per)

    def check_light(self, live: dict[str, float]) -> str | None:
        if not live:
            return _("Waiting for a reading…")
        if live.get("saturated"):
            return _("The sensor is saturated: lower the LED power.")
        if live.get("ch0", 0) < 200:
            return _("Too little light: turn the LED on or raise its power.")
        return None

    def blank_text(self) -> str:
        return _("Blank: I₀ = {lux:.1f} lx").format(lux=self.blank) if self.blank is not None else ""

    def fit_text(self) -> str:
        if self.fit is None:
            return _("The calibration line appears after the blank and one standard.")
        text = f"{self.fit.formula('c', 'A')}   ·   R² = {self.fit.r2:.4f}"
        eps = self.epsilon()
        if eps is not None and math.isfinite(eps.stderr):
            text += f"   ·   ε = {eps}"
        return text

    def unknown_text(self) -> str:
        if not len(self.unknowns):
            return self.fit_text()
        last = self.unknowns.row(len(self.unknowns) - 1)
        c = Measured(last["c"], last["c_err"], self.params["unit"])
        return _("{sample}: c = {c}").format(sample=last["sample"], c=c)

    def plot_calibration(self) -> PlotData:
        unit = self.params["unit"]
        standards = [(r["c"], r["A"]) for r in self.standards.rows() if math.isfinite(r["A"])]
        series = [Series(N_("Standards"), standards, "points", "a")]
        top = max((c for c, _a in standards), default=0.0)
        unknowns = [(r["c"], r["A"]) for r in self.unknowns.rows()]
        top = max([top, *(c for c, _a in unknowns)]) if unknowns else top
        if self.fit is not None and top > 0:
            series.append(Series(N_("Calibration line"), [(0.0, float(self.fit.predict(0.0))),
                                                          (top * 1.1, float(self.fit.predict(top * 1.1)))],
                                 "line", "fit"))
        if unknowns:
            series.append(Series(N_("Unknown samples"), unknowns, "points", "x"))
        return PlotData(f"c ({unit})", "A", series)

    def summary(self) -> list[tuple[str, str]]:
        out = []
        if self.blank is not None:
            out.append((_("Blank"), f"I₀ = {self.blank:.1f} lx"))
        if self.fit is not None:
            out.append((_("Calibration"), self.fit.formula("c", "A")))
            out.append(("R²", f"{self.fit.r2:.4f}"))
            eps = self.epsilon()
            if eps is not None:
                out.append((_("Molar absorptivity ε") if self.params["unit"] == "mol/L" else _("Absorptivity"),
                            str(eps)))
        out.append((_("Standards"), str(self.count_standards())))
        for r in self.unknowns.rows():
            out.append((str(r["sample"]), str(Measured(r["c"], r["c_err"], self.params["unit"]))))
        return out

    def wizard(self) -> list[Step]:
        return [
            DevicesStep(N_("Devices"), N_("Choose the photometer. It provides both the light sensor and the "
                                          "light source.")),
            ParametersStep(N_("Light setup"), N_("With the cuvette holder empty, choose the fitted LED and a power "
                                                 "that gives a strong reading without saturating the sensor."),
                           role="source", keys=("led_color", "led_power", "integration_time"),
                           experiment_keys=("solution", "unit", "samples"), check="check_light"),
            InstructionStep(N_("Prepare the blank"), N_("Fill a clean cuvette with the solvent (usually distilled "
                                                        "water), dry the outside, and insert it with the clear faces "
                                                        "towards the light.")),
            ActionStep(N_("Measure the blank"), N_("The blank is the zero of the scale: every absorbance is "
                                                   "measured against it."),
                       action="measure_blank", button=N_("Measure blank"), result="blank_text"),
            TableStep(N_("Standard solutions"), N_("Rinse the cuvette with the next standard, fill it and insert "
                                                   "it. Type its concentration, then press Measure. At least 3 "
                                                   "standards; 5 are better."),
                      dataset="standards", input_label=N_("Concentration"), input_unit_parameter="unit",
                      row_action="measure_standard", button=N_("Measure"), remove_action="remove_standard",
                      plot="plot_calibration", count="count_standards", min_rows=3, summary="fit_text"),
            TableStep(N_("Unknown sample"), N_("Fill the cuvette with the unknown solution, type a name for it, "
                                               "and press Measure."),
                      dataset="unknowns", input_label=N_("Sample name"), input_kind="text",
                      row_action="measure_unknown", button=N_("Measure"), plot="plot_calibration", min_rows=1,
                      summary="unknown_text"),
            ResultStep(N_("Results"), N_("Save the session to keep the data. Save the calibration to reuse it on "
                                         "another day with the same LED and settings.")),
        ]

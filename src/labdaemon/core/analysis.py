"""Fits with uncertainties. M1: straight lines (Beer–Lambert); non-linear models arrive with scipy in M2."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from labdaemon.core.errors import ExperimentError
from labdaemon.core.i18n import _


def ratio_unit(numerator: str, denominator: str) -> str:
    """The unit of numerator/denominator: ("", "mol/L") → "L/mol", ("V", "mm") → "V/mm"."""
    if not denominator:
        return numerator
    if "/" in denominator and denominator.count("/") == 1:
        top, bottom = denominator.split("/")
        inverse = f"{bottom}/{top}"
        return f"{numerator}·{inverse}" if numerator else inverse
    return f"{numerator or '1'}/{denominator}"


@dataclass(frozen=True)
class Measured:
    """A value with its standard uncertainty, printed the way a lab report writes it: 6.79 ± 0.07 L/mol."""

    value: float
    stderr: float = math.nan
    unit: str = ""

    def rounded(self) -> tuple[str, str]:
        """Value and uncertainty as text, the uncertainty to 2 significant figures and the value to match."""
        if not math.isfinite(self.stderr) or self.stderr <= 0:
            return f"{self.value:.4g}", ""
        decimals = max(0, 1 - math.floor(math.log10(self.stderr)))
        return f"{self.value:.{decimals}f}", f"{self.stderr:.{decimals}f}"

    def __str__(self) -> str:
        value, err = self.rounded()
        text = f"{value} ± {err}" if err else value
        return f"{text} {self.unit}".strip()


@dataclass(frozen=True)
class LinearFit:
    """y = slope·x + intercept, ordinary least squares, with the statistics needed for predictions."""

    slope: Measured
    intercept: Measured
    r2: float
    n: int
    through_origin: bool
    s: float  # residual standard deviation
    x_mean: float
    y_mean: float
    sxx: float  # Σ(x − x̄)² (or Σx² through the origin)

    def predict(self, x: float | np.ndarray) -> float | np.ndarray:
        return self.slope.value * np.asarray(x) + self.intercept.value

    def inverse(self, y: float, replicates: int = 1, unit: str = "") -> Measured:
        """x for a measured y (a concentration from an absorbance), with the calibration uncertainty.

        s_x = s/|m| · √(1/k + 1/n + (y − ȳ)² / (m² Σ(x − x̄)²)), k = replicate readings of the unknown.
        """
        m = self.slope.value
        if m == 0:
            raise ExperimentError(_("The calibration line is flat: it cannot give a concentration."))
        x = (y - self.intercept.value) / m
        if self.n <= 2 or not math.isfinite(self.s):
            return Measured(x, math.nan, unit)
        if self.through_origin:
            err = self.s / abs(m) * math.sqrt(1 / replicates + x * x * m * m / (m * m * self.sxx))
        else:
            err = self.s / abs(m) * math.sqrt(1 / replicates + 1 / self.n
                                              + (y - self.y_mean) ** 2 / (m * m * self.sxx))
        return Measured(x, err, unit)

    def formula(self, x: str = "x", y: str = "y") -> str:
        slope, _err = self.slope.rounded()
        if self.through_origin:
            return f"{y} = {slope}·{x}"
        q = self.intercept.value
        q_text, _err = Measured(abs(q), self.intercept.stderr).rounded()
        return f"{y} = {slope}·{x} {'−' if q < 0 else '+'} {q_text}"

    def to_dict(self) -> dict:
        return {"slope": self.slope.value, "slope_err": self.slope.stderr, "intercept": self.intercept.value,
                "intercept_err": self.intercept.stderr, "r2": self.r2, "n": self.n,
                "through_origin": self.through_origin, "s": self.s, "x_mean": self.x_mean, "y_mean": self.y_mean,
                "sxx": self.sxx}

    @classmethod
    def from_dict(cls, d: dict, x_unit: str = "", y_unit: str = "") -> LinearFit:
        per = ratio_unit(y_unit, x_unit)
        return cls(Measured(d["slope"], d.get("slope_err", math.nan), per),
                   Measured(d["intercept"], d.get("intercept_err", math.nan), y_unit), d.get("r2", math.nan),
                   int(d["n"]), bool(d.get("through_origin", False)), d.get("s", math.nan), d.get("x_mean", 0.0),
                   d.get("y_mean", 0.0), d.get("sxx", math.nan))


def linear_fit(x: Sequence[float], y: Sequence[float], *, through_origin: bool = False,
               x_unit: str = "", y_unit: str = "") -> LinearFit:
    xs = np.asarray(x, dtype=float)
    ys = np.asarray(y, dtype=float)
    ok = np.isfinite(xs) & np.isfinite(ys)
    xs, ys = xs[ok], ys[ok]
    n = len(xs)
    needed = 1 if through_origin else 2
    if n < needed or np.ptp(xs) == 0 and not through_origin:
        raise ExperimentError(_("At least two points with different values are needed for a line."))
    per = ratio_unit(y_unit, x_unit)
    if through_origin:
        sxx = float(np.sum(xs * xs))
        if sxx == 0:
            raise ExperimentError(_("At least one point away from zero is needed for a line through the origin."))
        m = float(np.sum(xs * ys) / sxx)
        q = 0.0
        dof = n - 1
    else:
        x_mean = float(xs.mean())
        sxx = float(np.sum((xs - x_mean) ** 2))
        m = float(np.sum((xs - x_mean) * (ys - ys.mean())) / sxx)
        q = float(ys.mean() - m * x_mean)
        dof = n - 2
    residuals = ys - (m * xs + q)
    ssr = float(np.sum(residuals ** 2))
    sst = float(np.sum((ys - ys.mean()) ** 2))
    r2 = 1 - ssr / sst if sst > 0 else math.nan
    s = math.sqrt(ssr / dof) if dof > 0 else math.nan
    if through_origin:
        m_err, q_err = s / math.sqrt(sxx), 0.0
    else:
        m_err = s / math.sqrt(sxx)
        q_err = s * math.sqrt(1 / n + float(xs.mean()) ** 2 / sxx)
    return LinearFit(Measured(m, m_err, per), Measured(q, q_err, y_unit), r2, n, through_origin, s,
                     float(xs.mean()), float(ys.mean()), sxx)


def absorbance(reference: float, sample: float) -> float:
    """A = log10(I0 / I). Raises a clear error instead of a math domain error when there is no light."""
    if reference <= 0:
        raise ExperimentError(_("The reference (blank) reading has no light. Raise the LED power and measure the "
                                "blank again."))
    if sample <= 0:
        raise ExperimentError(_("No light reached the sensor through the sample. Raise the LED power, or dilute "
                                "the sample."))
    return math.log10(reference / sample)

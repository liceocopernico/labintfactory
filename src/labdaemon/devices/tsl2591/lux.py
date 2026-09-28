"""TSL2591 figures and the lux calculation. The figures come from the plugin's hardware sheet."""

from pathlib import Path

from labdaemon.core.hardware import HardwareSheet, load_sheet

SHEET_PATH = Path(__file__).resolve().parent / "hardware" / "hardware.toml"


def sheet() -> HardwareSheet:
    return load_sheet(SHEET_PATH)


INTEGRATION_MS = tuple(sheet().spec("tsl2591", "integration_ms"))
GAINS = tuple(sheet().spec("tsl2591", "gains"))
LUX_DF = float(sheet().spec("tsl2591", "lux_df"))


def full_scale_counts(integration_ms: int) -> int:
    table = sheet().spec("tsl2591", "full_scale_counts")
    return int(table.get(str(integration_ms), table["default"]))


def counts_per_lux(integration_ms: int, gain: int) -> float:
    """CPL in the lux formula: counts per lux for the given settings."""
    return integration_ms * gain / LUX_DF


def lux(ch0: float, ch1: float, integration_ms: int, gain: int) -> float:
    """Illuminance from the full-spectrum (ch0) and infrared (ch1) counts.

    lux = (ch0 − ch1) · (1 − ch1/ch0) / CPL. No light (ch0 = 0) is a valid reading of 0 lx.
    """
    if ch0 <= 0:
        return 0.0
    return max(0.0, (ch0 - ch1) * (1.0 - ch1 / ch0) / counts_per_lux(integration_ms, gain))

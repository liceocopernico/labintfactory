"""TSL2591 figures and the lux calculation.

In M1 these figures move into the plugin's hardware sheet (hardware/hardware.toml, design §7.4),
which the GUI shows and this code reads.
"""

INTEGRATION_MS = (100, 200, 300, 400, 500, 600)
GAINS = (1, 25, 428, 9876)  # nominal factors: low, medium, high, max
LUX_DF = 408.0  # device factor used by the lux formula

# Full-scale counts per channel. At 100 ms the ADC tops out lower than at longer integration times
# (value from Adafruit's TSL2591 driver; to be confirmed against the ams datasheet in M1).
FULL_SCALE_100MS = 36863
FULL_SCALE = 65535


def full_scale_counts(integration_ms: int) -> int:
    return FULL_SCALE_100MS if integration_ms <= 100 else FULL_SCALE


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

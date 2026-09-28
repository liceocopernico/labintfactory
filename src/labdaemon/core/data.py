"""Measured quantities. Datasets and sessions arrive in M1; M0 needs only channels."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    key: str  # "lux"
    label: str  # English source text (N_)
    unit: str  # symbols ("lx", "mT") are shown as they are; words ("counts") are marked with N_()

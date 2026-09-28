"""Declarative wizard steps (design §6). Pure data: the GUI renders them, the experiment says when each is done."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    title: str  # N_()
    text: str = ""  # N_(): what to do, in a sentence or two


@dataclass(frozen=True)
class DevicesStep(Step):
    """Choose a device for every role the experiment requires. Done when all required roles are filled."""


@dataclass(frozen=True)
class ParametersStep(Step):
    """Settings of one device (and of the experiment), with its live reading.

    `check` names an experiment method: (live values) -> None when fine, or a message saying what to change.
    """

    role: str = ""
    keys: tuple[str, ...] = ()  # device parameters to show
    experiment_keys: tuple[str, ...] = ()  # experiment parameters to show
    check: str | None = None


@dataclass(frozen=True)
class InstructionStep(Step):
    """Something to do by hand (fill a cuvette …). Done when the user moves on."""

    image: str | None = None


@dataclass(frozen=True)
class ActionStep(Step):
    """One button that runs an @action. Done once the action has succeeded."""

    action: str = ""
    button: str = ""  # N_()
    result: str | None = None  # experiment method: () -> text describing the result


@dataclass(frozen=True)
class TableStep(Step):
    """Type a value, press the button: the row action runs with it and adds a row to the dataset."""

    dataset: str = ""
    input_label: str = ""  # N_()
    input_unit_parameter: str | None = None  # experiment parameter holding the unit of the input
    input_kind: str = "float"  # float | text
    row_action: str = ""
    button: str = ""  # N_()
    remove_action: str | None = None  # experiment method taking a row index
    plot: str | None = None  # experiment method: () -> PlotData
    count: str | None = None  # experiment method: () -> rows that count towards min_rows
    min_rows: int = 1
    summary: str | None = None  # experiment method: () -> text under the plot


@dataclass(frozen=True)
class ResultStep(Step):
    """Results and saving. `summary` names an experiment method: () -> [(label, text), …]."""

    summary: str = "summary"

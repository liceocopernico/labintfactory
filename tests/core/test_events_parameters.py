import pytest

from labdaemon.core.errors import ParameterError
from labdaemon.core.events import Signal
from labdaemon.core.parameters import Parameter, ParameterSet


def test_signal_delivers_to_all_even_if_one_fails():
    s = Signal("t")
    got = []
    s.connect(lambda x: 1 / 0)
    s.connect(got.append)
    s.emit(5)
    assert got == [5]
    s.disconnect(got.append)
    s.emit(6)
    assert got == [5]


def test_validation_converts_and_rejects():
    p = Parameter("n", "Samples", int, 1, minimum=1, maximum=15)
    assert p.validate("3") == 3
    with pytest.raises(ParameterError, match="outside 1–15"):
        p.validate(16)
    with pytest.raises(ParameterError, match="not a valid value"):
        p.validate(2.5)
    f = Parameter("x", "Length", float, 1.0, unit="cm")
    assert f.validate("1,5") == 1.5  # Italian decimal comma accepted
    c = Parameter("c", "Colour", str, "red", choices=("red", "blue"))
    with pytest.raises(ParameterError, match="choose one of red, blue"):
        c.validate("green")
    b = Parameter("b", "On", bool, False)
    assert b.validate("yes") is True and b.validate(0) is False


def test_fit_brings_dependent_values_into_range():
    p = Parameter("power", "Power", int, 780, minimum=780, maximum=850)
    assert p.fit(1850) == 850 and p.fit(100) == 780 and p.fit(800) == 800
    assert Parameter("c", "C", str, "red", choices=("red",)).fit("x") == "red"


def test_parameter_set_reports_changes():
    ps = ParameterSet([Parameter("a", "A", int, 1)])
    events = []
    ps.changed.connect(lambda values, defs: events.append((values, defs)))
    ps.replace([Parameter("a", "A", int, 1)], {"a": 2})
    ps.replace([Parameter("a", "A", int, 1)], {"a": 2})  # no change, no event
    ps.replace([Parameter("a", "A", int, 1, maximum=5)], {"a": 2})
    assert events == [({"a": 2}, False), ({"a": 2}, True)]
    with pytest.raises(ParameterError):
        ps.definition("zzz")

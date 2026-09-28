"""A form generated from Parameter definitions. It shows values; the device's ParameterSet owns them."""

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from labdaemon.core.i18n import _
from labdaemon.core.parameters import Parameter

_WIDE = 2_000_000_000


class ParameterForm(QWidget):
    edited = Signal(str, object)  # key, new value (not yet validated or applied)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._defs: tuple[Parameter, ...] = ()
        self._editors: dict[str, QWidget] = {}

    def set_parameters(self, definitions: Sequence[Parameter], values: dict[str, Any]) -> None:
        defs = tuple(definitions)
        if defs != self._defs:
            self._rebuild(defs)
        for p in defs:
            self._show(p, values.get(p.key, p.default))

    def _rebuild(self, defs: tuple[Parameter, ...]) -> None:
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._editors.clear()
        self._defs = defs
        for p in defs:
            editor = self._editor_for(p)
            label = QLabel(_(p.label) + (" " + self.tr("(advanced)") if p.advanced else ""))
            if p.help:
                label.setToolTip(_(p.help))
                editor.setToolTip(_(p.help))
            self._editors[p.key] = editor
            self._layout.addRow(label, editor)

    def _editor_for(self, p: Parameter) -> QWidget:
        key = p.key
        if p.choices is not None:
            w = QComboBox()
            for c in p.choices:
                w.addItem(_(str(c)) + (f" {p.unit}" if p.unit else ""), c)
            w.activated.connect(lambda i, w=w: self.edited.emit(key, w.itemData(i)))
            return w
        if p.type is bool:
            w = QCheckBox()
            w.toggled.connect(lambda v: self.edited.emit(key, v))
            return w
        if p.type is int:
            w = QSpinBox()
            w.setRange(int(p.minimum if p.minimum is not None else -_WIDE),
                       int(p.maximum if p.maximum is not None else _WIDE))
            w.setSingleStep(int(p.step or 1))
            w.setKeyboardTracking(False)  # one edit when the user is done, not one per keystroke
            if p.unit:
                w.setSuffix(f" {p.unit}")
            w.valueChanged.connect(lambda v: self.edited.emit(key, v))
            return w
        if p.type is float:
            w = QDoubleSpinBox()
            w.setDecimals(3)
            w.setRange(p.minimum if p.minimum is not None else -1e12, p.maximum if p.maximum is not None else 1e12)
            w.setSingleStep(p.step or 0.1)
            w.setKeyboardTracking(False)
            if p.unit:
                w.setSuffix(f" {p.unit}")
            w.valueChanged.connect(lambda v: self.edited.emit(key, v))
            return w
        w = QLineEdit()
        w.editingFinished.connect(lambda w=w: self.edited.emit(key, w.text()))
        return w

    def _show(self, p: Parameter, value: Any) -> None:
        w = self._editors[p.key]
        w.blockSignals(True)
        try:
            if isinstance(w, QComboBox):
                w.setCurrentIndex(max(0, w.findData(value)))
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(value))
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.setValue(value)
            elif isinstance(w, QLineEdit):
                w.setText(str(value))
        finally:
            w.blockSignals(False)

    def set_editable(self, editable: bool) -> None:
        for w in self._editors.values():
            w.setEnabled(editable)

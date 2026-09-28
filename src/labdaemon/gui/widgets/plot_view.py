"""Draws an experiment's PlotData with pyqtgraph, in the theme's colours."""

import pyqtgraph as pg
from PySide6.QtWidgets import QWidget

from labdaemon.core.experiment import PlotData
from labdaemon.core.i18n import _
from labdaemon.gui import theme


class PlotView(pg.PlotWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.showGrid(x=True, y=True, alpha=0.25)
        self._legend = self.addLegend(offset=(10, 10))
        self._data: PlotData | None = None
        for axis in ("left", "bottom"):
            self.getAxis(axis).enableAutoSIPrefix(False)  # "(x0.001)" on the axes confuses students
        theme.on_change(self._restyle)

    def _restyle(self) -> None:
        theme.style_plot(self)
        if self._data is not None:
            self.show_data(self._data)

    def show_data(self, data: PlotData) -> None:
        self._data = data
        self.clear()
        self._legend.clear()
        t = theme.tokens()
        self.setLabel("bottom", data.x_label)
        self.setLabel("left", data.y_label)
        for s in data.series:
            color = t.series.get(s.color, t.series["a"])
            xs = [p[0] for p in s.points]
            ys = [p[1] for p in s.points]
            if s.kind == "line":
                self.plot(xs, ys, pen=pg.mkPen(color, width=2, style=pg.QtCore.Qt.PenStyle.DashLine), name=_(s.label))
            else:
                self.plot(xs, ys, pen=None, symbol="o", symbolSize=9, symbolBrush=color, symbolPen=color,
                          name=_(s.label))
        self.enableAutoRange()

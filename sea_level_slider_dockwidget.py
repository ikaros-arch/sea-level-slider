# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel, QSlider

MIN_LEVEL_M = 1
MAX_LEVEL_M = 220


class SeaLevelSliderDockWidget(QDockWidget):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Sea Level Slider", parent)

        widget = QWidget()
        layout = QVBoxLayout()

        self.label = QLabel(f"Water level: {MIN_LEVEL_M} m")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(MIN_LEVEL_M)
        self.slider.setMaximum(MAX_LEVEL_M)
        self.slider.setValue(MIN_LEVEL_M)
        self.slider.valueChanged.connect(self._on_value_changed)

        layout.addWidget(self.label)
        layout.addWidget(self.slider)
        widget.setLayout(layout)
        self.setWidget(widget)

    def _on_value_changed(self, value):
        self.label.setText(f"Water level: {value} m")
        # TODO: reclassify/polygonize the active DEM at this level and update the
        # map layer, once the precompute-vs-on-the-fly approach is decided.

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

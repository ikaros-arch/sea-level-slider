# -*- coding: utf-8 -*-
import math

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .raster_styling import WaterLevelStyler, compute_band_min_max

NO_LAYER_MESSAGE = "Add a raster DEM layer to the project to begin."
# No point on Earth's land surface is outside this range; a selected band reporting
# values beyond it is not elevation data (e.g. a basemap raster, or an unset-nodata
# sentinel such as float32's +-3.4e38 leaking into the statistics).
PLAUSIBLE_ELEVATION_RANGE_M = 20000
DEFAULT_WATER_OPACITY_PERCENT = 60
DEFAULT_LAND_OPACITY_PERCENT = 0


class SeaLevelSliderDockWidget(QDockWidget):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Sea Level Slider", parent)
        self.styler = None

        widget = QWidget()
        layout = QVBoxLayout()

        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        self.layer_combo.layerChanged.connect(self._on_layer_changed)

        self.band_combo = QComboBox()
        self.band_combo.currentIndexChanged.connect(self._on_band_changed)

        self.range_label = QLabel("DEM range: -")

        self.min_spin = QDoubleSpinBox()
        self.max_spin = QDoubleSpinBox()
        for spin in (self.min_spin, self.max_spin):
            spin.setDecimals(1)
            spin.setRange(-PLAUSIBLE_ELEVATION_RANGE_M, PLAUSIBLE_ELEVATION_RANGE_M)
            spin.editingFinished.connect(self._on_range_override_changed)
        range_row = QHBoxLayout()
        range_row.addWidget(self.min_spin)
        range_row.addWidget(QLabel("to"))
        range_row.addWidget(self.max_spin)

        self.water_opacity_spin = QSpinBox()
        self.land_opacity_spin = QSpinBox()
        for spin, default in (
            (self.water_opacity_spin, DEFAULT_WATER_OPACITY_PERCENT),
            (self.land_opacity_spin, DEFAULT_LAND_OPACITY_PERCENT),
        ):
            spin.setRange(0, 100)
            spin.setSuffix("%")
            spin.setValue(default)
            # self.styler is None at this point, so the initial setValue's
            # valueChanged -> _apply_styling is a no-op (see the None check there).
            spin.valueChanged.connect(self._apply_styling)

        form = QFormLayout()
        form.addRow("DEM layer:", self.layer_combo)
        form.addRow("Band:", self.band_combo)
        form.addRow("DEM range:", self.range_label)
        form.addRow("Level range override:", range_row)
        form.addRow("Water opacity:", self.water_opacity_spin)
        form.addRow("Land opacity:", self.land_opacity_spin)
        layout.addLayout(form)

        self.level_label = QLabel("Water level: - m")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.level_label)
        layout.addWidget(self.slider)

        self.status_label = QLabel(NO_LAYER_MESSAGE)
        layout.addWidget(self.status_label)

        widget.setLayout(layout)
        self.setWidget(widget)

        self._set_controls_enabled(False)
        self._on_layer_changed(self.layer_combo.currentLayer())

    def _set_controls_enabled(self, enabled):
        controls = (
            self.band_combo,
            self.min_spin,
            self.max_spin,
            self.water_opacity_spin,
            self.land_opacity_spin,
            self.slider,
        )
        for widget in controls:
            widget.setEnabled(enabled)

    def _on_layer_changed(self, layer):
        self.styler = None
        if layer is None:
            self._set_controls_enabled(False)
            self.range_label.setText("DEM range: -")
            self.level_label.setText("Water level: - m")
            self.status_label.setText(NO_LAYER_MESSAGE)
            return

        self.band_combo.blockSignals(True)
        self.band_combo.clear()
        for band in range(1, layer.bandCount() + 1):
            self.band_combo.addItem(f"Band {band}", band)
        self.band_combo.blockSignals(False)
        self.band_combo.setEnabled(layer.bandCount() > 1)

        self._recompute_stats()

    def _on_band_changed(self, _index):
        self._recompute_stats()

    def _recompute_stats(self):
        self.styler = None
        layer = self.layer_combo.currentLayer()
        if layer is None:
            return
        band = self.band_combo.currentData() or 1

        self.status_label.setText("Computing DEM statistics...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            dem_min, dem_max = compute_band_min_max(layer, band)
        except Exception:
            # Layer removed/invalidated mid-computation, or a provider that doesn't
            # support real statistics (e.g. a WMS/XYZ basemap) - never let this
            # propagate as an unhandled exception out of a Qt signal handler.
            self._set_controls_enabled(False)
            self.range_label.setText("DEM range: -")
            self.status_label.setText("Could not read statistics for this layer/band.")
            return
        finally:
            QApplication.restoreOverrideCursor()

        if (
            not (math.isfinite(dem_min) and math.isfinite(dem_max))
            or abs(dem_min) > PLAUSIBLE_ELEVATION_RANGE_M
            or abs(dem_max) > PLAUSIBLE_ELEVATION_RANGE_M
        ):
            self._set_controls_enabled(False)
            self.range_label.setText("DEM range: -")
            self.status_label.setText(
                "Selected layer/band doesn't look like elevation data "
                "(unexpected value range) - pick a DEM layer."
            )
            return

        self.range_label.setText(f"DEM range: {dem_min:.1f} m to {dem_max:.1f} m")

        for spin, value in ((self.min_spin, dem_min), (self.max_spin, dem_max)):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

        self._apply_range_to_slider(dem_min, dem_max)
        self.styler = WaterLevelStyler(layer, band)
        self._set_controls_enabled(True)
        self.status_label.setText("")
        self._apply_styling()

    def _on_range_override_changed(self):
        self._apply_range_to_slider(self.min_spin.value(), self.max_spin.value())

    def _apply_range_to_slider(self, level_min, level_max):
        level_min, level_max = round(level_min), round(level_max)
        current = self.slider.value()
        self.slider.setMinimum(level_min)
        self.slider.setMaximum(level_max)
        self.slider.setValue(min(max(current, level_min), level_max))

    def _on_value_changed(self, value):
        self.level_label.setText(f"Water level: {value} m")
        self._apply_styling()

    def _apply_styling(self, *_args):
        if self.styler is None:
            return
        water_alpha = round(self.water_opacity_spin.value() / 100 * 255)
        land_alpha = round(self.land_opacity_spin.value() / 100 * 255)
        self.styler.apply(self.slider.value(), water_alpha, land_alpha)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

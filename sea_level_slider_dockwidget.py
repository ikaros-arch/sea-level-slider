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
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .i18n import tr
from .raster_export import export_level_as_polygon
from .raster_styling import WaterLevelStyler, compute_band_min_max

NO_LAYER_MESSAGE = tr("Add a raster DEM layer to the project to begin.")
# No point on Earth's land surface is outside this range; a selected band reporting
# values beyond it is not elevation data (e.g. a basemap raster, or an unset-nodata
# sentinel such as float32's +-3.4e38 leaking into the statistics).
PLAUSIBLE_ELEVATION_RANGE_M = 20000
DEFAULT_WATER_OPACITY_PERCENT = 60
DEFAULT_LAND_OPACITY_PERCENT = 0
# Never default to a specific datum silently - the plugin can't detect a DEM's
# actual vertical reference, and getting this wrong undermines the whole point of
# exporting a polygon for archaeological analysis.
DEFAULT_METHOD_TEXT = tr("QGIS Sea Level Slider plugin (threshold: elevation <= water level)")
DEFAULT_SMOOTHING_ITERATIONS = 2
DEFAULT_MIN_ISLAND_PIXELS = 4


class SeaLevelSliderDockWidget(QDockWidget):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(tr("Sea Level Slider"), parent)
        self.styler = None

        widget = QWidget()
        layout = QVBoxLayout()

        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        self.layer_combo.layerChanged.connect(self._on_layer_changed)

        self.band_combo = QComboBox()
        self.band_combo.currentIndexChanged.connect(self._on_band_changed)

        self.range_label = QLabel(tr("DEM range: -"))

        self.min_spin = QDoubleSpinBox()
        self.max_spin = QDoubleSpinBox()
        for spin in (self.min_spin, self.max_spin):
            spin.setDecimals(1)
            spin.setRange(-PLAUSIBLE_ELEVATION_RANGE_M, PLAUSIBLE_ELEVATION_RANGE_M)
            spin.editingFinished.connect(self._on_range_override_changed)
        range_row = QHBoxLayout()
        range_row.addWidget(self.min_spin)
        range_row.addWidget(QLabel(tr("to")))
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
        form.addRow(tr("DEM layer:"), self.layer_combo)
        form.addRow(tr("Band:"), self.band_combo)
        form.addRow(tr("DEM range:"), self.range_label)
        form.addRow(tr("Level range override:"), range_row)
        form.addRow(tr("Water opacity:"), self.water_opacity_spin)
        form.addRow(tr("Land opacity:"), self.land_opacity_spin)
        layout.addLayout(form)

        self.level_label = QLabel(tr("Water level: - m"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.level_label)
        layout.addWidget(self.slider)

        self.datum_combo = QComboBox()
        self.datum_combo.setEditable(True)
        # Kept untranslated: this is also the literal value written to the
        # exported polygon's vertical_datum attribute, which should stay
        # consistent across sessions regardless of UI language.
        self.datum_combo.addItems(["Unknown", "NN2000", "NN1954"])
        self.method_edit = QLineEdit(DEFAULT_METHOD_TEXT)
        self.min_island_spin = QSpinBox()
        self.min_island_spin.setRange(0, 10000)
        self.min_island_spin.setValue(DEFAULT_MIN_ISLAND_PIXELS)
        self.min_island_spin.setToolTip(
            tr(
                "Merges pixel groups smaller than this (in pixels) into their largest "
                "neighbour before vectorizing - removes few-pixel 'islands'/'lakes' that "
                "are just DEM-resolution noise. 0 = keep every speck."
            )
        )
        self.simplify_spin = QDoubleSpinBox()
        self.simplify_spin.setDecimals(2)
        self.simplify_spin.setRange(0, 100000)
        self.simplify_spin.setToolTip(
            tr(
                "Douglas-Peucker simplification distance, in the layer's map units. "
                "Reduces the 'one node per pixel' vertex density and generalizes the "
                "boundary. 0 = no simplification. Defaults to one DEM pixel width."
            )
        )
        self.smoothing_spin = QSpinBox()
        self.smoothing_spin.setRange(0, 10)
        self.smoothing_spin.setValue(DEFAULT_SMOOTHING_ITERATIONS)
        self.smoothing_spin.setToolTip(
            tr(
                "Rounds off remaining corners after simplification (Chaikin cutting - "
                "adds vertices, doesn't reduce them). 0 = no rounding."
            )
        )

        export_form = QFormLayout()
        export_form.addRow(tr("Vertical datum:"), self.datum_combo)
        export_form.addRow(tr("Method:"), self.method_edit)
        export_form.addRow(tr("Min. island/lake size (px):"), self.min_island_spin)
        export_form.addRow(tr("Simplify tolerance:"), self.simplify_spin)
        export_form.addRow(tr("Smoothing:"), self.smoothing_spin)
        layout.addLayout(export_form)

        self.export_button = QPushButton(tr("Export level as polygon..."))
        self.export_button.clicked.connect(self._on_export_clicked)
        layout.addWidget(self.export_button)

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
            self.datum_combo,
            self.method_edit,
            self.min_island_spin,
            self.simplify_spin,
            self.smoothing_spin,
            self.export_button,
        )
        for widget in controls:
            widget.setEnabled(enabled)

    def release_styler(self):
        """Restore the currently-styled layer's original renderer, if any."""
        if self.styler is not None:
            self.styler.restore()
            self.styler = None

    def _on_layer_changed(self, layer):
        self.release_styler()
        if layer is None:
            self._set_controls_enabled(False)
            self.range_label.setText(tr("DEM range: -"))
            self.level_label.setText(tr("Water level: - m"))
            self.status_label.setText(NO_LAYER_MESSAGE)
            return

        self.band_combo.blockSignals(True)
        self.band_combo.clear()
        for band in range(1, layer.bandCount() + 1):
            self.band_combo.addItem(tr("Band {n}").format(n=band), band)
        self.band_combo.blockSignals(False)
        self.band_combo.setEnabled(layer.bandCount() > 1)

        self._recompute_stats()

    def _on_band_changed(self, _index):
        self._recompute_stats()

    def _recompute_stats(self):
        self.release_styler()
        layer = self.layer_combo.currentLayer()
        if layer is None:
            return
        band = self.band_combo.currentData() or 1

        self.status_label.setText(tr("Computing DEM statistics..."))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            dem_min, dem_max = compute_band_min_max(layer, band)
        except Exception:
            # Layer removed/invalidated mid-computation, or a provider that doesn't
            # support real statistics (e.g. a WMS/XYZ basemap) - never let this
            # propagate as an unhandled exception out of a Qt signal handler.
            self._set_controls_enabled(False)
            self.range_label.setText(tr("DEM range: -"))
            self.status_label.setText(tr("Could not read statistics for this layer/band."))
            return
        finally:
            QApplication.restoreOverrideCursor()

        if (
            not (math.isfinite(dem_min) and math.isfinite(dem_max))
            or abs(dem_min) > PLAUSIBLE_ELEVATION_RANGE_M
            or abs(dem_max) > PLAUSIBLE_ELEVATION_RANGE_M
        ):
            self._set_controls_enabled(False)
            self.range_label.setText(tr("DEM range: -"))
            self.status_label.setText(
                tr(
                    "Selected layer/band doesn't look like elevation data "
                    "(unexpected value range) - pick a DEM layer."
                )
            )
            return

        self.range_label.setText(
            tr("DEM range: {min} m to {max} m").format(min=f"{dem_min:.1f}", max=f"{dem_max:.1f}")
        )

        for spin, value in ((self.min_spin, dem_min), (self.max_spin, dem_max)):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

        self._apply_range_to_slider(dem_min, dem_max)
        self.simplify_spin.setValue(abs(layer.rasterUnitsPerPixelX()))
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
        self.level_label.setText(tr("Water level: {value} m").format(value=value))
        self._apply_styling()

    def _apply_styling(self, *_args):
        if self.styler is None:
            return
        water_alpha = round(self.water_opacity_spin.value() / 100 * 255)
        land_alpha = round(self.land_opacity_spin.value() / 100 * 255)
        self.styler.apply(self.slider.value(), water_alpha, land_alpha)

    def _on_export_clicked(self):
        layer = self.layer_combo.currentLayer()
        if layer is None or self.styler is None:
            return
        band = self.band_combo.currentData() or 1
        water_level = self.slider.value()
        vertical_datum = self.datum_combo.currentText()
        method = self.method_edit.text()
        smoothing = self.smoothing_spin.value()
        simplify_tolerance = self.simplify_spin.value()
        min_island_pixels = self.min_island_spin.value()

        self.export_button.setEnabled(False)
        self.status_label.setText(tr("Exporting polygon..."))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            export_level_as_polygon(
                layer,
                band,
                water_level,
                vertical_datum,
                method,
                smoothing,
                simplify_tolerance,
                min_island_pixels,
            )
        except Exception as exc:
            self.status_label.setText(tr("Export failed: {error}").format(error=exc))
        else:
            self.status_label.setText(tr("Exported submerged area at {level} m.").format(level=water_level))
        finally:
            QApplication.restoreOverrideCursor()
            self.export_button.setEnabled(True)

    def closeEvent(self, event):
        self.release_styler()
        self.closingPlugin.emit()
        event.accept()

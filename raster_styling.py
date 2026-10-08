# -*- coding: utf-8 -*-
from qgis.core import (
    Qgis,
    QgsColorRampShader,
    QgsRasterShader,
    QgsRectangle,
    QgsSingleBandPseudoColorRenderer,
)
from qgis.PyQt.QtGui import QColor

WATER_COLOR = QColor(30, 100, 200)
LAND_COLOR = QColor(0, 0, 0)


def compute_band_min_max(layer, band, sample_size=250000):
    """Return (min, max) for a raster band, sampled for speed on large DEMs."""
    provider = layer.dataProvider()
    stats = provider.bandStatistics(
        band,
        Qgis.RasterBandStatistic.Min | Qgis.RasterBandStatistic.Max,
        QgsRectangle(),
        sample_size,
    )
    return stats.minimumValue, stats.maximumValue


class WaterLevelStyler:
    """Owns the raster shader driving live water -level recoloring for one layer/band.

    Cells <= the water level are painted as "water"; cells above are painted as
    "land". Both are independently semi-transparent so other project layers (a
    basemap, a site inventory) remain visible underneath either class.
    """

    def __init__(self, layer, band):
        self.layer = layer
        self.band = band
        self._renderer = None
        self._shader_function = None
        # setRenderer() below takes ownership of (and deletes) the layer's current
        # renderer, so the original must be cloned now, before we ever touch it, or
        # restore() would later try to re-attach an already-deleted C++ object.
        old_renderer = layer.renderer()
        self._original_renderer = old_renderer.clone() if old_renderer is not None else None
        self._build_renderer()

    def _build_renderer(self):
        shader = QgsRasterShader()
        shader_function = QgsColorRampShader()
        shader_function.setColorRampType(QgsColorRampShader.Type.Discrete)
        shader_function.setColorRampItemList(
            [
                QgsColorRampShader.ColorRampItem(0, QColor(WATER_COLOR), "Below water level"),
                QgsColorRampShader.ColorRampItem(float("inf"), QColor(LAND_COLOR), "Above water level"),
            ]
        )
        shader.setRasterShaderFunction(shader_function)
        self._renderer = QgsSingleBandPseudoColorRenderer(self.layer.dataProvider(), self.band, shader)
        self.layer.setRenderer(self._renderer)
        self._shader_function = shader_function

    def apply(self, water_level, water_alpha, land_alpha):
        if self.layer.renderer() is not self._renderer:
            # Something else restyled this layer since we last touched it - rebuild.
            self._build_renderer()

        water_color = QColor(WATER_COLOR)
        water_color.setAlpha(water_alpha)
        land_color = QColor(LAND_COLOR)
        land_color.setAlpha(land_alpha)

        self._shader_function.setColorRampItemList(
            [
                QgsColorRampShader.ColorRampItem(water_level, water_color, "Below water level"),
                QgsColorRampShader.ColorRampItem(float("inf"), land_color, "Above water level"),
            ]
        )
        self.layer.triggerRepaint()

    def restore(self):
        """Put the layer back how it looked before this styler touched it."""
        try:
            if self._original_renderer is not None:
                self.layer.setRenderer(self._original_renderer)
                self._original_renderer = None  # ownership transferred to the layer
            self.layer.triggerRepaint()
        except RuntimeError:
            # The underlying layer was already deleted (e.g. removed from the
            # project) - nothing left to restore.
            pass

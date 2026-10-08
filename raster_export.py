# -*- coding: utf-8 -*-
import os
import tempfile
import uuid

import processing
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
from qgis.core import QgsField, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant


def _fix_geometries(vector_layer):
    """Repair self-intersections etc. before they reach a stricter downstream step
    (buffer/simplify/smooth can all occasionally produce invalid output).
    """
    result = processing.run("native:fixgeometries", {"INPUT": vector_layer, "OUTPUT": "memory:"})
    return result["OUTPUT"]


def _threshold_to_temp_raster(layer, band, water_level):
    """Write a 0/1 GeoTIFF (1 = elevation <= water_level) via QGIS's own raster
    calculator - an in-process PyQGIS API, not a GDAL command-line subprocess, so
    there's no intermediate "TEMPORARY_OUTPUT" path to go missing.
    """
    provider = layer.dataProvider()
    has_nodata = provider.sourceHasNoDataValue(band)
    nodata = provider.sourceNoDataValue(band) if has_nodata else None

    ref = f"{layer.name()}@{band}"
    entry = QgsRasterCalculatorEntry()
    entry.ref = ref
    entry.raster = layer
    entry.bandNumber = band

    if has_nodata:
        formula = f'("{ref}" <= {water_level}) * ("{ref}" != {nodata})'
    else:
        formula = f'("{ref}" <= {water_level})'

    output_path = os.path.join(tempfile.gettempdir(), f"sea_level_slider_{uuid.uuid4().hex}.tif")
    calc = QgsRasterCalculator(
        formula,
        output_path,
        "GTiff",
        layer.extent(),
        layer.crs(),
        layer.width(),
        layer.height(),
        [entry],
    )
    result = calc.processCalculation()
    if result != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"Raster calculation failed (error code {result}) while thresholding the DEM.")
    return output_path


def export_level_as_polygon(
    layer,
    band,
    water_level,
    vertical_datum,
    method,
    smoothing_iterations=0,
    simplify_tolerance=0,
    min_island_pixels=0,
):
    """Threshold the DEM at water_level and load the submerged area as a polygon layer.

    Only run on demand (button click), not on every slider tick - correctness over
    speed, unlike the live raster recolor in raster_styling.py.
    """
    threshold_path = _threshold_to_temp_raster(layer, band, water_level)
    try:
        polygonize_input = threshold_path
        sieved_path = None
        if min_island_pixels > 0:
            # Merge pixel groups smaller than this into their largest neighbour,
            # on the raster, before vectorizing - removes the few-pixel "islands"
            # and "lakes" that are just DEM-resolution noise, without leaving a
            # hole behind the way deleting a tiny post-polygonize feature would.
            sieve_result = processing.run(
                "gdal:sieve",
                {
                    "INPUT": threshold_path,
                    "THRESHOLD": min_island_pixels,
                    "EIGHT_CONNECTEDNESS": False,
                    "NO_MASK": True,
                    "MASK_LAYER": None,
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
            )
            sieved_path = sieve_result["OUTPUT"]
            polygonize_input = sieved_path

        try:
            polygonize_result = processing.run(
                "gdal:polygonize",
                {
                    "INPUT": polygonize_input,
                    "BAND": 1,
                    "FIELD": "submerged",
                    "EIGHT_CONNECTEDNESS": False,
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
            )
        finally:
            if sieved_path and os.path.exists(sieved_path):
                os.remove(sieved_path)
    finally:
        os.remove(threshold_path)

    polygon_layer = QgsVectorLayer(polygonize_result["OUTPUT"], "tmp_polygonize", "ogr")
    # The threshold raster has no nodata set (every cell is a real 0 or 1), so
    # polygonize returns both "dry" and "submerged" polygons - filter to the latter.
    polygon_layer.selectByExpression('"submerged" = 1')
    save_result = processing.run(
        "native:saveselectedfeatures",
        {"INPUT": polygon_layer, "OUTPUT": "memory:"},
    )
    final_layer = save_result["OUTPUT"]

    if simplify_tolerance > 0 or smoothing_iterations > 0:
        # The DEM's bounding box is an artificial cutoff, not a real coastline -
        # without this, simplify/smooth treat each bbox corner as a real feature
        # and round it off, eating into valid area at the edges. Buffer outward
        # first so that corner is pushed well clear of where we crop back to the
        # real extent afterward; only the genuine coastline ends up generalized.
        pixel_size = abs(layer.rasterUnitsPerPixelX())
        edge_padding = max(simplify_tolerance, pixel_size) * 10

        buffer_result = processing.run(
            "native:buffer",
            {
                "INPUT": final_layer,
                "DISTANCE": edge_padding,
                "SEGMENTS": 8,
                "END_CAP_STYLE": 0,  # Round
                "JOIN_STYLE": 0,  # Round
                "MITER_LIMIT": 2,
                "DISSOLVE": False,
                "OUTPUT": "memory:",
            },
        )
        final_layer = _fix_geometries(buffer_result["OUTPUT"])

        if simplify_tolerance > 0:
            # Douglas-Peucker: actually reduces vertex count and generalizes the
            # boundary (unlike smoothgeometry below, which rounds corners but adds
            # vertices) - this is what shrinks/cleans up the "one node per pixel" look.
            simplify_result = processing.run(
                "native:simplifygeometries",
                {
                    "INPUT": final_layer,
                    "METHOD": 0,  # Distance (Douglas-Peucker)
                    "TOLERANCE": simplify_tolerance,
                    "OUTPUT": "memory:",
                },
            )
            final_layer = _fix_geometries(simplify_result["OUTPUT"])

        if smoothing_iterations > 0:
            # Chaikin corner-cutting: rounds off the pixel-grid staircase edges that
            # gdal:polygonize always produces. Pure QGIS native algorithm, no subprocess.
            smooth_result = processing.run(
                "native:smoothgeometry",
                {
                    "INPUT": final_layer,
                    "ITERATIONS": smoothing_iterations,
                    "OFFSET": 0.25,
                    "MAX_ANGLE": 180,
                    "OUTPUT": "memory:",
                },
            )
            final_layer = _fix_geometries(smooth_result["OUTPUT"])

        # Crop the buffered-and-generalized shape back to the DEM's real extent,
        # restoring an exact boundary edge there instead of the rounded-off one.
        crop_result = processing.run(
            "native:extractbyextent",
            {
                "INPUT": final_layer,
                "EXTENT": layer,
                "CLIP": True,
                "OUTPUT": "memory:",
            },
        )
        final_layer = crop_result["OUTPUT"]

    final_layer.startEditing()
    final_layer.addAttribute(QgsField("water_level_m", QVariant.Double))
    final_layer.addAttribute(QgsField("vertical_datum", QVariant.String))
    final_layer.addAttribute(QgsField("method", QVariant.String))
    final_layer.updateFields()

    idx_level = final_layer.fields().indexOf("water_level_m")
    idx_datum = final_layer.fields().indexOf("vertical_datum")
    idx_method = final_layer.fields().indexOf("method")
    for feature in final_layer.getFeatures():
        final_layer.changeAttributeValue(feature.id(), idx_level, water_level)
        final_layer.changeAttributeValue(feature.id(), idx_datum, vertical_datum)
        final_layer.changeAttributeValue(feature.id(), idx_method, method)
    final_layer.commitChanges()

    final_layer.setName(f"Submerged area at {water_level} m")
    QgsProject.instance().addMapLayer(final_layer)
    return final_layer

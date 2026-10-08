# Sea Level Slider — QGIS Plugin

A QGIS plugin for interactively visualising historical and prehistoric sea levels
over a digital elevation model (DEM) — shoreline-displacement ("strandlinje")
modelling used in Norwegian archaeology to track land uplift since the last ice
age and predict where coastal/maritime sites are likely to be found.

- **Author:** Hallvard Indgjerd (KHM, University of Oslo) — hallvard.indgjerd@khm.uio.no
- **License:** GNU General Public License v3.0 (see [LICENSE](LICENSE))

## Origin

Ported from a working **ArcGIS Pro** script (arcpy) drafted by **Steinar Kristensen**
at the Museum of Cultural History (KHM), University of Oslo. The original script
thresholds a DEM against each water level from 1–220 m (`Con(dem <= level, 1)` +
`RasterToPolygon`) and merges the results into one feature class driving ArcGIS
Pro's Range Slider tool. This plugin reimplements that workflow for QGIS so it's
usable by the wider Norwegian archaeological community, most of whom work in QGIS
rather than licensed ArcGIS seats.

## Status

**Experimental / early scaffold.** The dock widget currently exposes a 1–220 m
slider with no raster logic wired up yet. Key open decisions (see the project
note in the author's knowledgebase) are:

- Porting approach for the raster logic (QGIS Processing chain vs. raw
  GDAL/rasterio/numpy).
- Precomputed polygon layer (one feature class, 220 levels, like the original)
  vs. on-the-fly raster reclassification per slider move.
- Vertical datum handling — the original assumes NN2000 (Norwegian height
  reference system); the plugin should surface/validate this rather than
  assume it silently.

## Development

```
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install flake8
flake8
```

Package a release zip for plugins.qgis.org with:

```
bash scripts/make_zip.sh
```

## License

GPL-3.0, as required for submission to the QGIS Plugin Repository. See
[LICENSE](LICENSE).

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

**Experimental.** First functional release (v0.1):

- Pick any loaded raster DEM layer (and band) from the dock widget. The slider
  range is read from the DEM's own elevation statistics.
- **Live visualisation:** moving the slider recolors the DEM in place — cells
  at or below the current level are painted as water, the rest as land — via
  a raster shader, not a precomputed vector layer like the original ArcGIS
  script (QGIS has no equivalent to ArcGIS Pro's Range Slider widget for
  that). Water and land opacity are independently adjustable so basemaps or
  other project layers (e.g. a site inventory) stay visible underneath.
- **On-demand polygon export:** a separate button thresholds and polygonizes
  the *current* level into a real vector layer, for spatial analysis (e.g.
  overlaying against known site locations) — this is a deliberately separate,
  slower operation from the live visualisation. Includes:
  - Raster sieve filtering to remove few-pixel "island"/"lake" noise from the
    DEM's resolution limit, before vectorizing (so no holes are left behind).
  - Douglas-Peucker simplification and optional Chaikin smoothing, with the
    polygon buffered outward beforehand and cropped back to the DEM's real
    extent afterward — without this, generalizing would treat the DEM's
    bounding box corners as real coastline and cut into valid area there.
  - Exported polygons carry `water_level_m`, `vertical_datum` and `method`
    attributes. **Vertical datum is never assumed** — the original ArcGIS
    script hardcodes NN2000, but this plugin always leaves it to the user
    (defaulting to "Unknown") since the plugin can't detect a DEM's actual
    reference from the raster alone.
- **UI language** follows the QGIS application's own locale setting
  (English/Norwegian Bokmål).

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

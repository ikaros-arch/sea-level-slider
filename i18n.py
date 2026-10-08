# -*- coding: utf-8 -*-
"""Minimal UI translation, following the QGIS application's own language setting.

QGIS ships the standard Qt Linguist (.ts/.qm) translation pipeline, but compiling
.ts files to .qm requires the `lrelease` tool, which isn't bundled with the QGIS
Windows installer and isn't a trivial pip install. This module is a plain-Python
substitute: a dict lookup keyed by the same locale QGIS itself uses
('locale/userLocale' in QSettings, e.g. "nb_NO"). English (the keys below) is
always the fallback for any language without an entry.
"""
from qgis.PyQt.QtCore import QSettings

TRANSLATIONS = {
    "nb": {
        "Sea Level Slider": "Havnivåsimulator",
        "&Sea Level Slider": "&Havnivåsimulator",
        "Add a raster DEM layer to the project to begin.": "Legg til et raster-DEM-lag i prosjektet for å starte.",
        "DEM range: -": "DEM-område: -",
        "DEM range: {min} m to {max} m": "DEM-område: {min} m til {max} m",
        "Water level: - m": "Vannstand: - m",
        "Water level: {value} m": "Vannstand: {value} m",
        "DEM layer:": "DEM-lag:",
        "Band:": "Bånd:",
        "DEM range:": "DEM-område:",
        "Level range override:": "Overstyr nivåområde:",
        "to": "til",
        "Water opacity:": "Gjennomsiktighet, vann:",
        "Land opacity:": "Gjennomsiktighet, land:",
        "Vertical datum:": "Vertikalt datum:",
        "Method:": "Metode:",
        "Min. island/lake size (px):": "Min. størrelse øy/innsjø (px):",
        "Simplify tolerance:": "Forenklingstoleranse:",
        "Smoothing:": "Utjevning:",
        "QGIS Sea Level Slider plugin (threshold: elevation <= water level)": (
            "QGIS Havnivåglidebryter-utvidelse (terskel: høyde <= vannstand)"
        ),
        "Merges pixel groups smaller than this (in pixels) into their largest "
        "neighbour before vectorizing - removes few-pixel 'islands'/'lakes' that "
        "are just DEM-resolution noise. 0 = keep every speck.": (
            "Slår sammen pikselgrupper mindre enn dette (i piksler) med sin "
            "største nabo før vektorisering - fjerner småpiksel-«øyer»/«innsjøer» "
            "som bare er støy fra DEM-oppløsningen. 0 = behold alle flekker."
        ),
        "Douglas-Peucker simplification distance, in the layer's map units. "
        "Reduces the 'one node per pixel' vertex density and generalizes the "
        "boundary. 0 = no simplification. Defaults to one DEM pixel width.": (
            "Douglas-Peucker-forenklingsavstand, i lagets kartenheter. Reduserer "
            "nodetettheten («én node per piksel») og generaliserer grensa. "
            "0 = ingen forenkling. Standardverdi er én DEM-pikselbredde."
        ),
        "Rounds off remaining corners after simplification (Chaikin cutting - "
        "adds vertices, doesn't reduce them). 0 = no rounding.": (
            "Avrunder gjenværende hjørner etter forenkling (Chaikin-avskjæring - "
            "legger til noder, reduserer dem ikke). 0 = ingen avrunding."
        ),
        "Export level as polygon...": "Eksporter nivå som polygon...",
        "Computing DEM statistics...": "Beregner DEM-statistikk...",
        "Could not read statistics for this layer/band.": "Kunne ikke lese statistikk for dette laget/båndet.",
        "Selected layer/band doesn't look like elevation data "
        "(unexpected value range) - pick a DEM layer.": (
            "Det valgte laget/båndet ser ikke ut som høydedata "
            "(uventet verdiområde) - velg et DEM-lag."
        ),
        "Exporting polygon...": "Eksporterer polygon...",
        "Export failed: {error}": "Eksport mislyktes: {error}",
        "Exported submerged area at {level} m.": "Eksporterte oversvømt areal ved {level} m.",
        "Band {n}": "Bånd {n}",
    },
}


def _detect_language():
    locale = QSettings().value("locale/userLocale")
    return str(locale)[:2] if locale else "en"


# QGIS's UI locale doesn't change without a restart, so detect it once per session
# rather than on every tr() call.
_LANGUAGE = _detect_language()


def tr(text):
    """Translate text to the QGIS UI language; falls back to the English original
    (the text passed in) if there's no entry for the current language.
    """
    return TRANSLATIONS.get(_LANGUAGE, {}).get(text, text)

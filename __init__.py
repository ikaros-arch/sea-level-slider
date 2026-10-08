# -*- coding: utf-8 -*-
# --------------------------------------------------------
#    __init__ - Sea Level Slider plugin init file
# --------------------------------------------------------
def classFactory(iface):
    from .sea_level_slider_plugin import SeaLevelSliderPlugin
    return SeaLevelSliderPlugin(iface)

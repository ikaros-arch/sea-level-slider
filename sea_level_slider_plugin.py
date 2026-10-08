# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .sea_level_slider_dockwidget import SeaLevelSliderDockWidget


class SeaLevelSliderPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock_widget = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icons", "icon.png")
        self.action = QAction(QIcon(icon_path), "Sea Level Slider", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle_dock_widget)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Sea Level Slider", self.action)

    def unload(self):
        self.iface.removePluginMenu("&Sea Level Slider", self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget = None

    def toggle_dock_widget(self, checked):
        if checked:
            if self.dock_widget is None:
                self.dock_widget = SeaLevelSliderDockWidget()
                self.dock_widget.closingPlugin.connect(self._on_dock_closed)
                self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widget)
            self.dock_widget.show()
        elif self.dock_widget is not None:
            self.dock_widget.hide()

    def _on_dock_closed(self):
        self.action.setChecked(False)

# -*- coding: utf-8 -*-
"""
planX — Yerleşim Planı Araç Seti
Main Plugin Entry — Processing Provider Registration
"""

from qgis.core import QgsApplication
from .provider import PlanXYerlesimProvider


class PlanXYerlesimPlugin:
    """Main plugin class registered via classFactory."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initProcessing(self):
        self.provider = PlanXYerlesimProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)

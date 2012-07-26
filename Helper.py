# -*- coding: utf-8 -*-

from PyQt4.QtCore import QObject, Qt
from PyQt4.QtGui import QAction, QToolButton, QMenu, QLabel
from constants import *

from DomainDecomposition import runGenerateShapeTopology
from DataModelLoader import nldas

class Helper:
    """ Main class for PIHM helper plugin """

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.tb = self.iface.addToolBar(PIHM_HELPER)
        self.tb.setObjectName(PIHM_HELPER);
        label = QLabel("PIHM\nhelper")
        label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        label.setMargin(2)
        self.tb.addWidget(label)

    def initGui(self):
        # set up toolbar & menu
        self._domain()
        self._model()

    def unload(self):
        self.iface.removePluginMenu(PIHM_HELPER, self.domainAction)
        self.iface.removePluginMenu(PIHM_HELPER, self.modelAction)

    def _domain(self):
        """ Set up Domain Decomposition menu """
        menu = QMenu(PIHM_DOMAIN)
        action = QAction(PIHM_TOPOLOGY, self.iface.mainWindow())
        action.activated.connect(runGenerateShapeTopology)
        menu.addAction(action);

        self.domainAction = QAction(PIHM_DOMAIN, self.iface.mainWindow())
        self.domainAction.setMenu(menu);
        self.iface.addPluginToMenu(PIHM_HELPER, self.domainAction)

        b = QToolButton()
        b.setMenu(menu)
        b.setPopupMode(QToolButton.InstantPopup)
        b.setText(PIHM_DOMAIN)
        b.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.tb.addWidget(b)

    def _model(self):
        """ Set up DataModel Loader menu """
        menu = QMenu(PIHM_DML)
        action = QAction(PIHM_NLDAS, self.iface.mainWindow())
        action.activated.connect(nldas)
        menu.addAction(action);

        self.modelAction = QAction(PIHM_DML, self.iface.mainWindow())
        self.modelAction.setMenu(menu);
        self.iface.addPluginToMenu(PIHM_HELPER, self.modelAction)

        b = QToolButton()
        b.setMenu(menu)
        b.setPopupMode(QToolButton.InstantPopup)
        b.setText(PIHM_DML)
        b.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.tb.addWidget(b)

if __name__ == "__main__":
    pass

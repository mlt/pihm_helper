#!/usr/bin/env python
# -*- coding: utf-8; mode: python; mode: ropemacs -*-

""" A GUI for NLDAS-2 extractor
"""

import sys, re
from PyQt4.QtGui import QDialog, QApplication, QFileDialog, QMessageBox, QStatusBar
# QShortcut, QKeySequence
from PyQt4.QtCore import QObject, SIGNAL, Qt, QThread, pyqtSignal, pyqtSlot, QSettings, QDateTime, QEvent, QTimer
# QFuture
# QCoreApplication, QEventLoop
from ui_nldas_extractor import Ui_Dialog
from nldas_extractor import Extractor, CACHE
from datetime import datetime
import time
import logging

# log.basicConfig(level=log.DEBUG)
# logging.basicConfig(filename='d:/pihm_helper.log',level=logging.DEBUG)

log = logging.getLogger(__name__)

_iface = None
try:
    from qgis.core import QgsProject, QgsMessageLog, QgsMapLayerRegistry
    import qgis.utils
    _iface = qgis.utils.iface
except ImportError:
    pass

__all__ = ['nldas']

class MainWindow(QDialog):
    """ Dialog to fetch data over OPeNDAP from NLDAS-2 """

    stop_request = pyqtSignal()

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # flags = self.windowFlags() | Qt.WindowStaysOnTopHint ^ Qt.WindowContextHelpButtonHint
        flags = self.windowFlags() ^ Qt.WindowContextHelpButtonHint
        self.setWindowFlags(flags)
        self.ui.progressBar.setVisible(False)
        self.ui.stopButton.hide()

        self._connect_gui_signals()
        self._load_settings()
        self._setup_thread()

        # http://lists.osgeo.org/pipermail/qgis-developer/2012-July/021252.html
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_idle)

        # sc = QShortcut(QKeySequence(Qt.ALT + Qt.Key_A), self)
        # sc.activatedAmbiguously.connect(self.ui.coverageBox.setFocus)
        # sc.activated.connect(self.ui.coverageBox.setFocus)

        # self.sb = QStatusBar()
        # self.ui.verticalLayout.addWidget(self.sb)

    def _connect_gui_signals(self):
        self.ui.nldasButton.clicked.connect(self.browse_cache)
        self.ui.coverageButton.clicked.connect(self.browse_coverage)
        self.ui.outputButton.clicked.connect(self.browse_output)
        self.ui.runButton.clicked.connect(self.accept)
        self.ui.stopButton.clicked.connect(self.terminate)
        self.ui.hideButton.clicked.connect(self.close)
        QObject.connect(self.ui.coverageBox, SIGNAL("currentIndexChanged(int)"),
                        self.coverage_changed)
        QObject.connect(self.ui.coverageBox, SIGNAL("editTextChanged(QString)"),
                        self.coverage_text_changed)

    def _load_settings(self):
        s = QSettings()
        self.ui.nldasEdit.setText(s.value("pihm_helper/nldas/cache", "./cache").toString())
        o = s.value("pihm_helper/nldas/output", ".").toString()
        self.ui.coverageBox.setEditText(s.value("pihm_helper/nldas/input", ".").toString())
        self.ui.beginEdit.setDateTime(QDateTime.fromString(s.value("pihm_helper/nldas/begin", "1999-12-31T19:00:00").toString(), Qt.ISODate))
        self.ui.endEdit.setDateTime(QDateTime.fromString(s.value("pihm_helper/nldas/end", "2000-01-01T02:00:00").toString(), Qt.ISODate))
        if _iface:
            p = QgsProject.instance()
            o = p.readPath(p.readEntry("pihm_helper", "nldas/output", o)[0])
        self.ui.outputEdit.setText(o)

    def _save_settings(self):
        s = QSettings()
        s.setValue("pihm_helper/nldas/cache", self.ui.nldasEdit.text())
        s.setValue("pihm_helper/nldas/output", self.ui.outputEdit.text())
        if -1 == self.ui.coverageBox.currentIndex():
            s.setValue("pihm_helper/nldas/input", self.ui.coverageBox.currentText())
        s.setValue("pihm_helper/nldas/begin", self.ui.beginEdit.dateTime().toString(Qt.ISODate))
        s.setValue("pihm_helper/nldas/end", self.ui.endEdit.dateTime().toString(Qt.ISODate))
        if _iface:
            p = QgsProject.instance()
            p.writeEntry("pihm_helper", "nldas/output", p.writePath(self.ui.outputEdit.text()))

    def _setup_thread(self):
        self.thread = QThread(self) # self
        self.extractor = Worker()
        self.thread.started.connect(self.extractor.start)
        self.thread.finished.connect(self.on_finished)
        # self.extractor.finished.connect(self.thread.quit)
        QObject.connect(self.extractor, SIGNAL("finished()"),
                        self.thread.quit)
        QObject.connect(self, SIGNAL("stop_request()"),
                        self.extractor.stop)
        QObject.connect(self.extractor, SIGNAL("progress(QString,int,int)"),
                        self.on_progress)
        QObject.connect(self.extractor, SIGNAL("error(QString)"),
                        self.on_error)
        self.extractor.moveToThread(self.thread)

    def accept(self):
        # if self.thread.isRunning():
        #     QMessageBox.warning(self, "Extraction is in progress",
        #                         "I'm already working so I ignore this new request.")
        #     return
        self._save_settings()
        self.extractor.begin = self.ui.beginEdit.dateTime().toUTC().toPyDateTime()
        self.extractor.end = self.ui.endEdit.dateTime().toUTC().toPyDateTime()
        self.extractor.output = str(self.ui.outputEdit.text())
        CACHE = str(self.ui.nldasEdit.text())
        idx = self.ui.coverageBox.currentIndex()
        if idx > -1:
            id = self.ui.coverageBox.itemData(idx).toPyObject()
            layer = QgsMapLayerRegistry.instance().mapLayer(id)
            cnt = layer.selectedFeatureCount()
            if cnt and self.ui.selectedBox.isEnabled() and self.ui.selectedBox.isChecked():
                nldasid = layer.fieldNameIndex('NLDAS_ID')
                nldasx = layer.fieldNameIndex('NLDAS_X')
                nldasy = layer.fieldNameIndex('NLDAS_Y')
                if (any((x==-1 for x in (nldasid, nldasx, nldasy)))):
                    QMessageBox.critical(self, self.tr("Necessary attributes are not found"),
                                         self.tr("Layer must have NLDAS_ID, NLDAS_X, NLDAS_Y fields"))
                    return
                out = []
                r = layer.boundingBoxOfSelected()
                ext = [r.xMinimum(), r.xMaximum(), r.yMinimum(), r.yMaximum()]
                for feature in layer.selectedFeatures():
                    m = feature.attributeMap()
                    id = str(m[nldasid].toPyObject())
                    x = m[nldasx].toPyObject()
                    y = m[nldasy].toPyObject()
                    out.append((id, x, y))
                self.extractor.coverage = (ext, out)
            else:               # no selection
                self.extractor.setCoverage(str(layer.source()))
        else:
            self.extractor.setCoverage(str(self.ui.coverageBox.currentText()))
        self.extractor.csv = self.ui.csvButton.isChecked()
        self.ui.progressBar.setMaximum(0)
        self.ui.progressBar.setVisible(True)
        self.thread.start()
        self.start = datetime.now()
        self.ui.runButton.hide()
        self.ui.stopButton.show()
        if _iface:
            self.timer.start(2000)

    def browse_cache(self):
        folder = QFileDialog.getExistingDirectory(self,
                                                  self.tr("Select OPeNDAP cache location"),
                                                  self.ui.nldasEdit.text(),
                                                  QFileDialog.ShowDirsOnly)
        if folder:
            self.ui.nldasEdit.setText(folder)

    def browse_coverage(self):
        file = QFileDialog.getOpenFileName(self,
                                           self.tr("Select a shapefile"),
                                           self.ui.coverageBox.currentText(),
                                           self.tr("ESRI shapefile (*.shp);;All files (*.*)"))
        if file:
            self.ui.coverageBox.setEditText(file)

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self,
                                                  self.tr("Select output location"),
                                                  self.ui.outputEdit.text(),
                                                  QFileDialog.ShowDirsOnly)
        if folder:
            self.ui.outputEdit.setText(folder)

    def coverage_changed(self, idx):
        id = self.ui.coverageBox.itemData(idx).toPyObject()
        if _iface and id:
            try:
                layer = QgsMapLayerRegistry.instance().mapLayer(id)
                sel = layer.selectedFeatureCount() > 0
                self.ui.selectedBox.setEnabled(sel)
                self.ui.selectedBox.setChecked(sel)
            except TypeError:
                self.ui.selectedBox.setEnabled(False)
                self.ui.selectedBox.setChecked(False)

    def coverage_text_changed(self, text):
        idx = self.ui.coverageBox.findText(text)
        if idx > -1:
            self.ui.coverageBox.setCurrentIndex(idx)

    # def event(self, e):
    #     if e.type() == QEvent.StatusTip:
    #         self.sb.showMessage(e.tip())
    #         return True
    #     return super(MainWindow, self).event(e)

    def on_error(self, what):
        self.ui.progressBar.setVisible(False)
        raise Exception(what)

    def on_finished(self):
        self.timer.stop()
        self.ui.stopButton.hide()
        self.ui.stopButton.setEnabled()
        self.ui.runButton.show()
        if _iface:
            td = datetime.now() - self.start
            s = "Done! It took me {:s}".format(td)
            sb = _iface.mainWindow().statusBar()
            sb.showMessage(s)

    def on_idle(self):
        time.sleep(.01)

    def on_progress(self, var, at, end):
        self.ui.progressBar.setMaximum(end)
        self.ui.progressBar.setValue(at)
        if _iface:
            sb = _iface.mainWindow().statusBar()
            s = "NLDAS-2 extractor: {:.1f}% (working on {:s})".format(100.*at/end, var)
            sb.showMessage(s)

    def show(self):
        self.ui.coverageBox.clear()
        if _iface:
            legend = _iface.legendInterface()
            for x in legend.layers():
                if x.type() == x.VectorLayer:
                # if x.type() == x.VectorLayer and \
                #         x.crs().toProj4() == '+proj=longlat +datum=WGS84 +no_defs':
                    self.ui.coverageBox.addItem(x.name(), x.id())
            active = _iface.activeLayer()
            if active:
                idx = self.ui.coverageBox.findData(active.id())
                self.ui.coverageBox.setCurrentIndex(idx)
            # p = QgsProject.instance()
            # self.ui.outputEdit.setText(p.readPath('.'))
            # self.ui.nldasEdit.setText(p.readPath('./cache'))
        return super(QDialog, self).show()

    def terminate(self):
        self.ui.stopButton.setDisabled()
        self.stop_request.emit()
        # self.thread.terminate()
        # if self.thread.isFinished():
        #     self.ui.runButton.show()


# http://labs.qt.nokia.com/2010/06/17/youre-doing-it-wrong/
class Worker(QObject, Extractor):
    """ Worker object to fetch NLDAS-2 data in another thread """
    finished = pyqtSignal()
    progress = pyqtSignal('QString', int, int)
    error = pyqtSignal('QString')

    def __init__(self):
        super(Worker, self).__init__()
        Extractor.__init__(self) # otherwise want_quit is uninitialized
        self.callback = self.progress.emit

    @pyqtSlot()
    def start(self):
        self.extract()
        # try:
        #     self.extract()
        # except BaseException as e:
        #     self.error.emit(str(e))
        self.finished.emit()

    @pyqtSlot()
    def stop(self):
        self.want_quit = True


_dialog = None

def nldas():
    """ Create or pop-up the dialog """
    global _dialog
    if not _dialog:
        _dialog = MainWindow()
    _dialog.show()
    # and in case it was open but hiding
    _dialog.raise_()
    _dialog.activateWindow()

def main():
    from PyQt4.QtCore import QCoreApplication
    import logging
    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)
    # share settings with QGIS plugin
    QCoreApplication.setOrganizationName( "QuantumGIS" )
    QCoreApplication.setOrganizationDomain( "qgis.org" )
    QCoreApplication.setApplicationName( "QGIS" )
    nldas()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

import sys, re
from PyQt4.QtGui import QDialog, QApplication, QFileDialog
from PyQt4.QtCore import QObject, SIGNAL
from ui_generateshapetopology import Ui_GenerateShapeTopology
try:                            # when running as a plugin
    from ...constants import *
    from qgis.core import QgsProject
    project = QgsProject.instance()
except:
    project = None

class MainWindow(QDialog):
    """ Dialog for ShapeTopology converter"""
    def __init__(self):
        QDialog.__init__(self)
        self.ui = Ui_GenerateShapeTopology()
        self.ui.setupUi(self)

        QObject.connect(self.ui.cancelButton, SIGNAL("clicked()"), self.close)
        self.ui.inputBrowseButton.clicked.connect(self.browseInput)
        self.ui.outputBrowseButton.clicked.connect(self.browseOutput)
        self.ui.okButton.clicked.connect(self.accept)
        QObject.connect(self.ui.inputFileLineEdit, SIGNAL("textChanged(QString)"),
                        self.updateOutput)

    def show(self):
        input = "MergeFeatures.shp"
        output = "MergeFeatures.poly"
        if project:
            input = project.readPath(project.readEntry(PIHM, PIHM_MERGE, input)[0])
            output = project.readPath(project.readEntry(PIHM, PIHM_PSLG, output)[0])
        self.ui.inputFileLineEdit.setText(input)
        self.ui.outputFileLineEdit.setText(output)
        QDialog.show(self)

    def browseInput(self):
        fileName = QFileDialog.getOpenFileName(self,
                                               self.tr("Select a shapefile"),
                                               "Merged.shp",
                                               self.tr("ESRI shapefile (*.shp);;All files (*.*)"))
        if fileName:
            self.ui.inputFileLineEdit.setText(fileName)

    def updateOutput(self):
        self.ui.outputFileLineEdit.setText(re.sub("\\.shp$", ".poly", 
                                                  str(self.ui.inputFileLineEdit.text())))

    def browseOutput(self):
        fileName = QFileDialog.getSaveFileName(self,
                                               self.tr("Select an output poly file"),
                                               "Merged.poly",
                                               self.tr("Triangle poly file (*.poly);;All files (*.*)"))
        if fileName:
            self.ui.outputFileLineEdit.setText(fileName)

    def accept(self):
        pass

theDialog = None

def runGenerateShapeTopology():
    global theDialog
    if not theDialog:           # don't use Qt::WA_DeleteOnClose
        theDialog = MainWindow()
    theDialog.show()

if __name__ == '__main__':
    """ Unit testing"""
    app = QApplication(sys.argv)
    runGenerateShapeTopology()
    sys.exit(app.exec_())

# -*- coding: utf-8 -*-

import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "..", "ui", "import_culvert_file.ui"))


class dlg_import_culvert_file(QDialog, FORM_CLASS):
    def __init__(self, culv_flds=None, parent=None):
        super(dlg_import_culvert_file, self).__init__()
        self.setupUi(self)

        self.items = {}
        for fld in culv_flds:
            self.tableWidget.insertRow(self.tableWidget.rowCount())
            self.items[fld.lower()] = [fld, ""]

        self.updateTable()

        self.text_file.setFilter(self.tr("Text Files (*.txt);;All Files (*.*)"))
        self.layer_file.setFilter(self.tr("ESRI Shapefile (*.shp);;GeoPackage (*.gpkg)"))

        self.text_file.fileChanged.connect(self.parseTextFile)
        self.cb_tel_ver.currentIndexChanged.connect(self.parseTextFile)

    def tr(self, message):
        return QCoreApplication.translate(self.__class__.__name__, message)

    def updateTable(self):
        self.tableWidget.clearContents()
        for i, [param, txt_param] in enumerate(self.items.values()):
            self.tableWidget.setItem(
                i,
                0,
                QTableWidgetItem(param),
            )
            self.tableWidget.setItem(
                i,
                1,
                QTableWidgetItem(txt_param),
            )

    def parseTextFile(self):
        def get_values(string):
            values = string.strip().split("\t")
            if isinstance(values, str):
                values.split(" ")
            return values

        path = self.text_file.filePath()
        tel_ver = self.cb_tel_ver.currentText()

        with open(path, "r") as txt_file:
            # First line is always a comment
            txt_file.readline()
            # Parse relaxation parameter and number of culverts
            relax, nb_OH = get_values(txt_file.readline())
            headers = get_values(txt_file.readline())

        for header in headers:
            if header.lower() in self.items.keys():
                self.items[header.lower()][1] = header

        self.updateTable()

# -*- coding: utf-8 -*-

import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QComboBox, QDialog, QTableWidgetItem

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "..", "ui", "import_culvert_file.ui"))


class dlg_import_culvert_file(QDialog, FORM_CLASS):
    def __init__(self, culv_flds=None, parent=None):
        super(dlg_import_culvert_file, self).__init__()
        self.setupUi(self)

        self.items = {}
        for fld in culv_flds:
            self.items[fld.lower()] = [fld, ""]

        self.updateTable()

        self.text_file.setFilter(self.tr("Text Files (*.txt);;All Files (*.*)"))
        self.layer_file.setFilter(self.tr("ESRI Shapefile (*.shp);;GeoPackage (*.gpkg)"))

        self.text_file.fileChanged.connect(self.parseTextFile)
        self.cb_tel_ver.currentIndexChanged.connect(self.parseTextFile)

        self.buttonBox.accepted.connect(self.dialogAccepted)
        self.buttonBox.rejected.connect(self.dialogRejected)

    def tr(self, message):
        return QCoreApplication.translate(self.__class__.__name__, message)

    def cleanTable(self):
        while self.tableWidget.rowCount() > 0:
            self.tableWidget.cellWidget(0, 1).currentIndexChanged.disconnect()
            self.tableWidget.removeRow(0)

    def updateTable(self):
        self.cleanTable()

        txt_params = [""]
        for x in self.items.values():
            if x[1]:
                txt_params.append(x[1])

        for param, txt_param in self.items.values():
            self.tableWidget.insertRow(self.tableWidget.rowCount())
            self.tableWidget.setItem(
                self.tableWidget.rowCount() - 1,
                0,
                QTableWidgetItem(param),
            )
            cb = QComboBox()
            cb.addItems(txt_params)
            cb.setCurrentText(txt_param)
            cb.currentIndexChanged.connect(self.updateDico)
            self.tableWidget.setCellWidget(
                self.tableWidget.rowCount() - 1,
                1,
                cb,
            )

    def updateDico(self):
        for row in range(self.tableWidget.rowCount()):
            param = self.tableWidget.item(row, 0).text()
            txt_param = self.tableWidget.cellWidget(row, 1).currentText()
            self.items[param.lower()][1] = txt_param

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

    def dialogAccepted(self):
        self.updateDico()
        self.cleanTable()
        self.accept()

    def dialogRejected(self):
        self.cleanTable()
        self.reject()

# -*- coding: utf-8 -*-

import os

from qgis.gui import QgsProjectionSelectionDialog
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "..", "ui", "create_culvert_shp.ui"))


class dlg_create_culvert_shapefile(QDialog, FORM_CLASS):
    def __init__(self, crs_mesh=None, parent=None):
        super(dlg_create_culvert_shapefile, self).__init__()
        self.setupUi(self)
        self.cur_shp = None
        self.cur_crs = crs_mesh
        path_icon = os.path.join(os.path.dirname(__file__), "..", "icons/")

        self.btn_open_file.setIcon(QIcon(os.path.join(path_icon, "icon_rep.png")))
        self.btn_open_crs.setIcon(QIcon(os.path.join(path_icon, "icon_srs.png")))
        self.btn_valid.setIcon(QIcon(os.path.join(path_icon, "icon_val.png")))
        self.btn_cancel.setIcon(QIcon(os.path.join(path_icon, "icon_can.png")))

        self.btn_open_file.clicked.connect(self.select_bdd)
        self.btn_open_crs.clicked.connect(self.select_srs)
        self.btn_valid.clicked.connect(self.exec_maj)
        self.btn_cancel.clicked.connect(self.canc_maj)

        if self.cur_crs:
            self.lbl_crs.setText(self.cur_crs.description())

    def select_bdd(self):
        """Sélection de l'emplacement de la BDD"""
        txt, _ = QFileDialog.getSaveFileName(self, "Shapefile", "", "ESRI Shapefile (*.shp)")
        if txt != "":
            self.txt_file.setText(txt)

    def select_srs(self):
        """Sélection du système de projection de la BDD"""
        dlg_srs = QgsProjectionSelectionDialog()
        if dlg_srs.exec():
            if dlg_srs.crs().isValid():
                self.lbl_crs.setText(dlg_srs.crs().description())
                self.cur_crs = dlg_srs.crs()
                # self.cur_crs = dlg_srs.crs().authid()
            else:
                self.lbl_crs.setText("")
                self.cur_crs = None

    def exec_maj(self):
        """Création de la BDD"""
        if self.txt_file.text() == "":
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un fichier.", QMessageBox.Ok)
            self.cur_shp = None
            return
        else:
            self.cur_shp = self.txt_file.text()

        if not self.cur_crs:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner une projection.", QMessageBox.Ok)
            return

        self.accept()

    def canc_maj(self):
        """Annulation"""
        self.reject()

# -*- coding: utf-8 -*-

import os
from datetime import datetime

from qgis.core import (
    QgsProject,
    QgsMeshLayer,
    QgsMesh,
    QgsTriangle,
    QgsMapLayerType,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    
)
from qgis.gui import QgsVertexMarker

from qgis.utils import iface

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QIcon, QFont, QColor, QStandardItemModel, QStandardItem
from qgis.PyQt.QtWidgets import QWidget

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '..', 'ui', 'mesh_quality.ui'))


class MeshQuality(QWidget, FORM_CLASS):
    closingTool = pyqtSignal()

    def __init__(self, parent=None):
        super(MeshQuality, self).__init__(parent)
        self.setupUi(self)
        self.prt = parent
        self.path_icon = os.path.join(os.path.dirname(__file__), '..', 'icons/')
        
        self.lay_mesh = None
        self.lay_mesh_id = None
        self.native_mesh = None
        self.xform = None
        
        self.is_opening = True
        
        self.mdl_lay_mesh = QStandardItemModel()
        self.cb_lay_mesh.setModel(self.mdl_lay_mesh)
        
        QgsProject.instance().layersAdded.connect(self.addLayers)
        QgsProject.instance().layersRemoved.connect(self.removeLayers)
        
        self.cb_lay_mesh.currentIndexChanged.connect(self.mesh_lay_changed)
        
        self.btn_analyse_mesh.clicked.connect(self.analyse_mesh)
        
        for lay in QgsProject.instance().mapLayers().values():
            self.analyse_layer(lay)
            
        self.is_opening = False
        
    def closeEvent(self, event):
        self.closingTool.emit()
        event.accept()

    def addLayers(self, layers):
        for lay in layers:
            self.analyse_layer(lay)

    def removeLayers(self, layers):
        for mdl in [self.mdl_lay_culv, self.mdl_lay_mesh]:
            for r in range(mdl.rowCount() - 1, -1, -1):
                if mdl.item(r, 0).data(32) in layers:
                    mdl.takeRow(r)

    def analyse_layer(self, lay):
        if lay.type() == QgsMapLayerType.MeshLayer:
            itm = QStandardItem()
            itm.setData(lay.name(), 0)
            itm.setData(lay.id(), 32)
            self.mdl_lay_mesh.appendRow(itm)
            self.mdl_lay_mesh.sort(0)

    ######################################################################################
    #                                                                                    #
    #                                     MESH LAYER                                     #
    #                                                                                    #
    ######################################################################################

    def mesh_lay_changed(self):
        lay_id = self.cb_lay_mesh.currentData(32)
        if self.lay_mesh_id == lay_id:
            return

        if lay_id:
            self.lay_mesh = QgsProject.instance().mapLayer(lay_id)
            self.lay_mesh_id = lay_id
            self.xform = QgsCoordinateTransform(
                self.lay_mesh.crs(),
                QgsProject.instance().crs(),
                QgsProject.instance(),
            )
        else:
            self.lay_mesh = None
            self.lay_mesh_id = None
            self.native_mesh = None
            self.xform = None
        self.cur_mesh_changed()

    def cur_mesh_changed(self):
        if self.lay_mesh is not None:
            self.write_log(f"Current mesh changed : {self.lay_mesh.name()}")
            self.native_mesh = QgsMesh()
            self.lay_mesh.dataProvider().populateMesh(self.native_mesh)
            # self.faces = self.create_faces_spatial_index()

            # mesh_prov = self.lay_mesh.dataProvider()
            # for i in range(mesh_prov.datasetGroupCount()):
                # itm = QStandardItem()
                # itm.setData(mesh_prov.datasetGroupMetadata(i).name(), 0)
                # itm.setData(i, 32)
                # self.mdl_mesh_dataset.appendRow(itm)

    def analyse_mesh(self):
        if not self.lay_mesh:
            self.write_log("No mesh selected", 2)
            return
        
        wasInEditMode = False
        if self.lay_mesh.isEditable():
            wasInEditMode = True
            # self.lay_mesh.stopFrameEditing(self.xform)
            self.write_log("Stop edit mode first", 2)
            return
        
        
        
        
            
        
        

    def write_log(self, txt, mode=1):
        self.log.setTextColor(QColor("black"))
        self.log.setFontWeight(QFont.Bold)
        self.log.append(f"{datetime.now().strftime('%H:%M:%S')} - ")
        if mode == 0:
            self.log.setTextColor(QColor("green"))
        elif mode == 1:
            self.log.setTextColor(QColor("black"))
        elif mode == 2:
            self.log.setTextColor(QColor("red"))
        self.log.setFontWeight(QFont.Normal)
        self.log.insertPlainText(txt)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
    
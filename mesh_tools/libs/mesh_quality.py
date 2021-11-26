# -*- coding: utf-8 -*-

import math
import os
from datetime import datetime

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
    QgsLineString,
    QgsMapLayerProxyModel,
    QgsMapLayerType,
    QgsMesh,
    QgsPointXY,
    QgsProject,
    QgsTriangle,
    QgsVectorLayer,
)
from qgis.gui import QgsVertexMarker
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QWidget
from qgis.utils import iface

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "..", "ui", "mesh_quality.ui"))


class MeshQuality(QWidget, FORM_CLASS):
    def __init__(self, parent=None):
        super(MeshQuality, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.project = QgsProject.instance()
        self.prt = parent
        self.path_icon = os.path.join(os.path.dirname(__file__), "..", "icons/")

        self.lay_mesh = self.mMapLayerComboBox.currentLayer()
        self.native_mesh = None
        self.native_mesh_faces_count = None
        self.xform = None

        self.mesh_lay_changed()

        self.bad_faces_center = []

        self.mMapLayerComboBox.setFilters(QgsMapLayerProxyModel.MeshLayer)
        self.mMapLayerComboBox.layerChanged.connect(self.mesh_lay_changed)

        self.btn_analyse_mesh.clicked.connect(self.analyse_mesh)
        self.btn_reset_marker.clicked.connect(self.resetVertexMarker)

    def closeEvent(self, event):
        self.resetVertexMarker()
        event.accept()

    ######################################################################################
    #                                                                                    #
    #                                     MESH LAYER                                     #
    #                                                                                    #
    ######################################################################################

    def mesh_lay_changed(self):
        self.lay_mesh = self.mMapLayerComboBox.currentLayer()

        if self.lay_mesh:
            self.write_log(f"Current mesh changed : {self.lay_mesh.name()}")
            self.xform = QgsCoordinateTransform(
                self.lay_mesh.crs(),
                self.canvas.mapSettings().destinationCrs(),
                self.project,
            )
        else:
            self.lay_mesh = None
            self.native_mesh = None
            self.xform = None
        self.cur_mesh_changed()

    def cur_mesh_changed(self):
        if self.lay_mesh:
            self.native_mesh = QgsMesh()
            self.lay_mesh.dataProvider().populateMesh(self.native_mesh)

    def analyse_mesh(self):
        if not self.lay_mesh:
            self.write_log("No mesh selected", 2)

        wasInEditMode = False
        if self.lay_mesh.isEditable():
            wasInEditMode = True
            self.lay_mesh.commitFrameEditing(self.xform, False)
            self.cur_mesh_changed()

        self.resetVertexMarker()

        self.native_mesh_faces_count = self.native_mesh.faceCount()

        for index in range(self.native_mesh_faces_count):
            face = self.native_mesh.face(index)
            points = [self.native_mesh.vertex(v) for v in face]
            triangle = QgsTriangle()
            triangle.setExteriorRing(QgsLineString(points))

            if self.chk_equilateralness.isChecked():
                if any(math.degrees(a) < self.qdsb_bad_angle_1.value() for a in triangle.angles()):
                    self.addVertexMarker(triangle.centroid(), "bad_angle_1")
                elif any(math.degrees(a) < self.qdsb_bad_angle_2.value() for a in triangle.angles()):
                    self.addVertexMarker(triangle.centroid(), "bad_angle_2")
                elif any(math.degrees(a) < self.qdsb_bad_angle_3.value() for a in triangle.angles()):
                    self.addVertexMarker(triangle.centroid(), "bad_angle_3")

            if self.chk_min_size.isChecked():
                if any(l < self.qdsb_min_element_length.value() for l in triangle.lengths()):
                    self.addVertexMarker(triangle.centroid(), "bad_length")
                if triangle.area() < self.qdsb_min_face_area.value():
                    self.addVertexMarker(triangle.centroid(), "bad_area")

        if self.bad_faces_center:
            self.btn_reset_marker.setEnabled(True)
            self.showVertexMarker()

        if wasInEditMode:
            self.lay_mesh.startFrameEditing(self.xform)

    def addVertexMarker(self, point, type):
        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(QgsPointXY(point))

        if type == "bad_angle_1":
            marker.setColor(QColor(255, 0, 0))
            marker.setPenWidth(2)
            marker.setIconType(QgsVertexMarker.ICON_X)
            marker.setIconSize(10)
        elif type == "bad_angle_2":
            marker.setColor(QColor(255, 255, 0))
            marker.setPenWidth(2)
            marker.setIconType(QgsVertexMarker.ICON_X)
            marker.setIconSize(10)
        elif type == "bad_angle_3":
            marker.setColor(QColor(0, 0, 255))
            marker.setPenWidth(2)
            marker.setIconType(QgsVertexMarker.ICON_X)
            marker.setIconSize(10)
        elif type == "bad_length":
            marker.setColor(QColor(255, 0, 0))
            marker.setPenWidth(2)
            marker.setIconType(QgsVertexMarker.ICON_BOX)
            marker.setIconSize(10)
        elif type == "bad_area":
            marker.setColor(QColor(255, 0, 0))
            marker.setPenWidth(2)
            marker.setIconType(QgsVertexMarker.ICON_TRIANGLE)
            marker.setIconSize(10)

        marker.hide()

        self.bad_faces_center.append(marker)

    def showVertexMarker(self, id=None):
        if id:
            marker[id].show()
        else:
            for marker in self.bad_faces_center:
                marker.show()

    def hideVertexMarker(self, id=None):
        if id:
            marker[id].hide()
        else:
            for marker in self.bad_faces_center:
                marker.hide()

    def resetVertexMarker(self):
        if self.bad_faces_center:
            for marker in self.bad_faces_center:
                marker.hide()
                self.canvas.scene().removeItem(marker)
        self.bad_faces_center = []
        self.btn_reset_marker.setEnabled(False)

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

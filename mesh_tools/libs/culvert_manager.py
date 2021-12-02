# -*- coding: utf-8 -*-

import os
import time

import numpy as np
from processing.algs.gdal.GdalUtils import GdalUtils
from qgis.core import (
    NULL,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineString,
    QgsMapLayerProxyModel,
    QgsMapLayerType,
    QgsMesh,
    QgsMeshDatasetIndex,
    QgsPointXY,
    QgsPolygon,
    QgsProject,
    QgsSpatialIndex,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QVariant, pyqtSignal
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QLineEdit,
    QMessageBox,
)
from qgis.utils import iface

from ..mesh_tools_dockwidget import MeshToolDockWidget
from .create_culvert_shp_dlg import dlg_create_culvert_shapefile
from .import_culvert_file_dlg import dlg_import_culvert_file

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "..", "ui", "culvert_manager.ui"))


class CulvertManager(MeshToolDockWidget, FORM_CLASS):
    closingTool = pyqtSignal()

    def __init__(self, parent=None):
        super(CulvertManager, self).__init__(parent)
        self.setupUi(self)
        self.prt = parent
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.project = QgsProject.instance()
        self.path_icon = os.path.join(os.path.dirname(__file__), "..", "icons/")
        self.file_culv_style = os.path.join(os.path.dirname(__file__), "..", "styles/culvert.qml")
        self.ctrl_signal_blocked = False

        self.frm_culv_tools.hide()

        self.lay_mesh = None
        self.lay_culv = None

        self.native_mesh = None
        self.vertices = None

        self.cur_culv_id = None
        self.cur_mesh_dataset = None
        self.cur_mesh_time = None

        self.software_select = 0

        # Col4 - Index for Telemac
        # Col5 - Index for Uhaina
        self.culv_flds = [
            ["NAME", QVariant.String, self.txt_name, 28, 22],
            ["N1", QVariant.Int, None, 0, None],
            ["N2", QVariant.Int, None, 1, None],
            ["CE1", QVariant.Double, self.sb_ce1, 2, 6],
            ["CE2", QVariant.Double, self.sb_ce2, 3, 7],
            ["CS1", QVariant.Double, self.sb_cs1, 4, 8],
            ["CS2", QVariant.Double, self.sb_cs2, 5, 9],
            ["LARG", QVariant.Double, self.sb_larg, 6, 17],
            ["HAUT", QVariant.Double, self.sb_haut1, 7, 18],
            ["CLAP", QVariant.String, self.cb_clapet, 8, 20],
            ["L12", QVariant.Double, self.sb_l12, 9, 10],
            ["Z1", QVariant.Double, self.sb_z1, 10, 2],
            ["Z2", QVariant.Double, self.sb_z2, 11, 5],
            ["CV", QVariant.Double, self.sb_cv, 12, None],
            ["C56", QVariant.Double, self.sb_c56, 13, None],
            ["CV5", QVariant.Double, self.sb_cv5, 14, None],
            ["C5", QVariant.Double, self.sb_c5, 15, None],
            ["CT", QVariant.Double, self.sb_ct, 16, None],
            ["HAUT2", QVariant.Double, self.sb_haut2, 17, 19],
            ["FRIC", QVariant.Double, self.sb_fric, 18, None],
            ["LENGTH", QVariant.Double, self.sb_length, 19, None],
            ["CIRC", QVariant.Int, self.cb_circ, 20, 16],
            ["d1", QVariant.Double, self.sb_d1, 21, 11],
            ["d2", QVariant.Double, self.sb_d2, 22, 12],
            ["a1", QVariant.Double, self.sb_a1, 23, 14],
            ["a2", QVariant.Double, self.sb_a2, 24, 15],
            ["AA", QVariant.Int, self.cb_auto_a, 25, 13],
            ["AL", QVariant.Int, self.cb_auto_l, 26, None],
            ["AZ", QVariant.Int, self.cb_auto_z, 27, 21],
        ]

        self.is_opening = True

        self.mdl_lay_culv = QStandardItemModel()

        self.mdl_mesh_dataset = QStandardItemModel()
        self.mdl_mesh_time = QStandardItemModel()

        self.cb_lay_culv.setModel(self.mdl_lay_culv)
        self.cb_dataset_mesh.setModel(self.mdl_mesh_dataset)
        self.cb_time_mesh.setModel(self.mdl_mesh_time)

        # self.clickTool = QgsMapToolEmitPoint(iface.mapCanvas())
        # self.clickTool.canvasClicked.connect(self.postSelectCulvert)

        self.project.layersAdded.connect(self.addLayers)
        self.project.layersRemoved.connect(self.removeLayers)

        self.cb_lay_mesh.setFilters(QgsMapLayerProxyModel.MeshLayer)
        self.cb_lay_mesh.layerChanged.connect(self.mesh_lay_changed)
        self.cb_lay_culv.currentIndexChanged.connect(self.culv_lay_changed)
        self.cb_dataset_mesh.currentIndexChanged.connect(self.mesh_dataset_changed)
        self.cb_time_mesh.currentIndexChanged.connect(self.mesh_time_changed)

        self.btn_new_culv_file.clicked.connect(self.new_file)
        self.btn_import_culv_file.clicked.connect(self.import_culvert)
        self.btn_res_val.clicked.connect(self.reset_val)
        self.btn_verif.clicked.connect(self.verif_culvert)
        self.btn_create_file.clicked.connect(self.create_file)
        self.cb_software_select.currentIndexChanged.connect(self.soft_changed)
        # self.btn_sel_culv.clicked.connect(self.select_culv)

        for fld in self.culv_flds:
            ctrl = fld[2]
            if ctrl:
                if isinstance(ctrl, QDoubleSpinBox):
                    ctrl.valueChanged.connect(self.ctrl_edited)
                elif isinstance(ctrl, QComboBox):
                    ctrl.currentIndexChanged.connect(self.ctrl_edited)
                elif isinstance(ctrl, QCheckBox):
                    ctrl.stateChanged.connect(self.ctrl_edited)
                elif isinstance(ctrl, QLineEdit):
                    ctrl.textChanged.connect(self.ctrl_edited)

        for lay in self.project.mapLayers().values():
            self.analyse_layer(lay)

        self.mesh_lay_changed()

        if self.mdl_lay_culv.rowCount() == 0:
            self.culv_lay_changed()

        self.is_opening = False

    def addLayers(self, layers):
        for lay in layers:
            self.analyse_layer(lay)

    def removeLayers(self, layers):
        for r in range(self.mdl_lay_culv.rowCount() - 1, -1, -1):
            if self.mdl_lay_culv.item(r, 0).data(32) in layers:
                self.mdl_lay_culv.takeRow(r)

    def analyse_layer(self, lay):
        if lay.type() == QgsMapLayerType.VectorLayer:
            flds = [f.name() for f in lay.fields()]
            if all(elem in flds for elem in [fc[0] for fc in self.culv_flds]):
                itm = QStandardItem()
                itm.setData(lay.name(), 0)
                itm.setData(lay.id(), 32)
                self.mdl_lay_culv.appendRow(itm)
                self.mdl_lay_culv.sort(0)

    def clean(self):
        self.project.layersAdded.disconnect(self.addLayers)
        self.project.layersRemoved.disconnect(self.removeLayers)

        self.cb_lay_mesh.layerChanged.disconnect(self.mesh_lay_changed)
        self.cb_lay_culv.currentIndexChanged.disconnect(self.culv_lay_changed)
        self.cb_dataset_mesh.currentIndexChanged.disconnect(self.mesh_dataset_changed)
        self.cb_time_mesh.currentIndexChanged.disconnect(self.mesh_time_changed)

    ######################################################################################
    #                                                                                    #
    #                                      SOFTWARE                                      #
    #                                                                                    #
    ######################################################################################

    def soft_changed(self):
        self.software_select = self.cb_software_select.currentIndex()

    ######################################################################################
    #                                                                                    #
    #                                      SOFTWARE                                      #
    #                                                                                    #
    ######################################################################################

    def soft_changed(self):
        self.software_select = self.cb_software_select.currentIndex()

    ######################################################################################
    #                                                                                    #
    #                                     MESH LAYER                                     #
    #                                                                                    #
    ######################################################################################

    def mesh_lay_changed(self):
        self.lay_mesh = self.cb_lay_mesh.currentLayer()

        if self.lay_mesh:
            self.lay_mesh = self.cb_lay_mesh.currentLayer()
            self.cb_dataset_mesh.setEnabled(True)
            self.cb_time_mesh.setEnabled(True)
        else:
            self.lay_mesh = None
            self.native_mesh = None
            self.vertices = None
            self.cb_dataset_mesh.setEnabled(False)
            self.cb_time_mesh.setEnabled(False)
        self.cur_mesh_changed()

    def cur_mesh_changed(self):
        self.mdl_mesh_dataset.clear()
        if self.lay_mesh is not None:
            self.write_log(self.tr("Current mesh changed : {}").format(self.lay_mesh.name()))
            self.native_mesh = QgsMesh()
            self.lay_mesh.dataProvider().populateMesh(self.native_mesh)

            mesh_prov = self.lay_mesh.dataProvider()
            for i in range(mesh_prov.datasetGroupCount()):
                itm = QStandardItem()
                itm.setData(mesh_prov.datasetGroupMetadata(i).name(), 0)
                itm.setData(i, 32)
                self.mdl_mesh_dataset.appendRow(itm)

    def mesh_dataset_changed(self):
        self.mdl_mesh_time.clear()
        self.cur_mesh_dataset = self.cb_dataset_mesh.currentData(32)
        if self.cur_mesh_dataset is not None:
            self.write_log(self.tr("Current mesh dataset changed : {}").format(self.cb_dataset_mesh.currentText()))
            mesh_prov = self.lay_mesh.dataProvider()
            for i in range(mesh_prov.datasetCount(self.cur_mesh_dataset)):
                itm = QStandardItem()
                itm.setData(mesh_prov.datasetMetadata(QgsMeshDatasetIndex(self.cur_mesh_dataset, i)).time(), 0)
                itm.setData(i, 32)
                self.mdl_mesh_time.appendRow(itm)

    def mesh_time_changed(self):
        self.cur_mesh_time = self.cb_time_mesh.currentData(32)
        if self.cur_mesh_time is not None:
            self.write_log(self.tr("Current mesh timestep changed : {}").format(self.cb_time_mesh.currentText()))
            self.vertices = self.create_vertices_spatial_index()
            if self.lay_culv is not None and not self.is_opening:
                self.update_all_n()
                if (
                    QMessageBox.question(
                        self,
                        self.tr("Automatic Z Update"),
                        self.tr(
                            "Mesh parameters have been changed.\nUpdate culvert features with Automatic Z checked ?"
                        ),
                        QMessageBox.Cancel | QMessageBox.Ok,
                    )
                    == QMessageBox.Ok
                ):
                    self.update_all_auto_z()

    def create_vertices_spatial_index(self):
        if self.lay_mesh:
            self.write_log(self.tr("Creation of vertices spatial index…"))
            t0 = time.time()
            spindex = QgsSpatialIndex()

            count = self.native_mesh.vertexCount()
            offset = 0
            batch_size = 10
            while offset < count:
                lst_ft = list()
                iterations = min(batch_size, count - offset)
                for i in range(iterations):
                    ft = QgsFeature()
                    ft.setGeometry(QgsGeometry(self.native_mesh.vertex(offset + i)))
                    ft.setId(offset + i)
                    lst_ft.append(ft)
                spindex.addFeatures(lst_ft)
                offset += iterations

            self.write_log(self.tr("Vertices spatial index created in {} sec.").format(round(time.time() - t0, 1)))
            return spindex
        else:
            return None

    def face_to_poly(self, idx):
        face = self.native_mesh.face(idx)
        points = [self.native_mesh.vertex(v) for v in face]
        polygon = QgsPolygon()
        polygon.setExteriorRing(QgsLineString(points))
        return polygon

    ######################################################################################
    #                                                                                    #
    #                                    CULVERT LAYER                                   #
    #                                                                                    #
    ######################################################################################

    def new_file(self):
        srs_mesh = None
        if self.lay_mesh:
            srs_mesh = self.lay_mesh.crs()
        dlg = dlg_create_culvert_shapefile(srs_mesh, self)
        dlg.setWindowModality(2)
        if dlg.exec_():
            path, crs = dlg.cur_shp, dlg.cur_crs
        if path:
            self.create_new_shp(path, crs)

    def create_new_shp(self, path, crs):
        layerFields = QgsFields()
        for fld in self.culv_flds:
            layerFields.append(QgsField(fld[0], fld[1]))

        tmp_lay = QgsVectorLayer(f"MultiLineString?crs={crs.authid()}", "", "memory")
        pr = tmp_lay.dataProvider()
        pr.addAttributes(layerFields)
        tmp_lay.updateFields()
        QgsVectorFileWriter.writeAsVectorFormat(tmp_lay, path, None, destCRS=crs, driverName="ESRI Shapefile")

        shp_lay = QgsVectorLayer(path, os.path.basename(path).rsplit(".", 1)[0], "ogr")
        shp_lay.loadNamedStyle(self.file_culv_style)
        shp_lay.saveDefaultStyle()
        self.project.addMapLayer(shp_lay)
        self.cb_lay_culv.setCurrentIndex(self.cb_lay_culv.findData(shp_lay.id(), 32))

    def culv_lay_changed(self):
        lay_id = self.cb_lay_culv.currentData(32)
        self.cur_culv_id = None
        if lay_id:
            self.lay_culv = self.project.mapLayer(lay_id)
            self.lay_culv.selectionChanged.connect(self.cur_culv_changed)
            self.lay_culv.editingStarted.connect(self.cur_culv_changed)
            self.lay_culv.editingStopped.connect(self.cur_culv_changed)
            if self.lay_mesh is not None and self.is_opening is False:
                self.update_all_n()
                if (
                    QMessageBox.question(
                        self,
                        self.tr("Automatic Z Update"),
                        self.tr(
                            "Culvert culvert layer has been changed.\nUpdate culvert features with Automatic Z checked ?"
                        ),
                        QMessageBox.Cancel | QMessageBox.Ok,
                    )
                    == QMessageBox.Ok
                ):
                    self.update_all_auto_z()
        else:
            self.lay_culv = None
        self.cur_culv_changed()

    def cur_culv_changed(self):
        if self.lay_culv:
            if self.lay_culv.selectedFeatureCount() == 1:
                self.cur_culv_id = self.lay_culv.selectedFeatureIds()[0]
            else:
                self.cur_culv_id = None
        else:
            self.cur_culv_id = None
        self.display_culv_info()

    def display_culv_info(self):
        if self.lay_culv:
            if self.cur_culv_id is None:
                if self.lay_culv.selectedFeatureCount() == 0:
                    self.gb_cur_culv.setTitle(self.tr("No culvert selected"))
                else:
                    self.gb_cur_culv.setTitle(self.tr("More than one culvert selected"))
                self.clear_info()
                self.gb_cur_culv.setEnabled(False)
            else:
                self.gb_cur_culv.setTitle(self.tr("Selected culvert informations"))
                self.fill_info()
                self.gb_cur_culv.setEnabled(not self.lay_culv.isEditable())
        else:
            self.gb_cur_culv.setTitle(self.tr("No culvert layer selected"))
            self.clear_info()
            self.gb_cur_culv.setEnabled(False)

    def clear_info(self):
        self.ctrl_signal_blocked = True
        for fld in self.culv_flds:
            ctrl = fld[2]
            if ctrl:
                if isinstance(ctrl, QDoubleSpinBox):
                    ctrl.setValue(0.0)
                elif isinstance(ctrl, QComboBox):
                    ctrl.setCurrentIndex(0)
                elif isinstance(ctrl, QCheckBox):
                    ctrl.setCheckState(0)
                elif isinstance(ctrl, QLineEdit):
                    ctrl.setText("")
        self.ctrl_signal_blocked = False

    def fill_info(self):
        self.ctrl_signal_blocked = True
        ft = self.lay_culv.getFeature(self.cur_culv_id)
        for fld in self.culv_flds:
            if fld[2]:
                self.display_info(fld[2], ft[fld[0]])
        self.ctrl_signal_blocked = False

    def display_info(self, ctrl, val):
        if isinstance(ctrl, QDoubleSpinBox):
            if val is None:
                ctrl.setValue(0.0)
            else:
                ctrl.setValue(val)
        elif isinstance(ctrl, QComboBox):
            idx = to_integer(val)
            if idx is None:
                ctrl.setCurrentIndex(0)
            else:
                ctrl.setCurrentIndex(idx)
        elif isinstance(ctrl, QCheckBox):
            if val == 2:
                ctrl.setCheckState(2)
            else:
                ctrl.setCheckState(0)
        elif isinstance(ctrl, QLineEdit):
            ctrl.setText(str(val))

    def ctrl_edited(self):
        ft = None
        if not self.ctrl_signal_blocked:
            if self.cur_culv_id is not None:
                ft = self.lay_culv.getFeature(self.cur_culv_id)

                ctrl = self.sender()
                if isinstance(ctrl, QDoubleSpinBox):
                    val = ctrl.value()
                elif isinstance(ctrl, QComboBox):
                    val = ctrl.currentIndex()
                elif isinstance(ctrl, QCheckBox):
                    val = ctrl.checkState()
                elif isinstance(ctrl, QLineEdit):
                    val = ctrl.text()

                field_idx = None
                for idx in range(len(self.culv_flds)):
                    if ctrl == self.culv_flds[idx][2]:
                        field_name = self.culv_flds[idx][0]
                        field_idx = self.lay_culv.fields().indexFromName(field_name)
                        break

                if field_idx is not None:
                    attrs = {field_idx: val}
                    self.lay_culv.dataProvider().changeAttributeValues({self.cur_culv_id: attrs})
                    self.lay_culv.commitChanges()

        if self.sender() == self.cb_auto_z:
            self.sb_z1.setEnabled(not self.cb_auto_z.isChecked())
            self.sb_z2.setEnabled(not self.cb_auto_z.isChecked())
            if ft:
                if self.cb_auto_z.isChecked():
                    (n1, n2), err = self.recup_n_from_mesh(ft)
                    (z1, z2), err = self.recup_z_from_mesh(ft)
                    if err:
                        self.write_log(self.tr("Error on Z calculation : {}").format(err), 2)
                    else:
                        self.sb_z1.setValue(z1)
                        self.sb_z2.setValue(z2)
                        attrs = {self.cur_culv_id: {ft.fieldNameIndex("N1"): n1, ft.fieldNameIndex("N2"): n2}}
                        self.lay_culv.dataProvider().changeAttributeValues(attrs)
                        self.lay_culv.commitChanges()
                else:
                    attrs = {self.cur_culv_id: {ft.fieldNameIndex("N1"): None, ft.fieldNameIndex("N2"): None}}
                    self.lay_culv.dataProvider().changeAttributeValues(attrs)
                    self.lay_culv.commitChanges()

        if self.sender() == self.cb_auto_a:
            self.sb_a1.setEnabled(not self.cb_auto_a.isChecked())
            self.sb_a2.setEnabled(not self.cb_auto_a.isChecked())
            if ft and (self.cb_auto_a.isChecked()):
                a1, a2 = calculangle(ft)
                self.sb_a1.setValue(a1)
                self.sb_a2.setValue(a2)

        if self.sender() == self.cb_auto_l:
            self.sb_length.setEnabled(not self.cb_auto_l.isChecked())
            if ft and (self.cb_auto_l.isChecked()):
                self.sb_length.setValue(ft.geometry().length())

        if self.sender() == self.cb_circ:
            self.sb_haut2.setEnabled(not self.cb_circ.isChecked())
            self.sb_larg.setEnabled(not self.cb_circ.isChecked())

    def reset_val(self):
        for fld in self.culv_flds:
            ctrl = fld[2]
            if ctrl:
                if isinstance(ctrl, QDoubleSpinBox):
                    if ctrl in [self.sb_ce1, self.sb_ce2]:
                        ctrl.setValue(0.5)
                    elif ctrl in [self.sb_cs1, self.sb_cs2, self.sb_l12]:
                        ctrl.setValue(1.0)
                    else:
                        ctrl.setValue(0.0)
                elif isinstance(ctrl, QComboBox):
                    ctrl.setCurrentIndex(0)
                elif isinstance(ctrl, QCheckBox):
                    ctrl.setCheckState(0)

    def update_all_n(self, log=True):
        attrs = dict()
        for ft in self.lay_culv.getFeatures():
            (n1, n2), err = self.recup_n_from_mesh(ft)
            if not err:
                attrs[ft.id()] = {ft.fieldNameIndex("N1"): n1, ft.fieldNameIndex("N2"): n2}
            else:
                self.write_log(self.tr("Error on N calculation : {}").format(err), 2)
                return

        self.lay_culv.dataProvider().changeAttributeValues(attrs)
        self.lay_culv.commitChanges()
        if log:
            self.write_log(self.tr("N values updated"), 0)

    def update_all_auto_z(self):
        attrs = dict()
        for ft in self.lay_culv.getFeatures():
            if ft["AZ"] == 2:
                (z1, z2), err = self.recup_z_from_mesh(ft)
                if not err:
                    attrs[ft.id()] = {ft.fieldNameIndex("Z1"): z1, ft.fieldNameIndex("Z2"): z2}
                else:
                    self.write_log(self.tr("Error on Z calculation : {}").format(err), 2)
                    return

        self.lay_culv.dataProvider().changeAttributeValues(attrs)
        self.lay_culv.commitChanges()
        self.write_log(self.tr("Z values updated"), 0)
        self.display_culv_info()

    def recup_n_from_mesh(self, ft):
        err, n = None, [None, None]
        if self.lay_mesh:
            mesh_crs = self.lay_mesh.crs()
            if mesh_crs.isValid():
                shp_crs = self.lay_culv.sourceCrs()
                xform = QgsCoordinateTransform(shp_crs, mesh_crs, self.project)
                pts = ft.geometry().asMultiPolyline()
                for p in [0, -1]:
                    pt = pts[p][p]
                    x_pt = xform.transform(pt)
                    if not self.lay_mesh.snapOnElement(QgsMesh.Face, QgsPointXY(x_pt), 0).isEmpty():
                        idx = self.vertices.nearestNeighbor(x_pt, 1)[0]
                        n[p * -1] = idx + 1
                    else:
                        n[p * -1] = None
            else:
                err = self.tr("CRS defined for mesh layer is not valid")
        else:
            err = self.tr("No mesh layer selected")

        return n, err

    def recup_XY_from_n(self, n, shp_crs):
        err, point = None, None
        if self.lay_mesh:
            mesh_crs = self.lay_mesh.crs()
            if mesh_crs.isValid():
                xform = QgsCoordinateTransform(mesh_crs, shp_crs, self.project)
                pt = self.native_mesh.vertex(int(n - 1))
                if not pt.isEmpty():
                    point = xform.transform(QgsPointXY(pt))
                else:
                    err = self.tr("{} node is not in mesh layer").format(n)

            else:
                err = self.tr("CRS defined for mesh layer is not valid")
        else:
            err = self.tr("No mesh layer selected")

        return point, err

    def recup_z_from_mesh(self, ft):
        err, z = None, [None, None]
        if self.lay_mesh:
            mesh_crs = self.lay_mesh.crs()
            if mesh_crs.isValid():
                shp_crs = self.lay_culv.sourceCrs()
                xform = QgsCoordinateTransform(shp_crs, mesh_crs, self.project)
                pts = ft.geometry().asMultiPolyline()
                for p in [0, -1]:
                    pt = pts[p][p]
                    x_pt = xform.transform(pt)
                    if not self.lay_mesh.snapOnElement(QgsMesh.Face, QgsPointXY(x_pt), 0).isEmpty():
                        idx = self.vertices.nearestNeighbor(x_pt, 1)[0]
                        dset_val = self.lay_mesh.dataProvider().datasetValues(
                            QgsMeshDatasetIndex(self.cur_mesh_dataset, self.cur_mesh_time), idx, 1
                        )
                        z[p * -1] = round(dset_val.value(0).scalar(), 2)
                    else:
                        z[p * -1] = 0.0
            else:
                err = self.tr("CRS defined for mesh layer is not valid")
        else:
            err = self.tr("No mesh layer selected")

        return z, err

    ######################################################################################
    #                                                                                    #
    #                                       EXPORT                                       #
    #                                                                                    #
    ######################################################################################

    def verif_culvert(self):
        if not self.lay_culv:
            return

        self.update_all_n(log=False)
        ids = self.verif_culvert_validity()
        if not ids:
            self.write_log(self.tr("All culverts are valid"), 0)
        else:
            for id in ids:
                self.write_log("{} : {}".format(*id), 2)

    def create_file(self):
        if not self.lay_culv:
            return

        ids = self.verif_culvert_validity()
        if ids:
            self.write_log(self.tr("File creation is not possible, some culverts are not valid"), 2)
            return

        culv_file_name, _ = QFileDialog.getSaveFileName(self, self.tr("Culvert file"), "", self.tr("Text File (*.txt)"))

        if culv_file_name == "":
            return

        nb_culv = self.lay_culv.featureCount()
        relax = round(self.sb_relax.value(), 2)

        with open(culv_file_name, "w") as culv_file:
            if self.software_select == 0:  # Telemac
                culv_file.write("Relaxation" + str("\t") + self.tr("Culvert count") + str("\n"))
                culv_file.write(str(relax) + str("\t") + str(nb_culv) + str("\n"))
                idx_out = 3
            elif self.software_select == 1:  # Uhaina
                culv_file.write(self.tr("Culvert count") + str("\n"))
                culv_file.write(str(nb_culv) + str("\n"))
                idx_out = 4

            culv_flds_srtd = [
                fld
                for fld in sorted(self.culv_flds, key=lambda x: (x[idx_out] is None, x[idx_out]))
                if fld[idx_out] is not None
            ]

            txt = ""
            for fld in culv_flds_srtd[:-1]:
                if (self.software_select == 1) & (fld[0] in ["z1", "z2"]):  # Uhaina Only
                    txt += "X1\t"
                    txt += "Y1\t"
                else:
                    txt += "X2\t"
                    txt += "Y2\t"

                txt += f"{fld[0]}\t"
            txt += f"{culv_flds_srtd[-1][0]}\n"
            culv_file.write(txt)

            for ft in self.lay_culv.getFeatures():
                txt = ""
                pts = ft.geometry().asMultiPolyline()
                x1, y1 = QgsPointXY(pts[0][0])
                x2, y2 = QgsPointXY(pts[-1][-1])

                for fld in culv_flds_srtd[:-1]:
                    if (self.software_select == 1) and (fld[0] in ["Z1", "Z2"]):
                        if fld[0] == "Z1":
                            txt += f"{x1}\t"
                            txt += f"{y1}\t"
                        else:
                            txt += f"{x2}\t"
                            txt += f"{y2}\t"
                    txt += f"{ft[fld[0]]}\t"
                txt += f"{ft[culv_flds_srtd[-1][0]]}\n"
                culv_file.write(txt.replace("NULL", " "))

            self.write_log(self.tr("Culvert File Created"), 0)
            return

        self.write_log(self.tr("Error during culvert file creation"), 2)

    def verif_culvert_validity(self):
        selectedids = []
        for ft in self.lay_culv.getFeatures():
            if ft["NAME"] in [NULL, ""]:
                ft_name = self.tr("Nameless culvert (feature id {})").format(ft.id())
            else:
                ft_name = ft["NAME"]

            if (ft["N1"] == NULL) or (ft["N2"] == NULL):
                selectedids.append([ft_name, self.tr("Culvert extremity is not within the mesh.")])

            for fld in self.culv_flds:
                if fld[0] not in ["NAME", "Remarques"] and fld[2]:
                    if fld[1] == QVariant.String:
                        if (ft[fld[0]] == NULL) or not isinstance(ft[fld[0]], str):
                            selectedids.append([ft_name, self.tr("{} value is not correct.").format(fld[0])])
                    elif fld[1] == QVariant.Double:
                        if (ft[fld[0]] == NULL) or not isinstance(ft[fld[0]], float):
                            selectedids.append([ft_name, self.tr("{} value is not correct.").format(fld[0])])
                    elif fld[1] == QVariant.Int:
                        if (ft[fld[0]] == NULL) or not isinstance(ft[fld[0]], int):
                            selectedids.append([ft_name, self.tr("{} value is not correct.").format(fld[0])])

        return selectedids

    ######################################################################################
    #                                                                                    #
    #                                       IMPORT                                       #
    #                                                                                    #
    ######################################################################################

    def import_culvert(self):
        def get_values(string):
            values = string.strip().split("\t")
            if isinstance(values, str):
                values.split(" ")
            return values

        def asDict(headers, values):
            dico = {}
            for i, h in enumerate(headers):
                if values[i] == NULL:
                    dico[h] = ""
                else:
                    dico[h] = float(values[i])
            return dico

        culv_flds = [x[0] for x in self.culv_flds]
        dlg = dlg_import_culvert_file(culv_flds, self)
        dlg.setWindowModality(2)
        if dlg.exec_():
            items = dlg.items
            software = dlg.cb_soft.currentText()
            txt_path = dlg.text_file.filePath()
            layer_path = dlg.layer_file.filePath()
            layerDriver = GdalUtils.getVectorDriverFromFileName(layer_path)
        else:
            return

        if self.lay_mesh and self.lay_mesh.crs() is not None:
            crs = self.lay_mesh.crs()
        else:
            crs = self.project.crs()

        layerFields = QgsFields()
        for fld in self.culv_flds:
            layerFields.append(QgsField(fld[0], fld[1]))

        layer = QgsVectorLayer(f"MultiLineString?crs={crs.authid()}", self.tr("Culverts"), "memory")
        pr = layer.dataProvider()
        pr.addAttributes(layerFields)
        layer.updateFields()
        layer.startEditing()

        with open(txt_path, "r") as txt_file:
            # 1st line is comment
            txt_file.readline()
            # Relaxation and number of culverts
            relax, nb_culvert = get_values(txt_file.readline())
            self.sb_relax.setValue(relax)
            # Retrieve headers
            headers = get_values(txt_file.readline())

            for i in range(int(nb_culvert)):
                lineValues = get_values(txt_file.readline())
                if lineValues == [""]:
                    continue

                values = asDict(headers, lineValues)

                fet = QgsFeature()

                point_n1, err1 = self.recup_XY_from_n(values[items["n1"][1]], crs)
                point_n2, err2 = self.recup_XY_from_n(values[items["n2"][1]], crs)
                if err1 is not None or err2 is not None:
                    err = " ".join(filter(None, (err1, err2)))
                    self.write_log(
                        self.tr("Error when importing culvert {i} with error(s) : {err}").format(i=i, err=err), 2
                    )
                    continue

                line = QgsGeometry.fromPolylineXY([point_n1, point_n2])
                fet.setGeometry(line)

                attrs = []
                for fld in self.culv_flds:
                    key = items[fld[0].lower()][1]
                    if key:
                        attr = values[key]
                    else:
                        if fld[1] in [QVariant.Int, QVariant.Double]:
                            attr = 0
                        else:
                            attr = ""
                    attrs.append(attr)

                fet.setAttributes(attrs)

                if fet.isValid():
                    layer.addFeature(fet)

        if not layer.commitChanges():
            self.write_log(self.tr("Error during culvert file creation"), 2)
            return

        if layer_path:
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = layerDriver
            options.fileEncoding = "utf-8"
            QgsVectorFileWriter.writeAsVectorFormatV2(
                layer=layer,
                fileName=layer_path,
                transformContext=QgsCoordinateTransformContext(),
                options=options,
            )
            layer = QgsVectorLayer(layer_path, os.path.basename(layer_path).rsplit(".", 1)[0], "ogr")

        if layer.isValid():
            layer.loadNamedStyle(self.file_culv_style)
            layer.saveDefaultStyle()
            self.project.addMapLayer(layer)
            self.cb_lay_culv.setCurrentIndex(self.cb_lay_culv.findData(layer.id(), 32))
        else:
            self.write_log(self.tr("Created culvert layer is not valid."), 2)


def correctAngle(angle):
    if angle < 0.0:
        angle += 360
    elif angle > 360.0:
        angle = angle - 360
    return angle


def calculangle(ft):
    pts = ft.geometry().asMultiPolyline()

    deltax = pts[0][1].x() - pts[0][0].x()
    deltay = pts[0][1].y() - pts[0][0].y()
    angle0 = correctAngle(np.angle(deltax + deltay * 1j, deg=True))
    angle1 = correctAngle(angle0 - 180)

    deltax = pts[-1][-1].x() - pts[-1][-2].x()
    deltay = pts[-1][-1].y() - pts[-1][-2].y()
    angle2 = correctAngle(np.angle(deltax + deltay * 1j, deg=True))

    return angle1, angle2


def to_integer(n):
    if not n:
        return None

    try:
        int(n)
    except ValueError:
        return None
    else:
        return int(n)

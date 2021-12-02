# -*- coding: utf-8 -*-

import os
import time

import numpy as np
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineString,
    QgsMapLayerType,
    QgsMesh,
    QgsMeshDatasetIndex,
    QgsPointXY,
    QgsPolygon,
    QgsProject,
    QgsSpatialIndex,
    QgsVectorDataProvider,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QObject, QThread, QVariant, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QWidget,
)
from qgis.utils import iface

from .create_culvert_shp import dlg_create_culvert_shapefile

from ._mesh_tools import find_nearest_node, find_z_from_mesh
from ._log_tools import write_log

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "..", "ui", "culvert_manager.ui"))


class CulvertManager(QWidget, FORM_CLASS):
    closingTool = pyqtSignal()

    def __init__(self, parent=None):
        super(CulvertManager, self).__init__(parent)
        self.setupUi(self)
        self.prt = parent
        self.path_icon = os.path.join(os.path.dirname(__file__), "..", "icons/")
        self.file_culv_style = os.path.join(os.path.dirname(__file__), "..", "styles/culvert.qml")
        self.ctrl_signal_blocked = False

        self.frm_culv_tools.hide()

        self.lay_mesh = None
        self.lay_mesh_id = None
        self.lay_culv = None

        self.native_mesh = None
        self.vertices = None
        self.faces = None

        self.cur_culv_id = None
        self.cur_mesh_dataset = None
        self.cur_mesh_time = None

        self.software_select = 0

# Col4 - Index for Telemac
# Col5 - Index for Uhaina
        self.culv_flds = [
            ["NAME",        QVariant.String,    self.txt_name,  28, 22  ],
            ["N1",          QVariant.Int,       None,           0,  None],
            ["N2",          QVariant.Int,       None,           1,  None],
            ["d1",          QVariant.Double,    self.sb_d1,     21, 11  ],
            ["d2",          QVariant.Double,    self.sb_d2,     22, 12  ],
            ["CE1",         QVariant.Double,    self.sb_ce1,    2,  6   ],
            ["CE2",         QVariant.Double,    self.sb_ce2,    3,  7   ],
            ["CS1",         QVariant.Double,    self.sb_cs1,    4,  8   ],
            ["CS2",         QVariant.Double,    self.sb_cs2,    5,  9   ],
            ["LARG",        QVariant.Double,    self.sb_larg,   6,  17  ],
            ["HAUT",        QVariant.Double,    self.sb_haut1,  7,  18  ],
            ["CLAP",        QVariant.String,    self.cb_clapet, 8,  20  ],
            ["L12",         QVariant.Double,    self.sb_l12,    9,  10  ],
            ["z1",          QVariant.Double,    self.sb_z1,     10, 2   ],
            ["z2",          QVariant.Double,    self.sb_z2,     11, 5   ],
            ["a1",          QVariant.Double,    self.sb_a1,     23, 14  ],
            ["a2",          QVariant.Double,    self.sb_a2,     24, 15  ],
            ["CV",          QVariant.Double,    self.sb_cv,     12, None],
            ["C56",         QVariant.Double,    self.sb_c56,    13, None],
            ["CV5",         QVariant.Double,    self.sb_cv5,    14, None],
            ["C5",          QVariant.Double,    self.sb_c5,     15, None],
            ["CT",          QVariant.Double,    self.sb_ct,     16, None],
            ["HAUT2",       QVariant.Double,    self.sb_haut2,  17, 19  ],
            ["FRIC",        QVariant.Double,    self.sb_fric,   18, None],
            ["LENGTH",      QVariant.Double,    self.sb_length, 19, None],
            ["CIRC",        QVariant.Int,       self.cb_circ,   20, 16  ],
            ["AL",          QVariant.Int,       self.cb_auto_l, 26, None],
            ["AZ",          QVariant.Int,       self.cb_auto_z, 27, 21  ],
            ["AA",          QVariant.Int,       self.cb_auto_a, 25, 13  ],
            ["Remarques",   QVariant.String,    None,           29, None],
        ]

        self.is_opening = True

        self.mdl_lay_culv = QStandardItemModel()
        self.mdl_lay_mesh = QStandardItemModel()
        self.mdl_mesh_dataset = QStandardItemModel()
        self.mdl_mesh_time = QStandardItemModel()

        self.cb_lay_culv.setModel(self.mdl_lay_culv)
        self.cb_lay_mesh.setModel(self.mdl_lay_mesh)
        self.cb_dataset_mesh.setModel(self.mdl_mesh_dataset)
        self.cb_time_mesh.setModel(self.mdl_mesh_time)

        # self.clickTool = QgsMapToolEmitPoint(iface.mapCanvas())
        # self.clickTool.canvasClicked.connect(self.postSelectCulvert)

        QgsProject.instance().layersAdded.connect(self.addLayers)
        QgsProject.instance().layersRemoved.connect(self.removeLayers)

        self.cb_lay_culv.currentIndexChanged.connect(self.culv_lay_changed)
        self.cb_lay_mesh.currentIndexChanged.connect(self.mesh_lay_changed)
        self.cb_dataset_mesh.currentIndexChanged.connect(self.mesh_dataset_changed)
        self.cb_time_mesh.currentIndexChanged.connect(self.mesh_time_changed)
        self.btn_new_culv_file.clicked.connect(self.new_file)
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

        for lay in QgsProject.instance().mapLayers().values():
            self.analyse_layer(lay)

        if self.mdl_lay_culv.rowCount() == 0:
            self.culv_lay_changed()

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
        if lay.type() == QgsMapLayerType.VectorLayer:
            flds = [f.name() for f in lay.fields()]
            if all(elem in flds for elem in [fc[0] for fc in self.culv_flds]):
                itm = QStandardItem()
                itm.setData(lay.name(), 0)
                itm.setData(lay.id(), 32)
                self.mdl_lay_culv.appendRow(itm)
                self.mdl_lay_culv.sort(0)
        if lay.type() == QgsMapLayerType.MeshLayer:
            itm = QStandardItem()
            itm.setData(lay.name(), 0)
            itm.setData(lay.id(), 32)
            self.mdl_lay_mesh.appendRow(itm)
            self.mdl_lay_mesh.sort(0)

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
        lay_id = self.cb_lay_mesh.currentData(32)
        if self.lay_mesh_id == lay_id:
            return

        if lay_id:
            self.lay_mesh = QgsProject.instance().mapLayer(lay_id)
            self.lay_mesh_id = lay_id
            self.cb_dataset_mesh.setEnabled(True)
            self.cb_time_mesh.setEnabled(True)
        else:
            self.lay_mesh = None
            self.lay_mesh_id = None
            self.native_mesh = None
            self.vertices = None
            self.faces = None
            self.cb_dataset_mesh.setEnabled(False)
            self.cb_time_mesh.setEnabled(False)
        self.cur_mesh_changed()

    def cur_mesh_changed(self):
        self.mdl_mesh_dataset.clear()
        if self.lay_mesh is not None:
            write_log("Current mesh changed : {}".format(self.lay_mesh.name()))
            self.native_mesh = QgsMesh()
            self.lay_mesh.dataProvider().populateMesh(self.native_mesh)
            self.faces = self.create_faces_spatial_index()

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
            write_log("Current mesh dataset changed : {}".format(self.cb_dataset_mesh.currentText()))
            mesh_prov = self.lay_mesh.dataProvider()
            for i in range(mesh_prov.datasetCount(self.cur_mesh_dataset)):
                itm = QStandardItem()
                itm.setData(mesh_prov.datasetMetadata(QgsMeshDatasetIndex(self.cur_mesh_dataset, i)).time(), 0)
                itm.setData(i, 32)
                self.mdl_mesh_time.appendRow(itm)

    def mesh_time_changed(self):
        self.cur_mesh_time = self.cb_time_mesh.currentData(32)
        if self.cur_mesh_time is not None:
            write_log("Current mesh timestep changed : {}".format(self.cb_time_mesh.currentText()))
            self.vertices = self.create_vertices_spatial_index()
            if self.lay_culv is not None and self.is_opening is False:
                self.update_all_n()
                if (
                    QMessageBox.question(
                        self,
                        "Automatic Z Update",
                        "Mesh parameters have been changed.\n" "Update culvert features with Automatic Z checked ?",
                        QMessageBox.Cancel | QMessageBox.Ok,
                    )
                    == QMessageBox.Ok
                ):
                    self.update_all_auto_z()

    def create_vertices_spatial_index(self):
        if self.lay_mesh:
            write_log("Creation of vertices spatial index ...")
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

            write_log("Vertices spatial index created in {} sec".format(round(time.time() - t0, 1)))
            return spindex
        else:
            return None

    def create_faces_spatial_index(self):
        if self.lay_mesh:
            write_log("Creation of faces spatial index ...")
            t0 = time.time()
            spindex = QgsSpatialIndex()

            count = self.native_mesh.faceCount()
            offset = 0
            batch_size = 10
            while offset < count:
                lst_ft = list()
                iterations = min(batch_size, count - offset)
                for i in range(iterations):
                    ft = QgsFeature()
                    polygon = self.face_to_poly(offset + i)
                    ft.setGeometry(QgsGeometry(polygon))
                    ft.setId(offset + i)
                    lst_ft.append(ft)
                spindex.addFeatures(lst_ft)
                offset += iterations

            write_log("Faces spatial index created in {} sec".format(round(time.time() - t0, 1)))
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
            path, srs = dlg.cur_shp, dlg.cur_crs

        layerFields = QgsFields()
        for fld in self.culv_flds:
            layerFields.append(QgsField(fld[0], fld[1]))

        tmp_lay = QgsVectorLayer("MultiLineString?crs=" + str(srs.authid()), "", "memory")
        pr = tmp_lay.dataProvider()
        pr.addAttributes(layerFields)
        tmp_lay.updateFields()
        QgsVectorFileWriter.writeAsVectorFormat(tmp_lay, path, None, destCRS=srs, driverName="ESRI Shapefile")

        shp_lay = QgsVectorLayer(path, os.path.basename(path).rsplit(".", 1)[0], "ogr")
        shp_lay.loadNamedStyle(self.file_culv_style)
        shp_lay.saveDefaultStyle()
        QgsProject.instance().addMapLayer(shp_lay)
        self.cb_lay_culv.setCurrentIndex(self.cb_lay_culv.findData(shp_lay.id(), 32))

    def culv_lay_changed(self):
        lay_id = self.cb_lay_culv.currentData(32)
        self.cur_culv_id = None
        if lay_id:
            self.lay_culv = QgsProject.instance().mapLayer(lay_id)
            self.lay_culv.selectionChanged.connect(self.cur_culv_changed)
            self.lay_culv.editingStarted.connect(self.cur_culv_changed)
            self.lay_culv.editingStopped.connect(self.cur_culv_changed)
            if self.lay_mesh is not None and self.is_opening is False:
                self.update_all_n()
                if (
                    QMessageBox.question(
                        self,
                        "Automatic Z Update",
                        "Culvert culvert layer has been changed.\n"
                        "Update culvert features with Automatic Z checked ?",
                        QMessageBox.Cancel | QMessageBox.Ok)
                    == QMessageBox.Ok):
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
                    self.gb_cur_culv.setTitle("No culvert selected")
                else:
                    self.gb_cur_culv.setTitle("More than one culvert selected")
                self.clear_info()
                self.gb_cur_culv.setEnabled(False)
            else:
                self.gb_cur_culv.setTitle("Selected culvert informations")
                self.fill_info()
                self.gb_cur_culv.setEnabled(not self.lay_culv.isEditable())
        else:
            self.gb_cur_culv.setTitle("No culvert layer selected")
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
            if val == None:
                ctrl.setValue(0.0)
            else:
                ctrl.setValue(val)
        elif isinstance(ctrl, QComboBox):
            idx = to_integer(val)
            if idx == None:
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
                    (z1, z2), err = self.recup_z_from_mesh(ft)
                    (n1, n2), errn = self.recup_n_from_mesh(ft)
                    print((n1, n2), err,(z1, z2))
                    print(self.recup_z_from_mesh(ft))
                    print(self.recup_n_from_mesh(ft))
                    if err or errn:
                        write_log("Error on Z calculation : {}".format(err), 2)
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
                write_log("Error on N calculation : {}".format(err), 2)
                return

        self.lay_culv.dataProvider().changeAttributeValues(attrs)
        self.lay_culv.commitChanges()
        if log:
            write_log("N values updated", 0)

    def update_all_auto_z(self):
        attrs = dict()
        for ft in self.lay_culv.getFeatures():
            if ft["AZ"] == 2:
                (z1, z2), err = self.recup_z_from_mesh(ft)
                if not err:
                    attrs[ft.id()] = {ft.fieldNameIndex("z1"): z1, ft.fieldNameIndex("z2"): z2}
                else:
                    write_log("Error on Z calculation : {}".format(err), 2)
                    return

        self.lay_culv.dataProvider().changeAttributeValues(attrs)
        self.lay_culv.commitChanges()
        write_log("Z values updated", 0)
        self.display_culv_info()

    def recup_n_from_mesh(self, ft):
        err, n = None, [None, None]
        pts = ft.geometry().asMultiPolyline()
        for p in [0, -1]:
            pt = pts[p][p]
            idx, err = find_nearest_node(self, pt)
            n[p * -1] = idx + 1

        return n, err

    def recup_z_from_mesh(self, ft):
        err, z = None, [None, None]
        pts = ft.geometry().asMultiPolyline()
        for p in [0, -1]:
             pt = pts[p][p]
             z[p * -1], err = find_z_from_mesh(self, pt)

        return z, err

    ######################################################################################
    #                                                                                    #
    #                                       EXPORT                                       #
    #                                                                                    #
    ######################################################################################

    def verif_culvert(self):
        if self.lay_culv:
            self.update_all_n(log=False)
            ids = self.verif_culvert_validity()
            if not ids:
                write_log("All culverts are valid", 0)
            else:
                for id in ids:
                    write_log("{} : {}".format(*id), 2)

    def create_file(self):
        if self.lay_culv:
            ids = self.verif_culvert_validity()
            if ids:
                write_log("File creation is not possible, some culverts are not valid", 2)
                return
            else:
                try:
                    culv_file_name, _ = QFileDialog.getSaveFileName(self, "Shapefile", "", "Text File (*.txt)")
                    if culv_file_name != "":
                        elem_width = 12
                        nb_culv = 0

                        culv_file = open(culv_file_name, "w")
                        for ft in self.lay_culv.getFeatures():
                            nb_culv += 1

                        if self.software_select == 0: # Telemac
                            culv_file.write("Relaxation" + str("  ") + "Culvert count" + str("\n"))
                            culv_file.write("0.1" + str("         ") + str(nb_culv) + str("\n"))
                            idx_out = 3
                        elif self.software_select == 1: #Uhaina
                            culv_file.write("Culvert count" + str("\n"))
                            culv_file.write(str(nb_culv) + str("\n"))
                            idx_out = 4
                        else:
                            write_log("Unknown software", 2)

                        self.culv_flds_srtd = sorted(self.culv_flds, key=lambda x: (x[idx_out] is None, x[idx_out]))

                        txt = ""
                        for fld in self.culv_flds_srtd:
                            if fld[idx_out] is not None:
                                if (self.software_select == 1) & (fld[0] in ["z1", "z2"]): # Uhaina Only
                                    if fld[0] == "z1":
                                        txt += convertToText("x1", elem_width)
                                        txt += convertToText("y1", elem_width)
                                    else:
                                        txt += convertToText("x2", elem_width)
                                        txt += convertToText("y2", elem_width)
                                txt += convertToText(fld[0], elem_width)
                        culv_file.write(txt + str("\n"))

                        for ft in self.lay_culv.getFeatures():
                            txt = ""
                            pts = ft.geometry().asMultiPolyline()
                            p1 = pts[0][0]
                            p2 = pts[-1][-1]
                            x1 = QgsPointXY(p1).x()
                            y1 = QgsPointXY(p1).y()
                            x2 = QgsPointXY(p2).x()
                            y2 = QgsPointXY(p2).y()

                            for fld in self.culv_flds_srtd:
                                if fld[idx_out] is not None:
                                    if fld[0] in ["CIRC", "AA", "AL", "AZ"]:
                                        if ft[fld[0]] == 0:
                                            txt += convertToText("0", elem_width)
                                        else:
                                            txt += convertToText("1", elem_width)
                                    elif (self.software_select == 1) & (fld[0] in ["z1", "z2"]): # Uhaina Only
                                        if fld[0] == "z1":
                                            txt += convertToText(x1, elem_width)
                                            txt += convertToText(y1, elem_width)
                                            txt += convertToText(ft[fld[0]], elem_width)
                                        else:
                                            txt += convertToText(x2, elem_width)
                                            txt += convertToText(y2, elem_width)
                                            txt += convertToText(ft[fld[0]], elem_width)
                                    else:
                                        if ft[fld[0]] or ft[fld[0]] == 0.0:
                                            txt += convertToText(ft[fld[0]], elem_width)
                                        else:
                                            txt += convertToText("0", elem_width)
                            culv_file.write(txt + str("\n"))

                        culv_file.close()
                        write_log("Culvert File Created", 0)

                except Exception as e:
                    write_log("Error on File Creation", 2)
                    pass

    def verif_culvert_validity(self):
        selectedids = []
        for ft in self.lay_culv.getFeatures():
            if ft["NAME"] in [None, ""]:
                ft_name = "Nameless culvert"
            else:
                ft_name = ft["NAME"]

            if (ft["N1"] == None) or (ft["N2"] == None):
                selectedids.append([ft_name, "Culvert extremity is out of the mesh extent."])

            for fld in self.culv_flds:
                if fld[0] not in ["NAME", "Remarques"]:
                    if fld[2]:
                        if fld[1] == QVariant.String:
                            if (ft[fld[0]] == None) or not isinstance(ft[fld[0]], str):
                                selectedids.append([ft_name, "{} value is not correct.".format(fld[0])])
                        elif fld[1] == QVariant.Double:
                            if (ft[fld[0]] == None) or not isinstance(ft[fld[0]], float):
                                selectedids.append([ft_name, "{} value is not correct.".format(fld[0])])
                        elif fld[1] == QVariant.Int:
                            if (ft[fld[0]] == None) or not isinstance(ft[fld[0]], int):
                                selectedids.append([ft_name, "{} value is not correct.".format(fld[0])])

        return selectedids


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


def convertToText(var, length):
    if isinstance(var, float):
        floatmodif = format(var, ".3f")
        long = len(str(floatmodif))
        return (length - long) * " " + str(floatmodif)
    elif isinstance(var, str):
        return (length - len(var)) * " " + var
    elif isinstance(var, int):
        long = len(str(var))
        return (length - long) * " " + str(var)

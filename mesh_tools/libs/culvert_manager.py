# -*- coding: utf-8 -*-

"""
/***************************************************************************
 CulvertManager
                                 A QGIS plugin
 Tools for management of Data on mesh (Telemac, Uhaina)
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-03-24
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Artelia/BRGM/ISL
        email                : a@a
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import time

from contextlib import suppress

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
    QgsMapLayerProxyModel,
    QgsMapLayerType,
    QgsMesh,
    QgsMeshDatasetIndex,
    QgsPointXY,
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
    QSpinBox,
)

from ..mesh_tools_dockwidget import MeshToolsDockWidget
from .create_shp_dlg import dlg_create_shapefile
from .import_culvert_file_dlg import dlg_import_culvert_file
from .MeshUtils import MeshUtils

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), "..", "ui", "culvert_manager.ui"))


class CulvertManager(MeshToolsDockWidget, FORM_CLASS):
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
        self.lay_mesh_xform = None
        self.lay_culv = None
        self.lay_culv_xform = None

        self.native_mesh = None
        self.vertices = None

        self.cur_culv_id = None
        self.cur_mesh_dataset = None
        self.cur_mesh_time = None

        self.software_select = 0

        # fmt: off
        # Col4 - Index for Telemac
        # Col5 - Index for Uhaina
        self.culv_flds = [
            ["NAME",        QVariant.String,    self.txt_name,  28, 23  ],
            ["N1",          QVariant.Int,       None,           0,  None],
            ["N2",          QVariant.Int,       None,           1,  None],
            ["CE1",         QVariant.Double,    self.sb_ce1,    2, 6    ],
            ["CE2",         QVariant.Double,    self.sb_ce2,    3, 7    ],
            ["CS1",         QVariant.Double,    self.sb_cs1,    4, 8    ],
            ["CS2",         QVariant.Double,    self.sb_cs2,    5, 9    ],
            ["LARG",        QVariant.Double,    self.sb_larg,   6, 17   ],
            ["HAUT",        QVariant.Double,    self.sb_haut1,  7, 18   ],
            ["CLAP",        QVariant.String,    self.cb_clapet, 8, 20   ],
            ["L12",         QVariant.Double,    self.sb_l12,    9, 10   ],
            ["Z1",          QVariant.Double,    self.sb_z1,     10, 2   ],
            ["Z2",          QVariant.Double,    self.sb_z2,     11, 5   ],
            ["CV",          QVariant.Double,    self.sb_cv,     12, None],
            ["C56",         QVariant.Double,    self.sb_c56,    13, None],
            ["CV5",         QVariant.Double,    self.sb_cv5,    14, None],
            ["C5",          QVariant.Double,    self.sb_c5,     15, None],
            ["CT",          QVariant.Double,    self.sb_ct,     16, None],
            ["HAUT2",       QVariant.Double,    self.sb_haut2,  17, 19  ],
            ["FRIC",        QVariant.Double,    self.sb_fric,   18, None],
            ["LENGTH",      QVariant.Double,    self.sb_length, 19, None],
            ["CIRC",        QVariant.Int,       self.cb_circ,   20, 16  ],
            ["d1",          QVariant.Double,    self.sb_d1,     21, 11  ],
            ["d2",          QVariant.Double,    self.sb_d2,     22, 12  ],
            ["a1",          QVariant.Double,    self.sb_a1,     23, 14  ],
            ["a2",          QVariant.Double,    self.sb_a2,     24, 15  ],
            ["AA",          QVariant.Int,       self.cb_auto_a, 25, 13  ],
            ["NB_in_//",    QVariant.Int,       self.sb_nbre,   None, 21  ],
            ["AL",          QVariant.Int,       self.cb_auto_l, 26, None],
            ["AZ",          QVariant.Int,       self.cb_auto_z, 27, 22  ]
        ]
        # fmt: on

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
                if isinstance(ctrl, QDoubleSpinBox) or isinstance(ctrl, QSpinBox):
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

    def valid_mesh_culv(self):
        if self.lay_mesh_xform is not None and self.lay_culv_xform is not None:
            self.gb_output.setEnabled(True)
            self.btn_verif.setEnabled(True)
            self.frm_relax.setEnabled(True)
            self.gb_cur_culv.setEnabled(True)
            self.frm_culv_tools.setEnabled(True)
        else:
            self.gb_output.setEnabled(False)
            self.btn_verif.setEnabled(False)
            self.frm_relax.setEnabled(False)
            self.gb_cur_culv.setEnabled(False)
            self.frm_culv_tools.setEnabled(False)
        self.cur_culv_changed()

    def clean(self):
        self.project.layersAdded.disconnect(self.addLayers)
        self.project.layersRemoved.disconnect(self.removeLayers)

        self.lay_mesh.crsChanged.disconnect(self.cur_mesh_changed)
        self.lay_culv.crsChanged.disconnect(self.culv_lay_changed)

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
        for fld in self.culv_flds:
            ctrl = fld[2]
            if ctrl is not None:
                ctrl.setEnabled(fld[self.software_select + 3] is not None)

    ######################################################################################
    #                                                                                    #
    #                                     MESH LAYER                                     #
    #                                                                                    #
    ######################################################################################

    def mesh_lay_changed(self):
        with suppress(AttributeError, RuntimeError, TypeError):
            self.lay_mesh.crsChanged.disconnect()

        self.lay_mesh = self.cb_lay_mesh.currentLayer()

        if self.lay_mesh:
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
        self.mdl_mesh_time.clear()
        if self.lay_mesh is None:
            return

        self.writeInfo(self.tr("Current mesh changed : {}").format(self.lay_mesh.name()))
        self.native_mesh = QgsMesh()
        self.lay_mesh.dataProvider().populateMesh(self.native_mesh)

        self.lay_mesh.crsChanged.connect(self.cur_mesh_changed)
        if self.lay_mesh.crs().isValid():
            self.lay_mesh_xform = QgsCoordinateTransform(
                self.lay_mesh.crs(), self.canvas.mapSettings().destinationCrs(), self.project
            )
        else:
            self.lay_mesh_xform = None
            self.valid_mesh_culv()
            self.writeError(self.tr("Mesh CRS is not valid."))
            return

        self.valid_mesh_culv()

        self.writeInfo(self.tr("Creation of vertices spatial index..."))
        t0 = time.time()
        self.vertices = MeshUtils.createVerticesSpatialIndex(self.native_mesh, self.lay_mesh_xform)
        self.writeInfo(self.tr("Vertices spatial index created in {} sec.").format(round(time.time() - t0, 1)))

        self.cb_dataset_mesh.blockSignals(True)
        mesh_prov = self.lay_mesh.dataProvider()
        indexFound = None
        for i in range(mesh_prov.datasetGroupCount()):
            itm = QStandardItem()
            datasetName = mesh_prov.datasetGroupMetadata(i).name()
            itm.setData(datasetName, 0)
            itm.setData(i, 32)
            self.mdl_mesh_dataset.appendRow(itm)

            if any(name in datasetName for name in ["fond", "bottom"]):
                indexFound = i

        if indexFound is not None:
            self.cb_dataset_mesh.setCurrentIndex(indexFound)

        self.cb_dataset_mesh.blockSignals(False)
        self.mesh_dataset_changed()

    def mesh_dataset_changed(self):
        self.mdl_mesh_time.clear()
        self.cur_mesh_dataset = self.cb_dataset_mesh.currentData(32)
        if self.cur_mesh_dataset is not None:
            self.writeInfo(self.tr("Current mesh dataset changed : {}").format(self.cb_dataset_mesh.currentText()))
            mesh_prov = self.lay_mesh.dataProvider()
            for i in range(mesh_prov.datasetCount(self.cur_mesh_dataset)):
                itm = QStandardItem()
                itm.setData(mesh_prov.datasetMetadata(QgsMeshDatasetIndex(self.cur_mesh_dataset, i)).time(), 0)
                itm.setData(i, 32)
                self.mdl_mesh_time.appendRow(itm)

        tmpSettings = self.lay_mesh.rendererSettings()
        tmpSettings.setActiveScalarDatasetGroup(self.cur_mesh_dataset)
        self.lay_mesh.setRendererSettings(tmpSettings)

    def mesh_time_changed(self):
        self.cur_mesh_time = self.cb_time_mesh.currentData(32)
        if self.cur_mesh_time is not None:
            self.writeInfo(self.tr("Current mesh timestep changed : {}").format(self.cb_time_mesh.currentText()))
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

    ######################################################################################
    #                                                                                    #
    #                                    CULVERT LAYER                                   #
    #                                                                                    #
    ######################################################################################

    def new_file(self):
        srs_mesh = None
        path = ""
        if self.lay_mesh:
            srs_mesh = self.lay_mesh.crs()
        dlg = dlg_create_shapefile(self.tr("culvert"), srs_mesh, self)
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

        layerDriver = GdalUtils.getVectorDriverFromFileName(path)

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = layerDriver
        options.fileEncoding = "utf-8"
        QgsVectorFileWriter.writeAsVectorFormatV2(
            layer=tmp_lay,
            fileName=path,
            transformContext=QgsCoordinateTransformContext(),
            options=options,
        )

        shp_lay = QgsVectorLayer(path, os.path.basename(path).rsplit(".", 1)[0], "ogr")
        shp_lay.setCrs(crs)
        shp_lay.loadNamedStyle(self.file_culv_style)
        shp_lay.saveDefaultStyle()
        self.project.addMapLayer(shp_lay)
        self.cb_lay_culv.setCurrentIndex(self.cb_lay_culv.findData(shp_lay.id(), 32))

    def culv_lay_changed(self):
        with suppress(AttributeError, RuntimeError, TypeError):
            self.lay_culv.crsChanged.disconnect()

        lay_id = self.cb_lay_culv.currentData(32)
        self.cur_culv_id = None
        if lay_id:
            self.lay_culv = self.project.mapLayer(lay_id)
            self.lay_culv.selectionChanged.connect(self.cur_culv_changed)
            self.lay_culv.editingStarted.connect(self.cur_culv_changed)
            self.lay_culv.editingStopped.connect(self.cur_culv_changed)
            self.lay_culv.crsChanged.connect(self.culv_lay_changed)

            if self.lay_culv.crs().isValid():
                self.lay_culv_xform = QgsCoordinateTransform(
                    self.lay_culv.crs(), self.canvas.mapSettings().destinationCrs(), self.project
                )
            else:
                self.lay_culv_xform = None
                self.writeWarning(self.tr("Culvert layer CRS is not valid."))

            if self.lay_mesh is not None and self.is_opening is False:
                self.update_all_n()
                if (
                    QMessageBox.question(
                        self,
                        self.tr("Automatic Z Update"),
                        self.tr("Culvert layer has been changed.\nUpdate culvert features with Automatic Z checked ?"),
                        QMessageBox.Cancel | QMessageBox.Ok,
                    )
                    == QMessageBox.Ok
                ):
                    self.update_all_auto_z()
        else:
            self.lay_culv = None
            self.lay_culv_xform = None
        self.valid_mesh_culv()

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
                elif isinstance(ctrl, QSpinBox):
                    ctrl.setValue(1)
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
        elif isinstance(ctrl, QSpinBox):
            if val is None:
                ctrl.setValue(1)
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
                if isinstance(ctrl, QDoubleSpinBox) or isinstance(ctrl, QSpinBox):
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
                (n1, n2), err = MeshUtils.n1n2FromFeature(self.lay_mesh, self.vertices, ft, self.lay_culv_xform)

                if err is not None:
                    self.writeError(self.tr("Error on Z calculation : {}").format(err))
                    return

                attrs = {self.cur_culv_id: {ft.fieldNameIndex("N1"): n1, ft.fieldNameIndex("N2"): n2}}

                if self.cb_auto_z.isChecked():
                    z1 = MeshUtils.zFromN(
                        self.lay_mesh, QgsMeshDatasetIndex(self.cur_mesh_dataset, self.cur_mesh_time), n1
                    )
                    z2 = MeshUtils.zFromN(
                        self.lay_mesh, QgsMeshDatasetIndex(self.cur_mesh_dataset, self.cur_mesh_time), n2
                    )

                    self.sb_z1.setValue(z1)
                    self.sb_z2.setValue(z2)

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
                elif isinstance(ctrl, QSpinBox):
                    ctrl.setValue(1)
                elif isinstance(ctrl, QComboBox):
                    ctrl.setCurrentIndex(0)
                elif isinstance(ctrl, QCheckBox):
                    ctrl.setCheckState(0)

    def update_all_n(self, log=True):
        attrs = dict()
        success = True
        for ft in self.lay_culv.getFeatures():
            (n1, n2), err = MeshUtils.n1n2FromFeature(self.lay_mesh, self.vertices, ft, self.lay_culv_xform)

            if err is not None:
                success = False
                n1 = NULL
                n2 = NULL
                if log:
                    self.writeError(self.tr("Error on N calculation : {}").format(err))

            attrs[ft.id()] = {ft.fieldNameIndex("N1"): n1, ft.fieldNameIndex("N2"): n2}

        self.lay_culv.dataProvider().changeAttributeValues(attrs)
        self.lay_culv.commitChanges()
        if log and success:
            self.writeSuccess(self.tr("N values updated"))

    def update_all_auto_z(self):
        attrs = dict()
        for ft in self.lay_culv.getFeatures():
            if ft["AZ"] != 1:
                continue

            (n1, n2), err = MeshUtils.n1n2FromFeature(self.lay_mesh, self.vertices, ft, self.lay_culv_xform)
            if err is None:
                z1 = MeshUtils.zFromN(self.lay_mesh, QgsMeshDatasetIndex(self.cur_mesh_dataset, self.cur_mesh_time), n1)
                z2 = MeshUtils.zFromN(self.lay_mesh, QgsMeshDatasetIndex(self.cur_mesh_dataset, self.cur_mesh_time), n2)
                attrs[ft.id()] = {ft.fieldNameIndex("Z1"): z1, ft.fieldNameIndex("Z2"): z2}
            else:
                self.writeError(self.tr("Error on Z calculation : {}").format(err))
                return

        self.lay_culv.dataProvider().changeAttributeValues(attrs)
        self.lay_culv.commitChanges()
        self.writeSuccess(self.tr("Z values updated"))
        self.display_culv_info()

    ######################################################################################
    #                                                                                    #
    #                                       EXPORT                                       #
    #                                                                                    #
    ######################################################################################

    def verif_culvert(self):
        if not self.lay_culv:
            return

        self.update_all_n(log=False)
        invalidIds = self.verif_culvert_validity()
        if not invalidIds:
            self.writeSuccess(self.tr("All culverts are valid"))
        else:
            for invalidId in invalidIds:
                self.writeError("{} : {}".format(*invalidId))

    def create_file(self):
        if not self.lay_culv:
            return

        invalidIds = self.verif_culvert_validity()
        if invalidIds:
            self.writeError(self.tr("File creation is not possible, some culverts are not valid"))
            return

        culv_file_name, _ = QFileDialog.getSaveFileName(self, self.tr("Culvert file"), "", self.tr("Text File (*.txt)"))

        if not culv_file_name:
            return

        nb_culv = self.lay_culv.featureCount()
        relax = round(self.sb_relax.value(), 2)

        with open(culv_file_name, "w", encoding="utf-8") as culv_file:
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
                if (self.software_select == 1) and (fld[0] in ["Z1", "Z2"]):  # Uhaina Only
                    txt += f"X{fld[0][1]}\t"
                    txt += f"Y{fld[0][1]}\t"

                txt += f"{fld[0]}\t"
            txt += f"{culv_flds_srtd[-1][0]}\n"
            culv_file.write(txt)

            for ft in self.lay_culv.getFeatures():
                txt = ""
                if self.software_select == 1:  # Uhaina Only
                    pts = ft.geometry().asMultiPolyline()
                    pt1 = QgsPointXY(pts[0][0])
                    pt2 = QgsPointXY(pts[-1][-1])

                    # pt1 and pt2 need to be transformed into mesh CRS
                    pt1 = self.lay_mesh_xform.transform(
                        self.lay_culv_xform.transform(pt1, QgsCoordinateTransform.ReverseTransform),
                        QgsCoordinateTransform.ReverseTransform,
                    )
                    pt2 = self.lay_mesh_xform.transform(
                        self.lay_culv_xform.transform(pt2, QgsCoordinateTransform.ReverseTransform),
                        QgsCoordinateTransform.ReverseTransform,
                    )

                for fld in culv_flds_srtd[:-1]:
                    if (self.software_select == 1) and (fld[0] in ["Z1", "Z2"]):
                        if fld[0] == "Z1":
                            txt += f"{pt1.x()}\t{pt1.y()}\t"
                        elif fld[0] == "Z2":
                            txt += f"{pt2.x()}\t{pt2.y()}\t"

                    txt += f"{ft[fld[0]]}\t"
                txt += f"{ft[culv_flds_srtd[-1][0]]}\n"
                culv_file.write(txt.replace("NULL", " "))

            self.writeSuccess(self.tr("Culvert File Created"))
            return

        self.writeError(self.tr("Error during culvert file creation"))

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
                try:
                    if values[i] == NULL:
                        dico[h] = ""
                    elif values[i].isdigit():
                        dico[h] = float(values[i])
                    else:
                        dico[h] = values[i]
                # Usually means that NAME is empty
                except IndexError:
                    dico[h] = ""
            return dico

        if not self.lay_mesh:
            self.writeError(self.tr("Import a mesh first."))
            return

        if self.lay_mesh.crs().isValid():
            mesh_crs = self.lay_mesh.crs()
        else:
            mesh_crs = self.project.crs()

        culv_flds = [x[0] for x in self.culv_flds]
        dlg = dlg_import_culvert_file(culv_flds, mesh_crs, self)
        dlg.setWindowModality(2)
        if dlg.exec_():
            items = dlg.items
            self.cb_software_select.setCurrentIndex(dlg.cb_soft.currentIndex())
            txt_path = dlg.text_file.filePath()
            layer_path = dlg.layer_file.filePath()
            layer_crs = dlg.layer_crs.crs()
            culv_xform = QgsCoordinateTransform(layer_crs, self.canvas.mapSettings().destinationCrs(), self.project)
            layerDriver = GdalUtils.getVectorDriverFromFileName(layer_path)
        else:
            return

        if not txt_path:
            return

        layerFields = QgsFields()
        for fld in self.culv_flds:
            layerFields.append(QgsField(fld[0], fld[1]))

        layer = QgsVectorLayer(f"MultiLineString?crs={mesh_crs.authid()}", self.tr("Culverts"), "memory")
        pr = layer.dataProvider()
        pr.addAttributes(layerFields)
        layer.updateFields()
        layer.startEditing()

        with open(txt_path, "r") as txt_file:
            # 1st line is comment
            txt_file.readline()
            # Relaxation and number of culverts
            relax, nb_culvert = get_values(txt_file.readline())
            self.sb_relax.setValue(float(relax))
            # Retrieve headers
            headers = get_values(txt_file.readline())

            for i in range(int(nb_culvert)):
                lineValues = get_values(txt_file.readline())
                if lineValues == [""]:
                    continue

                values = asDict(headers, lineValues)

                fet = QgsFeature()

                n1 = int(values[items["n1"][1]])
                n2 = int(values[items["n2"][1]])
                point_n1, err1 = MeshUtils.xyFromN(self.native_mesh, n1, self.lay_mesh_xform, culv_xform)
                point_n2, err2 = MeshUtils.xyFromN(self.native_mesh, n2, self.lay_mesh_xform, culv_xform)

                if err1 is not None or err2 is not None:
                    err = " ".join(filter(None, (err1, err2)))
                    self.writeError(
                        self.tr("Error when importing culvert {i} with error(s) : {err}").format(i=i, err=err)
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
            self.writeError(self.tr("Error during culvert file creation"))
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
            layer.setCrs(layer_crs)
            layer.loadNamedStyle(self.file_culv_style)
            layer.saveDefaultStyle()
            self.project.addMapLayer(layer)
            self.cb_lay_culv.setCurrentIndex(self.cb_lay_culv.findData(layer.id(), 32))
        else:
            self.writeError(self.tr("Created culvert layer is not valid."))


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

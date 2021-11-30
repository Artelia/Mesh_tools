# -*- coding: utf-8 -*-

# This file is dedicated to store functions linked to the mesh
#   - Find the nearest node of a point
#   - Check if a point in inside a mesh
#   - ...
#

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

def pt_within_mesh(self, pt):
    within = False
    idxs = self.faces.intersects(QgsGeometry.fromPointXY(pt).boundingBox())
    for idx in idxs:
        f = QgsGeometry(self.face_to_poly(idx))
        if f.contains(pt):
            within = True
            break
    return within

def find_nearest_node(self, point):
    err, n = None, None
    if self.lay_mesh:
        mesh_crs = self.lay_mesh.crs()
        if mesh_crs.isValid():
            shp_crs = self.lay_culv.sourceCrs()
            xform = QgsCoordinateTransform(shp_crs, mesh_crs, QgsProject.instance())
            x_pt = xform.transform(point)
            if pt_within_mesh(self, x_pt):
                idx = self.vertices.nearestNeighbor(x_pt, 1)[0]
                n = idx
            else:
                n = None
        else:
            err = "CRS defined for mesh layer is not valid"
    else:
        err = "No mesh layer selected"

    return n, err

def find_z_from_mesh(self, point):
    err, z = None, None
    if self.lay_mesh:
        mesh_crs = self.lay_mesh.crs()
        if mesh_crs.isValid():
            shp_crs = self.lay_culv.sourceCrs()
            xform = QgsCoordinateTransform(shp_crs, mesh_crs, QgsProject.instance())
            x_pt = xform.transform(point)
            print("eeee",pt_within_mesh(self, x_pt))

            if pt_within_mesh(self, x_pt):
                idx, err = find_nearest_node(self, x_pt)
                print(idx)
                dset_val = self.lay_mesh.dataProvider().datasetValues(
                    QgsMeshDatasetIndex(self.cur_mesh_dataset, self.cur_mesh_time), idx, 1
                )
                print(dset_val.value(0).scalar())
                z = round(dset_val.value(0).scalar(), 2)
            else:
                z = 0.0
        else:
            err = "CRS defined for mesh layer is not valid"
    else:
        err = "No mesh layer selected"

    return z, err

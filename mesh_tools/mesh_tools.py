# -*- coding: utf-8 -*-
"""
/***************************************************************************
 MeshTools
                                 A QGIS plugin
 Tools for management of Data on mesh (Telemac, Uhaina)
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-03-24
        git sha              : $Format:%H$
        copyright            : (C) 2021 by APn/Artelia
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
import os.path

from qgis.core import Qgis
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QToolBar

from .libs.culvert_manager import CulvertManager
from .libs.mesh_quality import MeshQuality

# Import the code for the DockWidget
from .mesh_tools_dockwidget import MeshToolDockWidget

# Initialize Qt resources from file resources.py
# from .resources import *


class MeshTools:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        self.path_icon = os.path.join(os.path.dirname(__file__), "icons/")

        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(self.plugin_dir, "i18n", "MeshTools_{}.qm".format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&Mesh Tools")
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = QToolBar()
        # self.toolbar = self.iface.addToolBar(u'MeshTools')
        # self.toolbar.setObjectName(u'MeshTools')

        self.pluginIsActive = False
        self.dockwidget = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("MeshTools", message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=False,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        self.add_action(
            icon_path,
            text=self.tr("Culvert Manager"),
            callback=lambda: self.run(1),
            parent=self.iface.mainWindow(),
        )
        if Qgis.versionInt() >= 32200:
            self.add_action(
                icon_path,
                text=self.tr("Mesh Quality Analysis"),
                callback=lambda: self.run(2),
                parent=self.iface.mainWindow(),
            )

    # --------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        self.dockwidget = None

        self.pluginIsActive = False

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        if self.dockwidget:
            self.dockwidget.close()

        for action in self.actions:
            self.iface.removePluginMenu(self.tr("&Mesh Tools"), action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    # --------------------------------------------------------------------------

    def run(self, tool):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

        if self.dockwidget:
            print(self.dockwidget.close())

        if tool == 1:
            self.dockwidget = CulvertManager()
            self.dockwidget.setWindowTitle(self.tr("Culvert Manager"))
        elif tool == 2:
            self.dockwidget = MeshQuality()
            self.dockwidget.setWindowTitle(self.tr("Telemac - Mesh Quality Analysis"))
        else:
            self.dockwidget = TelemacToolDockWidget()
            self.dockwidget.setWindowTitle(self.tr("MeshTool - Error"))

        self.dockwidget.closingPlugin.connect(self.onClosePlugin)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
        self.dockwidget.show()

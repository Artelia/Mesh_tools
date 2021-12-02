# -*- coding: utf-8 -*-

# This file is dedicated to store log functions
#

from datetime import datetime

from qgis.PyQt.QtGui import QColor, QFont

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

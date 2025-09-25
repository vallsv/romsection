import os
from PyQt5 import Qt


def initResources():
    resourcePath = os.path.abspath(os.path.join(__file__, ".."))
    Qt.QDir.setSearchPaths("icons", [os.path.join(resourcePath, "icons")])

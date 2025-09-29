import numpy
from PyQt5 import Qt

from .tile_set_model import TileSetModel


class TileSetBrowser(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent)
        self.__view = Qt.QListView(self)
        self.__view.setViewMode(Qt.QListView.IconMode)
        self.__view.setWrapping(True)
        self.__view.setIconSize(Qt.QSize(64, 64))
        self.__model = TileSetModel(self)
        self.__view.setModel(self.__model)

        layout = Qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__view)

    def setData(self, data: numpy.ndarray):
        self.__model.setTileSet(data)

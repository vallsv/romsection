from __future__ import annotations
import numpy
import typing
import lru
from PyQt5 import Qt


_tileSetPreview: lru.LRU[int, Qt.QIcon] = lru.LRU(512)


def createTileIcon(data: numpy.ndarray) -> Qt.QIcon:
    """
    Create an icon preview from tile data.

    This icons are cached into a global structure.
    """
    nb_colors = data.shape[2] if len(data.shape) == 3 else 1

    if nb_colors == 1:
        image = Qt.QImage(
            data.tobytes(),
            data.shape[1],
            data.shape[0],
            Qt.QImage.Format_Grayscale8,
        )
    elif nb_colors == 3:
        image = Qt.QImage(
            data.tobytes(),
            8,
            8,
            Qt.QImage.Format_RGB888,
        )
    elif nb_colors == 4:
        image = Qt.QImage(
            data[..., 0:3].tobytes(),
            8,
            8,
            Qt.QImage.Format_BGR888,
        )
        pixmap = Qt.QPixmap.fromImage(image)
    else:
        return Qt.QIcon()

    pixmap = Qt.QPixmap.fromImage(image)
    pixmap = pixmap.scaled(64, 64, Qt.Qt.IgnoreAspectRatio, Qt.Qt.FastTransformation)
    return Qt.QIcon(pixmap)


class TileSetModel(Qt.QAbstractItemModel):
    """
    Qt model to expose a tile set.

    No move or remove are supported.
    """
    TileSetRole = Qt.Qt.UserRole

    def __init__(self, parent: Qt.QObject | None = None):
        super().__init__(parent=parent)
        self.__data: numpy.ndarray = numpy.array([])

    def setTileSet(self, data: numpy.ndarray):
        self.beginResetModel()
        self.__data = data
        self.endResetModel()

    def rowCount(self, parent: Qt.QModelIndex = Qt.QModelIndex()):
        return len(self.__data)

    def index(self, row, column, parent=Qt.QModelIndex()):
        if 0 <= row < len(self.__data):
            return self.createIndex(row, column)
        else:
            return Qt.QModelIndex()

    def tileset(self, index: Qt.QModelIndex) -> numpy.ndarray:
        """Return a RGB or indexed array for tileset of this index"""
        return self.data(index, role=self.TileSetRole)

    def parent(self, index: Qt.QModelIndex):
        return Qt.QModelIndex()

    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.DisplayRole):
        row = index.row()
        if role == self.TileSetRole:
            if not index.isValid():
                return None
            return self.__data[row]
        elif role in (Qt.Qt.DisplayRole, Qt.Qt.EditRole):
            if not index.isValid():
                return ""
            return f"#{row + 1}"
        elif role == Qt.Qt.DecorationRole:
            if not index.isValid():
                return Qt.QIcon()
            data = self.__data[row]
            key = data.tobytes()
            icon = _tileSetPreview.get(key)
            if icon is None:
                icon = createTileIcon(data)
                _tileSetPreview[key] = icon
            return icon
        return None

    def columnCount(self, parent: Qt.QModelIndex = Qt.QModelIndex()):
        return 1

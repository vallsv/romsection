import typing
from PyQt5 import Qt


class ObjectListModel(Qt.QAbstractItemModel):
    """
    Store a list of object as a Qt model.

    No move or remove are supported.
    """
    ObjectRole = Qt.Qt.UserRole

    def __init__(self, parent: Qt.QObject | None = None):
        super().__init__(parent=parent)
        self.__items: list[object] = []

    def setObjectList(self, items: list[typing.Any]):
        self.beginResetModel()
        self.__items = list(items)
        self.endResetModel()

    def rowCount(self, parent: Qt.QModelIndex = Qt.QModelIndex()):
        return len(self.__items)

    def index(self, row, column, parent=Qt.QModelIndex()):
        if 0 <= row < len(self.__items):
            return self.createIndex(row, column)
        else:
            return Qt.QModelIndex()

    def objectIndex(self, obj) -> Qt.QModelIndex:
        try:
            row = self.__items.index(obj)
            return self.index(row, 0)
        except IndexError:
            return Qt.QModelIndex()

    def object(self, index: Qt.QModelIndex) -> typing.Any:
        return self.data(index, role=self.ObjectRole)

    def parent(self, index: Qt.QModelIndex):
        return Qt.QModelIndex()

    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.DisplayRole):
        row = index.row()
        item = self.__items[row]
        if role == self.ObjectRole:
            return item
        elif role == Qt.Qt.DisplayRole:
            return str(item)
        return None

    def columnCount(self, parent: Qt.QModelIndex = Qt.QModelIndex()):
        return 1

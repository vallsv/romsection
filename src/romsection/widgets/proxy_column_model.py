import typing
from PyQt5 import Qt

from .object_list_model import ObjectListModel


class ProxyColumnModel(Qt.QIdentityProxyModel):
    """Provides proxyfied multi columns pointing to the same source column.

    It is mainly used with `modelReset`. `dataChanged` is probably not properly
    managed.
    """

    def __init__(self, parent=None):
        Qt.QIdentityProxyModel.__init__(self, parent=parent)
        self.__columns = 0
        self.__columnTitle = {}
        self.__columnEditor = set()

    def setColumn(self, columnId: int, title: str):
        """Define a column to this model.

        This new column will point to the first column of the source model.
        """
        self.beginResetModel()
        self.__columns = max(self.__columns, columnId + 1)
        self.__columnTitle[columnId] = title
        self.endResetModel()

    def setColumnEditor(self, columnId: int, editor: bool):
        if editor:
            self.__columnEditor.add(columnId)
        else:
            self.__columnEditor.discard(columnId)

    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.DisplayRole):
        if index.isValid():
            if role == Qt.Qt.DisplayRole:
                if index.column() in self.__columnEditor:
                    return ""
        return Qt.QIdentityProxyModel.data(self, index, role)

    def object(self, index: Qt.QModelIndex) -> typing.Any:
        return self.data(index, role=ObjectListModel.ObjectRole)

    def objectIndex(self, obj: typing.Any) -> Qt.QModelIndex:
        sourceModel = self.sourceModel()
        sourceIndex = sourceModel.objectIndex(obj)
        if not sourceIndex.isValid():
            return sourceIndex
        return self.mapFromSource(sourceIndex)

    def columnCount(self, parent: Qt.QModelIndex = Qt.QModelIndex()):
        return self.__columns

    def rowCount(self, parent: Qt.QModelIndex = Qt.QModelIndex()):
        sourceModel = self.sourceModel()
        if sourceModel is None:
            return 0
        parent = self.mapToSource(parent)
        result = sourceModel.rowCount(parent)
        return result

    def index(self, row, column, parent=Qt.QModelIndex()):
        if column != 0:
            firstCol = self.index(row, 0, parent)
            return self.createIndex(row, column, firstCol.internalPointer())
        return super().index(row, column, parent)

    def parent(self, child):
        if not child.isValid():
            return Qt.QModelIndex()
        if child.column() != 0:
            child = self.createIndex(child.row(), 0, child.internalPointer())
        return super().parent(child)

    def mapFromSource(self, sourceIndex: Qt.QModelIndex) -> Qt.QModelIndex:
        if not sourceIndex.isValid():
            return Qt.QModelIndex()
        if sourceIndex.column() != 0:
            return Qt.QModelIndex()
        return super().mapFromSource(sourceIndex)

    def mapToSource(self, proxyIndex: Qt.QModelIndex) -> Qt.QModelIndex:
        if not proxyIndex.isValid():
            return Qt.QModelIndex()
        if proxyIndex.column() != 0:
            proxyIndex = self.createIndex(
                proxyIndex.row(), 0, proxyIndex.internalPointer()
            )
        return super().mapToSource(proxyIndex)

    def headerData(
        self,
        section: int,
        orientation: Qt.Qt.Orientation,
        role: int = Qt.Qt.DisplayRole,
    ):
        if role == Qt.Qt.DisplayRole:
            if orientation == Qt.Qt.Horizontal:
                return self.__columnTitle.get(section, str(section))
        sourceModel = self.sourceModel()
        if sourceModel is None:
            return None
        if orientation == Qt.Qt.Horizontal:
            return sourceModel.headerData(0, orientation, role)
        return sourceModel.headerData(section, orientation, role)

from PyQt5 import Qt

from ..gba_file import MemoryMap
from .memory_map_proxy_model import MemoryMapProxyModel
from .proxy_column_model import ProxyColumnModel


class MemoryMapListView(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)

        self.__table = Qt.QTableView(self)
        self.__table.setIconSize(Qt.QSize(16, 16))
        self.__table.setShowGrid(False)
        horizontalHeader = self.__table.horizontalHeader()
        horizontalHeader.hide()
        horizontalHeader.setStretchLastSection(True)
        verticalHeader = self.__table.verticalHeader()
        verticalHeader.hide()
        verticalHeader.setDefaultSectionSize(20)
        verticalHeader.sectionResizeMode(Qt.QHeaderView.Fixed)
        self.__table.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.__table.setSelectionMode(Qt.QAbstractItemView.ExtendedSelection)

        layout = Qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__table)

        self.__columned = ProxyColumnModel(self)
        self.__columned.setColumn(0, "Name")
        self.__columned.setColumn(1, "Memory")
        self.__proxy = MemoryMapProxyModel(self)
        self.__proxy.setSourceModel(self.__columned)
        self.__table.setModel(self.__proxy)

    def setModel(self, model: Qt.QAbstractItemModel):
        self.__columned.setSourceModel(model)

    def model(self) -> Qt.QAbstractItemModel:
        return self.__columned.sourceModel()

    def filterModel(self) -> MemoryMapProxyModel:
        return self.__proxy

    def selectionModel(self) -> Qt.QItemSelectionModel:
        return self.__table.selectionModel()

    def selectedMemoryMap(self) -> MemoryMap | None:
        model = self.__table.selectionModel()
        items = model.selectedRows()
        if len(items) != 1:
            return None
        mem = items[0].data(Qt.Qt.UserRole)
        return mem

    def selectedMemoryMaps(self) -> list[MemoryMap]:
        model = self.__table.selectionModel()
        items = model.selectedRows()
        return [i.data(Qt.Qt.UserRole) for i in items]

    def currentMemoryMap(self) -> MemoryMap | None:
        """Return the current memory map."""
        model = self.__table.selectionModel()
        index = model.currentIndex()
        if not index.isValid():
            return None
        mem = index.data(Qt.Qt.UserRole)
        return mem

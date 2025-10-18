from __future__ import annotations
import io
import lru
from PyQt5 import Qt
from typing import Callable


class HexaStructModel(Qt.QAbstractTableModel):
    """Struct of bytes rendering of hexadecimal and description.

    Each element of the strcut is displayed as bytes and it's description.
    """

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QAbstractTableModel.__init__(self, parent)
        self.__struct: list[tuple[int, bytes, str]] = []
        self.__address: int = 0
        self.__itemSize: int = 0
        self.__font = Qt.QFontDatabase.systemFont(Qt.QFontDatabase.FixedFont)
        self.__palette = Qt.QPalette()

    def rowCount(self, parent_idx=None):
        """Returns number of rows to be displayed in table"""
        return len(self.__struct)

    def columnCount(self, parent_idx=None):
        """Returns number of columns to be displayed in table"""
        return self.__itemSize + 1

    def data(self, index: Qt.QModelIndex, role=Qt.Qt.DisplayRole):
        """QAbstractTableModel method to access data values
        in the format ready to be displayed"""
        if not index.isValid():
            return None

        row = index.row()
        column = index.column()
        dataStruct = self.__struct[row]

        if role == Qt.Qt.DisplayRole:
            if column == self.__itemSize:
                return dataStruct[2]
            else:
                data = dataStruct[1]
                if column < len(data):
                    return f"{data[column]:02X}"
                else:
                    return ""

        elif role == Qt.Qt.FontRole:
            if column < self.__itemSize:
                return self.__font
            else:
                return None

        elif role == Qt.Qt.ForegroundRole:
            if column == self.__itemSize:
                return Qt.QColorConstants.Black

        elif role == Qt.Qt.BackgroundRole:
            if column == self.__itemSize:
                return self.__palette.color(Qt.QPalette.Disabled, Qt.QPalette.Window)
            else:
                data = dataStruct[1]
                if column < len(data):
                    return None
                else:
                    return self.__palette.color(Qt.QPalette.Disabled, Qt.QPalette.ButtonText)

        elif role == Qt.Qt.TextAlignmentRole:
            if column == self.__itemSize:
                return Qt.Qt.AlignLeft | Qt.Qt.AlignVCenter
            else:
                return Qt.Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.Qt.DisplayRole):
        """Returns the 0-based row or column index, for display in the
        horizontal and vertical headers"""
        if section == -1:
            # PyQt4 send -1 when there is columns but no rows
            return None

        if role == Qt.Qt.DisplayRole:
            if orientation == Qt.Qt.Vertical:
                dataStruct = self.__struct[section]
                address = self.__address + dataStruct[0]
                return f"{address:08X}"
            if orientation == Qt.Qt.Horizontal:
                if section == self.__itemSize:
                    return "Description"
                else:
                    return f"{section:02X}"
        elif role == Qt.Qt.FontRole:
            if orientation == Qt.Qt.Vertical:
                return self.__font
            if orientation == Qt.Qt.Horizontal:
                if section != self.__itemSize:
                    return self.__font
                else:
                    return None
        elif role == Qt.Qt.TextAlignmentRole:
            if orientation == Qt.Qt.Vertical:
                return Qt.Qt.AlignRight | Qt.Qt.AlignVCenter
            if orientation == Qt.Qt.Horizontal:
                if section == self.__itemSize:
                    return Qt.Qt.AlignLeft | Qt.Qt.AlignVCenter
                else:
                    return Qt.Qt.AlignCenter
        return None

    def flags(self, index: Qt.QModelIndex):
        """QAbstractTableModel method to inform the view whether data
        is editable or not.
        """
        column = index.column()
        if column == self.__itemSize:
            return Qt.Qt.NoItemFlags
        row = index.row()
        dataStruct = self.__struct[row]
        if column >= len(dataStruct[1]):
            return Qt.Qt.NoItemFlags
        return Qt.QAbstractTableModel.flags(self, index)

    def setStruct(self, data: list[tuple[int, bytes, str]], address: int = 0):
        self.beginResetModel()
        self.__address = address
        self.__struct = data
        if self.__struct != []:
            self.__itemSize = max([len(s[1]) for s in self.__struct])
        else:
            self.__itemSize = 0
        self.endResetModel()


class HexaStructView(Qt.QTableView):
    """
    TableView to show a 1D tablarray of binary data.

    The memory input is split into multiple items of the
    same size.

    A basic description can be assosiated.
    """

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QTableView.__init__(self, parent)
        model = HexaStructModel(self)
        self.setModel(model)

    def setStruct(self, data: list[tuple[int, bytes, str]] | None, address: int = 0):
        model = self.model()
        model.setStruct(data if data is not None else [], address)
        self.__fixHeader()

    def __fixHeader(self):
        """Update the view according to the state of the auto-resize"""
        header = self.horizontalHeader()
        header.setDefaultSectionSize(30)
        header.setStretchLastSection(True)
        model = self.model()
        columnCount = model.columnCount()
        for i in range(columnCount - 1):
            header.setSectionResizeMode(i, Qt.QHeaderView.Fixed)
        header.setSectionResizeMode(columnCount - 1, Qt.QHeaderView.Stretch)

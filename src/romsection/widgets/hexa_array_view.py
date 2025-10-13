from __future__ import annotations
import io
import lru
from PyQt5 import Qt
from typing import Callable


class HexaTableModel(Qt.QAbstractTableModel):
    """Table of hexadecimal rendering of byte data.

    Bytes are displayed one by one as a hexadecimal viewer.

    The first columns display bytes as hexadecimal, the last column
    displays the same data as custom description.
    """

    AddressRole = Qt.Qt.UserRole

    ItemAddressRole = Qt.Qt.UserRole + 1

    ItemData = Qt.Qt.UserRole + 2

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QAbstractTableModel.__init__(self, parent)
        self.__data: bytes | None = None
        self.__address: int = 0
        self.__itemSize: int = 16
        self.__length: int = 0
        self.__font = Qt.QFontDatabase.systemFont(Qt.QFontDatabase.FixedFont)
        self.__palette = Qt.QPalette()
        self.__description: lru.LRU[int, str] = lru.LRU(256)
        self.__descriptionMeth: Callable[[int, bytes], str] | None = None

    def itemSize(self) -> int:
        return self.__itemSize

    def setItemSize(self, itemSize: int):
        self.beginResetModel()
        self.__itemSize = itemSize
        self.endResetModel()

    def rowCount(self, parent_idx=None):
        """Returns number of rows to be displayed in table"""
        if self.__data is None or self.__length == 0:
            return 0
        nb, remaining = divmod(self.__length, self.__itemSize)
        return nb + int(remaining != 0)

    def columnCount(self, parent_idx=None):
        """Returns number of columns to be displayed in table"""
        return self.__itemSize + 1

    def _getCachedDescription(self, row: int) -> str:
        ascii = self.__description.get(row, None)
        if ascii is not None:
            return ascii

        if self.__data is None:
            text = "No data"
        else:
            start = row * self.__itemSize
            if start + self.__itemSize > self.__length:
                text = "Invalid size"
            else:
                data = self.__data[start:start + self.__itemSize]
                text = self._getDescription(row, data)
        self.__description[row] = text
        return text

    def setDescriptionMethod(self, meth: Callable[[int, bytes], str] | None):
        self.beginResetModel()
        self.__descriptionMeth = meth
        self.__description.clear()
        self.endResetModel()

    def _getDescription(self, row: int, data: bytes) -> str:
        descriptionMeth = self.__descriptionMeth
        if descriptionMeth is not None:
            description = descriptionMeth(row, data)
            return f"#{row + 1:03d} {description}"
        else:
            return f"#{row + 1:03d}"

    def data(self, index: Qt.QModelIndex, role=Qt.Qt.DisplayRole):
        """QAbstractTableModel method to access data values
        in the format ready to be displayed"""
        if not index.isValid():
            return None

        if self.__data is None:
            return None

        row = index.row()
        column = index.column()

        if role == self.AddressRole:
            pos = (row * self.__itemSize) + column
            if pos > self.__length:
                return None
            return self.__address + pos

        elif role == self.ItemAddressRole:
            pos = (row * self.__itemSize) + column
            if pos > self.__length:
                return None
            return self.__address + row * self.__itemSize

        elif role == self.ItemData:
            start = (row * self.__itemSize)
            if start + self.__itemSize > self.__length:
                return None
            return self.__data[start:start + self.__itemSize]

        elif role == Qt.Qt.DisplayRole:
            if column == self.__itemSize:
                return self._getCachedDescription(row)
            else:
                pos = (row * self.__itemSize) + column
                if pos < self.__length:
                    value = self.__data[pos]
                    return f"{value:02X}"
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
            pos = (row * self.__itemSize) + column
            if column == self.__itemSize:
                return self.__palette.color(Qt.QPalette.Disabled, Qt.QPalette.Window)
            elif pos >= self.__length:
                return self.__palette.color(Qt.QPalette.Disabled, Qt.QPalette.ButtonText)
            else:
                return None

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
                address = self.__address + (section * self.__itemSize)
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
            return Qt.QAbstractTableModel.flags(self, index)
        row = index.row()
        pos = (row * self.__itemSize) + column
        if pos >= self.__length:
            return Qt.Qt.NoItemFlags
        return Qt.QAbstractTableModel.flags(self, index)

    def setBytes(self, data: bytes | None, address: int = 0):
        """Set the data array."""
        self.beginResetModel()
        self.__data = data
        self.__address = address
        self.__length = len(data) if data is not None else 0
        self.__description.clear()
        self.endResetModel()

    def indexFromAddress(self, address: int) -> Qt.QModelIndex:
        if address < self.__address or address >= self.__address + self.__length:
            return Qt.QModelIndex()
        row, col = divmod(address - self.__address, self.__itemSize)
        return self.index(row, col)

    def bytes(self) -> bytes | None:
        """Returns the internal data."""
        return self.__data


class HexaArrayView(Qt.QTableView):
    """
    TableView to show a 1D tablarray of binary data.

    The memory input is split into multiple items of the
    same size.

    A basic description can be assosiated.
    """

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QTableView.__init__(self, parent)
        model = HexaTableModel(self)
        self.setModel(model)

    def setPosition(self, pos: int):
        line = pos // 16
        model = self.model()
        index = model.index(line, 0)
        self.scrollTo(index)

    def setMemory(self, memory: io.IOBase | None, address: int=0):
        """
        Set the binary data.
        """
        if memory is not None:
            # FIXME: Really handle `io`, actually we only support `BytesIO`.
            data = memory.getvalue()
        else:
            data = b""
        self.model().setBytes(data, address=address)
        self.__fixHeader()

    def __fixHeader(self):
        """Update the view according to the state of the auto-resize"""
        header = self.horizontalHeader()
        header.setDefaultSectionSize(30)
        header.setStretchLastSection(True)
        model = self.model()
        itemSize = model.itemSize()
        for i in range(itemSize):
            header.setSectionResizeMode(i, Qt.QHeaderView.Fixed)
        header.setSectionResizeMode(itemSize, Qt.QHeaderView.Stretch)

    def selectedAddress(self) -> int | None:
        """Return the selected address"""
        model = self.selectionModel()
        items = model.selectedIndexes()
        if len(items) != 1:
            return None
        index = items[0]
        return index.data(HexaTableModel.AddressRole)

    def selectedItemAddress(self) -> int | None:
        """Return the selected address"""
        model = self.selectionModel()
        items = model.selectedIndexes()
        if len(items) != 1:
            return None
        index = items[0]
        return index.data(HexaTableModel.ItemAddressRole)

    def selectedItemData(self) -> bytes | None:
        """Return the selected address"""
        model = self.selectionModel()
        items = model.selectedIndexes()
        if len(items) != 1:
            return None
        index = items[0]
        return index.data(HexaTableModel.ItemData)

    def selectAddress(self, address: int | None):
        """Set the selected address"""
        selectionModel = self.selectionModel()
        if address is None:
            selectionModel.clearSelection()
            return
        model = self.model()
        index = model.indexFromAddress(address)
        selectionModel.select(index, Qt.QItemSelectionModel.ClearAndSelect)

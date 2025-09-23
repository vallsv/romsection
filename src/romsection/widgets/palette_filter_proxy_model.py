from __future__ import annotations

import logging
import numpy
import typing
import lru
from PyQt5 import Qt

from .object_list_model import ObjectListModel
from ..gba_file import GBAFile, MemoryMap, DataType
from ..utils import convert_16bx1_to_5bx3


_palettePreview: lru.LRU[int, Qt.QIcon] = lru.LRU(512)


def createPaletteIcon(rom: GBAFile, mem: MemoryMap) -> Qt.QIcon:
    """
    Create an icon preview from a memory map.

    This icons are cached into a global structure.
    """
    try:
        data = rom.palette_data(mem)
    except Exception:
        logging.warning("Error while getting palette data", exc_info=True)
        return Qt.QIcon()

    # FIXME: Support Palette set
    paletteData = data[0]

    size = len(paletteData)
    pixmap = Qt.QPixmap(size, size)
    painter = Qt.QPainter(pixmap)
    # FIXME: This could be done without loop
    for i in range(size):
        rgb = paletteData[i]
        r, g, b = rgb[0], rgb[1], rgb[2]
        painter.setPen(Qt.QColor.fromRgbF(r, g, b))
        painter.drawPoint(Qt.QPoint(i, 0))

    painter.drawPixmap(0, 1, size, size - 1, pixmap, 0, 0, size, 1)
    painter.end()

    return Qt.QIcon(pixmap)


class PaletteFilterProxyModel(Qt.QSortFilterProxyModel):
    def __init__(self, parent: Qt.QObject | None = None):
        Qt.QSortFilterProxyModel.__init__(self, parent=parent)
        self._rom: GBAFile | None = None

    def setRom(self, rom: GBAFile):
        self._rom = rom

    def objectIndex(self, obj: typing.Any) -> Qt.QModelIndex:
        sourceModel = self.sourceModel()
        sourceIndex = sourceModel.objectIndex(obj)
        if not sourceIndex.isValid():
            return sourceIndex
        return self.mapFromSource(sourceIndex)

    def object(self, index: Qt.QModelIndex) -> typing.Any:
        return self.data(index, role=ObjectListModel.ObjectRole)

    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.DisplayRole):
        global _palettePreview
        if role in (Qt.Qt.DisplayRole, Qt.Qt.EditRole):
            if not index.isValid():
                return ""
            mem = self.object(index)
            if mem is None:
                return "No palette"
            return f"Palette 0x{mem.byte_offset:08X}"
        if role == Qt.Qt.DecorationRole:
            if not index.isValid():
                return Qt.QIcon()
            if self._rom is None:
                return Qt.QIcon()
            mem = self.object(index)
            if mem is None:
                return Qt.QIcon()
            # FIXME: Use a hash from the mem state
            icon = _palettePreview.get(mem.byte_offset)
            if icon is None:
                icon = createPaletteIcon(self._rom, mem)
                _palettePreview[mem.byte_offset] = icon
            return icon
        return Qt.QSortFilterProxyModel.data(self, index, role)

    def filterAcceptsRow(self, source_row: int, source_parent: Qt.QModelIndex) -> bool:
        sourceModel = self.sourceModel()
        index = sourceModel.index(source_row, 0, source_parent)
        if not index.isValid():
            return True
        mem = sourceModel.data(index, role=ObjectListModel.ObjectRole)
        return mem.data_type == DataType.PALETTE

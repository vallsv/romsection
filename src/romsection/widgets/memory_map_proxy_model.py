from __future__ import annotations

import logging
import numpy
import typing
import lru
from PyQt5 import Qt

from .object_list_model import ObjectListModel
from ..gba_file import MemoryMap, ByteCodec, DataType


class MemoryMapFilter(typing.NamedTuple):
    shownDataTypes: set[DataType] | None = None
    minBytePayload: int | None = None
    maxBytePayload: int | None = None

    def accepts(self, mem: MemoryMap) -> bool:
        if self.shownDataTypes is not None:
            if mem.data_type not in self.shownDataTypes:
                return False
        bytePayload = mem.byte_payload or mem.byte_length or 0
        if self.minBytePayload is not None:
            if bytePayload < self.minBytePayload:
                return False
        if self.maxBytePayload is not None:
            if bytePayload > self.maxBytePayload:
                return False
        return True


def format_size(size: int) -> str:
    if size < 2 * 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size // (1024)} KiB"
    return f"{size // (1024 * 1024)} MiB"


class MemoryMapProxyModel(Qt.QSortFilterProxyModel):
    """Filter and create multiple columns from the original model"""

    ColumnAddress = 0
    ColumnMemory = 1
    NbColumns = 2

    def __init__(self, parent: Qt.QObject | None = None):
        Qt.QSortFilterProxyModel.__init__(self, parent=parent)
        self._filter: MemoryMapFilter | None = None

    def columnCount(self, parent: Qt.QModelIndex) -> int:
        return self.NbColumns

    def objectIndex(self, obj: typing.Any) -> Qt.QModelIndex:
        sourceModel = self.sourceModel()
        sourceIndex = sourceModel.objectIndex(obj)
        if not sourceIndex.isValid():
            return sourceIndex
        return self.mapFromSource(sourceIndex)

    def object(self, index: Qt.QModelIndex) -> typing.Any:
        sourceModel = self.sourceModel()
        sourceIndex = self.mapToSource(index)
        if not sourceIndex.isValid():
            return None
        return sourceIndex.data(ObjectListModel.ObjectRole)

    def setFilter(self, filter: MemoryMapFilter | None):
        self._filter = filter
        self.invalidateFilter()

    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.DisplayRole):
        if not index.isValid():
            return None

        column = index.column()
        sourceModel = self.sourceModel()
        firstColumn = self.index(index.row(), 0)
        sourceIndex = self.mapToSource(index)

        if column == self.ColumnAddress:
            if role in (Qt.Qt.DisplayRole, Qt.Qt.EditRole):
                mem = sourceIndex.data(ObjectListModel.ObjectRole)
                return f"{mem.byte_offset:08X}h"
            return sourceIndex.data(role=role)

        if column == self.ColumnMemory:
            mem = sourceIndex.data(ObjectListModel.ObjectRole)
            if role in (Qt.Qt.DisplayRole, Qt.Qt.EditRole):
                length = mem.byte_payload or mem.byte_length or 0
                return format_size(length)
            if role == Qt.Qt.ToolTipRole:
                length = mem.byte_length
                byteCodec = mem.byte_codec
                if byteCodec is None or byteCodec == ByteCodec.RAW:
                    return f"Size: {length} B"
                else:
                    dataLength = mem.byte_payload or mem.byte_length or 0
                    return f"Size: {dataLength} B\nCodec: {byteCodec.name}\nCompressed: {length} B"
            if role == Qt.Qt.DecorationRole:
                byteCodec = mem.byte_codec
                if byteCodec is None or byteCodec == ByteCodec.RAW:
                    return Qt.QIcon("icons:empty.png")
                if byteCodec == ByteCodec.LZ77:
                    return Qt.QIcon("icons:lz77.png")
                if byteCodec == ByteCodec.HUFFMAN:
                    return Qt.QIcon("icons:huffman.png")
                if byteCodec == ByteCodec.HUFFMAN_OVER_LZ77:
                    return Qt.QIcon("icons:huffman_lz77.png")
                else:
                    return Qt.QIcon("icons:lz77.png")

        return Qt.QSortFilterProxyModel.data(self, index, role)

    def filterAcceptsRow(self, source_row: int, source_parent: Qt.QModelIndex) -> bool:
        sourceModel = self.sourceModel()
        index = sourceModel.index(source_row, 0, source_parent)
        if not index.isValid():
            return True
        mem = sourceModel.data(index, role=ObjectListModel.ObjectRole)
        filter = self._filter
        if filter is None:
            return True
        return filter.accepts(mem)

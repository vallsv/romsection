from __future__ import annotations

import logging
import numpy
import lru
from PyQt5 import Qt

from .object_list_model import ObjectListModel
from ..gba_file import MemoryMap, DataType


class MemoryMapListModel(ObjectListModel):
    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.DisplayRole):
        if role in (Qt.Qt.DisplayRole, Qt.Qt.EditRole):
            if not index.isValid():
                return ""
            mem = self.object(index)
            if mem is None:
                return ""
            length = mem.byte_payload or mem.byte_length or 0
            return f"{mem.byte_offset:08X} {length: 8d}B"

        if role == Qt.Qt.DecorationRole:
            if not index.isValid():
                return Qt.QIcon()
            mem = self.object(index)
            if mem is None:
                return Qt.QIcon()
            if mem.data_type == DataType.IMAGE:
                return Qt.QIcon("icons:image.png")
            if mem.data_type == DataType.PALETTE:
                return Qt.QIcon("icons:palette.png")
            if mem.data_type == DataType.UNKNOWN:
                return Qt.QIcon("icons:unknown.png")
            if mem.data_type == DataType.PADDING:
                return Qt.QIcon("icons:padding.png")

            return Qt.QIcon("icons:empty.png")

        return ObjectListModel.data(self, index, role)

from __future__ import annotations

import logging
import numpy
import lru
from PyQt5 import Qt

from .object_list_model import ObjectListModel
from ..gba_file import MemoryMap, DataType
from . import ui_styles


class MemoryMapListModel(ObjectListModel):

    def indexAfterOffset(self, offset: int):
        # FIXME: Use bisect instead
        before = None
        for row in range(self.rowCount()):
            index = self.index(row, 0)
            mem = self.object(index)
            if offset < mem.byte_offset:
                return row
        return self.rowCount()

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
            data_type = mem.data_type
            if data_type is None:
                return Qt.QIcon("icons:empty.png")
            return ui_styles.getIcon(data_type)

        return ObjectListModel.data(self, index, role)

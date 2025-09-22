from __future__ import annotations

import logging
import numpy
import lru
from PyQt5 import Qt

from .object_list_model import ObjectListModel
from ..gba_file import MemoryMap


class MemoryMapListModel(ObjectListModel):
    def __init__(self, parent: Qt.QObject | None = None):
        ObjectListModel.__init__(self, parent=parent)

    def data(self, index: Qt.QModelIndex, role: int = Qt.Qt.DisplayRole):
        if role in (Qt.Qt.DisplayRole, Qt.Qt.EditRole):
            if not index.isValid():
                return ""
            mem = self.object(index)
            if mem is None:
                return ""
            length = mem.byte_payload or mem.byte_length or 0
            return f"{mem.byte_offset:08X} {length: 8d}B"
        return ObjectListModel.data(self, index, role)

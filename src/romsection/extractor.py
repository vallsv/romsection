import os
import sys
import logging
import yaml
from PyQt5 import Qt

from silx.gui.plot.ImageView import ImageView
from .lz77 import decompress as decompress_lz77
from .utils import prime_factors, guessed_shapes


class MemMapping:
    def __init__(self, offset, nb_pixels, shape=None):
        self.offset = offset
        self.nb_pixels = nb_pixels
        self.shape = shape

    def to_dict(self):
        description = {"offset": self.offset, "nb_pixels": self.nb_pixels}
        if self.shape is not ne:
            description["shape"] = list(self.shape)
        return description

    @staticmethod
    def from_dict(description: dict):
        offset = description["offset"]
        nb_pixels = description.get("nb_pixels")
        shape = description.get("shape")
        if shape is not None:
            shape = tuple(shape)
        return MemMapping(offset, nb_pixels, shape)


class GBAFile:

    def __init__(self, filename):
        self._filename = filename
        f = open(filename, "rb")
        self.offsets: list[MemMapping] = []
        f.seek(0, os.SEEK_END)
        self._size = f.tell()
        f.seek(0, os.SEEK_SET)
        self._f = f

    @property
    def filename(self):
        return self._filename

    @property
    def size(self):
        return self._size

    def scan_all(self):
        self.offsets.clear()
        f = self._f
        f.seek(0, os.SEEK_SET)
        offset = 0
        while offset < self._size:
            try:
                data = decompress_lz77(f)
            except ValueError:
                pass
            else:
                self.offsets.append(MemMapping(offset, data.size))
            offset += 1
            f.seek(offset, os.SEEK_SET)

    def extract_lz77(self, sprite: MemMapping):
        f = self._f
        f.seek(sprite.offset, os.SEEK_SET)
        return decompress_lz77(f)


class Extractor(Qt.QWidget):
    def __init__(self):
        Qt.QWidget.__init__(self)
        toolbar = Qt.QVBoxLayout()
        self.rom = None

        scanAll = Qt.QPushButton(self)
        scanAll.clicked.connect(self._scanAll)
        scanAll.setText("Scan All")
        toolbar.addWidget(scanAll)

        loadInfo = Qt.QPushButton(self)
        loadInfo.clicked.connect(self._loadInfo)
        loadInfo.setText("Load Info")
        toolbar.addWidget(loadInfo)

        saveInfo = Qt.QPushButton(self)
        saveInfo.clicked.connect(self._saveInfo)
        saveInfo.setText("Save Info")
        toolbar.addWidget(saveInfo)

        self._spriteList = Qt.QListWidget(self)
        self._spriteList.itemSelectionChanged.connect(self._selectSprite)

        self._shapeList = Qt.QListWidget(self)
        self._shapeList.itemSelectionChanged.connect(self._selectShape)

        self._view = ImageView(self, backend="gl")
        self._view.setKeepDataAspectRatio(True)
        self._view.setSideHistogramDisplayed(False)
        self._view.getYAxis().setInverted(True)

        main = Qt.QHBoxLayout(self)
        main.addLayout(toolbar)
        main.addWidget(self._spriteList)
        main.addWidget(self._shapeList)
        main.addWidget(self._view)

    def _scanAll(self):
        self.rom.scan_all()
        self._syncSpriteList()

    def _loadInfo(self):
        with open(f"{self.rom.filename}.yml", "rt") as f:
            data = yaml.safe_load(f)
        self.rom.offsets.clear()
        for m in data["mapping"]:
            mapping = MemMapping.from_dict(m)
            self.rom.offsets.append(mapping)
        self._syncSpriteList()

    def _syncSpriteList(self):
        self._spriteList.clear()
        for sprite in self.rom.offsets:
            item = Qt.QListWidgetItem()
            item.setText(f"{sprite.offset:08X} {sprite.nb_pixels: 8d}px")
            item.setData(Qt.Qt.UserRole, sprite)
            self._spriteList.addItem(item)

    def _saveInfo(self):
        mapping = []
        for s in self.rom.offsets:
            mapping.append(s.to_dict())
        with open(f"{self.rom.filename}.yml", "wt") as f:
            yaml.dump({"mapping": mapping}, f)

    def _selectSprite(self):
        items = self._spriteList.selectedItems() 
        if len(items) != 1:
            return
        sprite = items[0].data(Qt.Qt.UserRole)

        try:
            data = self.rom.extract_lz77(sprite)
        except Exception as e:
            logging.error("Error while decompressing sprite", exc_info=True)
            return

        self._shapeList.clear()
        shapes = guessed_shapes(data.size)
        if len(shapes) == 0:
            shapes.append((data.size, 1))

        for shape in shapes:
            item = Qt.QListWidgetItem()
            item.setText(f"{shape[0]} × {shape[1]}")
            item.setData(Qt.Qt.UserRole, shape)
            self._shapeList.addItem(item)

        data.shape = sprite.shape or shapes[0]

        selectedShapeItem = self._findItemFromShape(data.shape)
        if selectedShapeItem is not None:
            old = self._shapeList.blockSignals(True)
            try:
                i = self._shapeList.row(selectedShapeItem)
                self._shapeList.setCurrentRow(i)
            finally:
                self._shapeList.blockSignals(old)

        self._view.setImage(data)

    def _findItemFromShape(self, shape) -> Qt.QListWidgetItem | None:
        for i in range(self._shapeList.count()):
            item = self._shapeList.item(i)
            if item.data(Qt.Qt.UserRole) == shape:
                return item
        return None

    def _selectShape(self):
        items = self._spriteList.selectedItems() 
        if len(items) != 1:
            return
        sprite = items[0].data(Qt.Qt.UserRole)

        items = self._shapeList.selectedItems() 
        if len(items) != 1:
            return
        shape = items[0].data(Qt.Qt.UserRole)

        try:
            data = self.rom.extract_lz77(sprite)
        except Exception as e:
            logging.error("Error while decompressing sprite", exc_info=True)
            return

        sprite.shape = shape
        data.shape = shape
        self._view.setImage(data)

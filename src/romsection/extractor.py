import os
import sys
import logging
import yaml
import enum
from PyQt5 import Qt

from silx.gui.plot.ImageView import ImageView
from .lz77 import decompress as decompress_lz77
from .utils import prime_factors, guessed_shapes, convert_8bx1_to_4bx2


class ColorMode(enum.Enum):
    INDEXED_8BIT = enum.auto()
    INDEXED_4BIT = enum.auto()


class MemMapping:
    def __init__(
        self,
        offset,
        nb_pixels,
        shape: tuple[int, int] | None = None,
        color_mode: ColorMode | None = None,
        length: int | None = None,
    ):
        self.offset = offset
        self.length = length
        self.nb_pixels = nb_pixels
        self.shape = shape
        self.color_mode: ColorMode | None = color_mode

    def to_dict(self):
        description = {"offset": self.offset, "nb_pixels": self.nb_pixels}
        if self.shape is not None:
            description["shape"] = list(self.shape)
        if self.color_mode is not None:
            description["color_mode"] = self.color_mode.name
        if self.length is not None:
            description["length"] = self.length
        return description

    @staticmethod
    def from_dict(description: dict):
        offset = description["offset"]
        nb_pixels = description.get("nb_pixels")
        shape = description.get("shape")
        color_mode = description.get("color_mode")
        length = description.get("length")
        if shape is not None:
            shape = tuple(shape)
        if color_mode is not None:
            color_mode = ColorMode[color_mode]
        return MemMapping(
            offset,
            nb_pixels,
            shape=shape,
            color_mode=color_mode,
            length=length,
        )


class GBAFile:

    def __init__(self, filename: str):
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

    def extract_raw(self, mapping: MemMapping) -> bytes:
        f = self._f
        f.seek(mapping.offset, os.SEEK_SET)
        data = f.read(mapping.length)
        return data

    def extract_lz77(self, sprite: MemMapping):
        f = self._f
        f.seek(sprite.offset, os.SEEK_SET)
        result = decompress_lz77(f)
        offset_end = f.tell()
        sprite.length = offset_end - sprite.offset
        return result


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
        self._spriteList.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self._spriteList.customContextMenuRequested.connect(self._showSpriteContextMenu)
        self._spriteList.setUniformItemSizes(True)

        self._colorModeList = Qt.QListWidget(self)
        self._colorModeList.itemSelectionChanged.connect(self._selectColorMode)
        item = Qt.QListWidgetItem()
        item.setText(f"Indexed 256 colors")
        item.setData(Qt.Qt.UserRole, ColorMode.INDEXED_8BIT)
        self._colorModeList.addItem(item)
        item = Qt.QListWidgetItem()
        item.setText(f"Indexed 16 colors")
        item.setData(Qt.Qt.UserRole, ColorMode.INDEXED_4BIT)
        self._colorModeList.addItem(item)
        self._colorModeList.setUniformItemSizes(True)
        self._colorModeList.setVerticalScrollBarPolicy(Qt.Qt.ScrollBarAlwaysOff)
        self._colorModeList.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Maximum)
        self._colorModeList.setSizeAdjustPolicy(Qt.QListWidget.AdjustToContents)

        self._shapeList = Qt.QListWidget(self)
        self._shapeList.itemSelectionChanged.connect(self._selectShape)
        self._shapeList.setUniformItemSizes(True)

        self._view = ImageView(self, backend="gl")
        self._view.setKeepDataAspectRatio(True)
        self._view.setSideHistogramDisplayed(False)
        self._view.getYAxis().setInverted(True)

        spriteCodec = Qt.QVBoxLayout()
        spriteCodec.addWidget(self._colorModeList)
        spriteCodec.addWidget(self._shapeList)
        spriteCodec.setStretchFactor(self._shapeList, 1)

        main = Qt.QHBoxLayout(self)
        main.addLayout(toolbar)
        main.addWidget(self._spriteList)
        main.addLayout(spriteCodec)
        main.addWidget(self._view)

    def _scanAll(self):
        self.rom.scan_all()
        self._syncSpriteList()

    def _showSpriteContextMenu(self, pos: Qt.QPoint):
        globalPos = self._spriteList.mapToGlobal(pos)
        menu = Qt.QMenu(self)

        saveRaw = Qt.QAction(menu)
        saveRaw.setText("Save as raw...")
        saveRaw.triggered.connect(self._saveMemMapAsRaw)
        menu.addAction(saveRaw)

        menu.exec(globalPos)

    def _saveMemMapAsRaw(self):
        dialog = Qt.QFileDialog(self)
        dialog.setWindowTitle("Save as RAW")
        dialog.setModal(True)
        filters = [
            "RAW files (*.raw)",
            "All files (*)",
        ]
        dialog.setNameFilters(filters)
        dialog.setFileMode(Qt.QFileDialog.AnyFile)
        dialog.setAcceptMode(Qt.QFileDialog.AcceptSave)

        items = self._spriteList.selectedItems()
        if len(items) != 1:
            return
        sprite = items[0].data(Qt.Qt.UserRole)

        dialog.selectFile(f"{sprite.offset:08X}+{sprite.length}.raw")
        result = dialog.exec_()
        if not result:
            return

        data = self.rom.extract_raw(sprite)

        filename = dialog.selectedFiles()[0]
        with open(filename, "wb") as f:
            f.write(data)

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

        data = self._readSprite(sprite)
        if data is None:
            return

        self._shapeList.clear()
        shapes = guessed_shapes(data.size)
        for shape in shapes:
            item = Qt.QListWidgetItem()
            item.setText(f"{shape[0]} × {shape[1]}")
            item.setData(Qt.Qt.UserRole, shape)
            self._shapeList.addItem(item)

        selectedColorModeItem = self._findItemFromColorMode(sprite.color_mode)
        if selectedColorModeItem is not None:
            old = self._colorModeList.blockSignals(True)
            try:
                i = self._colorModeList.row(selectedColorModeItem)
                self._colorModeList.setCurrentRow(i)
            finally:
                self._colorModeList.blockSignals(old)
        else:
            self._colorModeList.setCurrentRow(-1)

        selectedShapeItem = self._findItemFromShape(data.shape)
        if selectedShapeItem is not None:
            old = self._shapeList.blockSignals(True)
            try:
                i = self._shapeList.row(selectedShapeItem)
                self._shapeList.setCurrentRow(i)
            finally:
                self._shapeList.blockSignals(old)
        else:
            self._shapeList.setCurrentRow(-1)

        self._view.setImage(data)

    def _findItemFromColorMode(self, color_mode: ColorMode | None) -> Qt.QListWidgetItem | None:
        if color_mode is None:
            return None
        for i in range(self._colorModeList.count()):
            item = self._colorModeList.item(i)
            if item.data(Qt.Qt.UserRole) == color_mode:
                return item
        return None

    def _findItemFromShape(self, shape) -> Qt.QListWidgetItem | None:
        for i in range(self._shapeList.count()):
            item = self._shapeList.item(i)
            if item.data(Qt.Qt.UserRole) == shape:
                return item
        return None

    def _selectColorMode(self):
        items = self._spriteList.selectedItems() 
        if len(items) != 1:
            return
        sprite = items[0].data(Qt.Qt.UserRole)

        items = self._colorModeList.selectedItems() 
        if len(items) != 1:
            return
        colorMode = items[0].data(Qt.Qt.UserRole)
        if sprite.color_mode == colorMode:
            return

        previousColorMode = sprite.color_mode
        sprite.color_mode = colorMode

        if sprite.shape is not None:
            pnb = 1 if previousColorMode in [None, ColorMode.INDEXED_8BIT] else 2
            nb = 1 if colorMode in [None, ColorMode.INDEXED_8BIT] else 2
            if pnb != nb:
                sprite.shape = sprite.shape[0], int(sprite.shape[1] * nb / pnb)

        self._selectSprite()

    def _selectShape(self):
        items = self._spriteList.selectedItems() 
        if len(items) != 1:
            return
        sprite = items[0].data(Qt.Qt.UserRole)

        items = self._shapeList.selectedItems() 
        if len(items) != 1:
            return
        shape = items[0].data(Qt.Qt.UserRole)
        sprite.shape = shape

        data = self._readSprite(sprite)
        if data is None:
            return

        self._view.setImage(data)

    def _guessFirstShape(self, data):
        if data.size == 240 * 160:
            # LCD mode
            return 160, 240
        if data.size == 160 * 128:
            # LCD mode
            return 128, 160
        # FIXME: Guess something closer to a square
        return 1, data.size

    def _readSprite(self, sprite):
        try:
            data = self.rom.extract_lz77(sprite)
        except Exception as e:
            logging.error("Error while decompressing sprite", exc_info=True)
            return None

        if sprite.color_mode == ColorMode.INDEXED_4BIT:
            data = convert_8bx1_to_4bx2(data)

        if sprite.shape is not None:
            try:
                data.shape = sprite.shape
            except Exception:
                data.shape = self._guessFirstShape(data)
        else:
            data.shape = self._guessFirstShape(data)

        return data

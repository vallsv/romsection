import os
import sys
import logging
import yaml
import enum
import numpy
from PyQt5 import Qt

from silx.gui.plot.ImageView import ImageView
from .lz77 import decompress as decompress_lz77
from .utils import prime_factors, guessed_shapes, convert_8bx1_to_4bx2, convert_to_tiled_8x8, convert_16bx1_to_5bx3
from .widgets.memory_map_list import MemoryMapList
from .widgets.color_mode_list import ColorModeList
from .widgets.shape_list import ShapeList
from .widgets.pixel_order_list import PixelOrderList
from .widgets.data_type_list import DataTypeList
from .gba_file import GBAFile, MemoryMap, ColorMode, PixelOrder, DataType


class Extractor(Qt.QWidget):
    def __init__(self):
        Qt.QWidget.__init__(self)
        self.rom = None

        self._lastBySize: dict[int, MemoryMap] = {}

        toolbar = Qt.QVBoxLayout()
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

        toolbar.addStretch(1)

        self._memList = MemoryMapList(self)
        self._memList.itemSelectionChanged.connect(self._onMemoryMapSelected)
        self._memList.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self._memList.customContextMenuRequested.connect(self._showSpriteContextMenu)

        self._dataTypeList = DataTypeList(self)
        self._dataTypeList.itemSelectionChanged.connect(self._onDataTypeSelected)

        self._colorModeList = ColorModeList(self)
        self._colorModeList.itemSelectionChanged.connect(self._onColorModeSelected)

        self._shapeList = ShapeList(self)
        self._shapeList.itemSelectionChanged.connect(self._onShapeSelected)

        self._pixelOrderList = PixelOrderList(self)
        self._pixelOrderList.itemSelectionChanged.connect(self._onPixelOrderSelected)

        self._view = ImageView(self, backend="gl")
        self._view.setKeepDataAspectRatio(True)
        self._view.setSideHistogramDisplayed(False)
        self._view.getYAxis().setInverted(True)

        spriteCodec = Qt.QVBoxLayout()
        spriteCodec.addWidget(self._dataTypeList)
        spriteCodec.addWidget(self._colorModeList)
        spriteCodec.addWidget(self._shapeList)
        spriteCodec.addWidget(self._pixelOrderList)
        spriteCodec.setStretchFactor(self._dataTypeList, 0)
        spriteCodec.setStretchFactor(self._colorModeList, 0)
        spriteCodec.setStretchFactor(self._shapeList, 1)
        spriteCodec.setStretchFactor(self._pixelOrderList, 0)

        main = Qt.QHBoxLayout(self)
        main.addLayout(toolbar)
        main.addWidget(self._memList)
        main.addLayout(spriteCodec)
        main.addWidget(self._view)

    def _scanAll(self):
        self.rom.scan_all()
        self._syncSpriteList()

    def _showSpriteContextMenu(self, pos: Qt.QPoint):
        globalPos = self._memList.mapToGlobal(pos)
        menu = Qt.QMenu(self)

        saveRaw = Qt.QAction(menu)
        saveRaw.setText("Save as raw...")
        saveRaw.triggered.connect(self._saveMemoryMapAsRaw)
        menu.addAction(saveRaw)

        menu.exec(globalPos)

    def _saveMemoryMapAsRaw(self):
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

        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        dialog.selectFile(f"{mem.offset:08X}+{mem.length}.raw")
        result = dialog.exec_()
        if not result:
            return

        data = self.rom.extract_raw(mem)

        filename = dialog.selectedFiles()[0]
        with open(filename, "wb") as f:
            f.write(data)

    def _loadInfo(self):
        with open(f"{self.rom.filename}.yml", "rt") as f:
            data = yaml.safe_load(f)
        self.rom.offsets.clear()
        for m in data["mapping"]:
            mem = MemoryMap.from_dict(m)
            self.rom.offsets.append(mem)
        self._syncSpriteList()

    def _syncSpriteList(self):
        self._memList.clear()
        for mem in self.rom.offsets:
            self._memList.addMemoryMap(mem)

    def _saveInfo(self):
        mapping = []
        for mem in self.rom.offsets:
            mapping.append(mem.to_dict())
        with open(f"{self.rom.filename}.yml", "wt") as f:
            yaml.dump({"mapping": mapping}, f)

    def _onMemoryMapSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        if mem.data_type is None:
            # Compatibility with old files
            mem.data_type = DataType.IMAGE

        if mem.color_mode is None and mem.shape is None and mem.pixel_order is None:
            previous = self._lastBySize.get(mem.nb_pixels)
            if previous is not None:
                mem.color_mode = previous.color_mode
                mem.shape = previous.shape
                mem.pixel_order = previous.pixel_order

        self._lastBySize[mem.nb_pixels] = mem

        try:
            old = self._dataTypeList.blockSignals(True)
            self._dataTypeList.selectDataType(mem.data_type)
        finally:
            self._dataTypeList.blockSignals(old)

        try:
            old = self._colorModeList.blockSignals(True)
            self._colorModeList.selectColorMode(mem.color_mode)
        finally:
            self._colorModeList.blockSignals(old)

        try:
            old = self._pixelOrderList.blockSignals(True)
            self._pixelOrderList.selectPixelOrder(mem.pixel_order)
        finally:
            self._pixelOrderList.blockSignals(old)

        self._syncShapes()

    def _onDataTypeSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        dataType = self._dataTypeList.selectedDataType()
        if dataType is None:
            return

        mem.data_type = dataType
        self._updateImage()

    def _syncShapes(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        data = self._readImage(mem)
        if data is None:
            return

        shapes = guessed_shapes(data.size)
        try:
            old = self._shapeList.blockSignals(True)
            self._shapeList.clear()
            for shape in shapes:
                self._shapeList.addShape(shape)
            self._shapeList.selectShape(data.shape)
        finally:
            self._shapeList.blockSignals(old)

        self._view.setImage(data)

    def _onColorModeSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        items = self._colorModeList.selectedItems() 
        if len(items) != 1:
            return
        colorMode = items[0].data(Qt.Qt.UserRole)
        if mem.color_mode == colorMode:
            return

        previousColorMode = mem.color_mode
        mem.color_mode = colorMode

        if mem.shape is not None:
            pnb = 1 if previousColorMode in [None, ColorMode.INDEXED_8BIT] else 2
            nb = 1 if colorMode in [None, ColorMode.INDEXED_8BIT] else 2
            if pnb != nb:
                mem.shape = mem.shape[0], int(mem.shape[1] * nb / pnb)

        self._syncShapes()

    def _onShapeSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        shape = self._shapeList.selectedShape()
        mem.shape = shape
        self._updateImage()

    def _onPixelOrderSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        pixelOrder = self._pixelOrderList.selectedPixelOrder()
        mem.pixel_order = pixelOrder
        self._updateImage()

    def _guessFirstShape(self, data):
        if data.size == 240 * 160:
            # LCD mode
            return 160, 240
        if data.size == 160 * 128:
            # LCD mode
            return 128, 160
        # FIXME: Guess something closer to a square
        return 1, data.size

    def _updateImage(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        data = self._readImage(mem)
        if data is None:
            self._view.setVisible(False)
            return

        self._view.setVisible(True)
        self._view.setImage(data)

    def _readImage(self, mem: MemoryMap):
        try:
            data = self.rom.extract_lz77(mem)
        except Exception as e:
            logging.error("Error while decompressing sprite", exc_info=True)
            return None

        if mem.data_type == DataType.PALETTE:
            if data.size % 32 == 0:
                nb = data.size // 32
                data = data.view(numpy.uint16)
                data = convert_16bx1_to_5bx3(data)
                data = data / 0x1F
                data.shape = nb, -1, 3
                return data
            return data

        if mem.color_mode == ColorMode.INDEXED_4BIT:
            data = convert_8bx1_to_4bx2(data)

        if mem.shape is not None:
            try:
                data.shape = mem.shape
            except Exception:
                data.shape = self._guessFirstShape(data)
        else:
            data.shape = self._guessFirstShape(data)

        if mem.pixel_order == PixelOrder.TILED_8X8:
            if data.shape[0] % 8 != 0 or data.shape[1] % 8 != 0:
                return None
            data = convert_to_tiled_8x8(data)

        return data

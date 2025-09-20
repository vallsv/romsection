import os
import sys
import logging
import yaml
import enum
import numpy
import traceback
from PyQt5 import Qt
from silx.gui.plot.ImageView import ImageView

from .lz77 import decompress as decompress_lz77
from .utils import prime_factors, guessed_shapes
from .widgets.memory_map_list import MemoryMapList
from .widgets.image_color_mode_list import ImageColorModeList
from .widgets.shape_list import ShapeList
from .widgets.image_pixel_order_list import ImagePixelOrderList
from .widgets.data_type_list import DataTypeList
from .widgets.palette_list_model import PaletteListModel
from .widgets.combo_box import ComboBox
from .widgets.palette_combo_box import PaletteComboBox
from .gba_file import GBAFile, MemoryMap, ImageColorMode, ImagePixelOrder, DataType


class Extractor(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent)
        self._rom: GBAFile | None = None

        self._lastBySize: dict[int, MemoryMap] = {}
        self._paletteList =  PaletteListModel(self)

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

        self._paletteCombo = PaletteComboBox(self)
        self._paletteCombo.setModel(self._paletteList)
        self._paletteCombo.setMaxVisibleItems(15)
        self._paletteCombo.setSizeAdjustPolicy(
            Qt.QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self._paletteCombo.currentIndexChanged.connect(self._onPaletteSelected)

        self._colorModeList = ImageColorModeList(self)
        self._colorModeList.itemSelectionChanged.connect(self._onImageColorModeSelected)

        self._shapeList = ShapeList(self)
        self._shapeList.itemSelectionChanged.connect(self._onShapeSelected)

        self._pixelOrderList = ImagePixelOrderList(self)
        self._pixelOrderList.itemSelectionChanged.connect(self._onImagePixelOrderSelected)

        self._nothing = Qt.QWidget(self)

        self._error = Qt.QTextEdit(self)
        self._error.setReadOnly(True)
        self._error.setStyleSheet(".QTextEdit { color: red; }")

        self._array = ImageView(self, backend="gl")
        self._array.setKeepDataAspectRatio(True)
        self._array.setSideHistogramDisplayed(False)
        self._array.getYAxis().setInverted(True)

        self._view = Qt.QStackedLayout()
        self._view.addWidget(self._nothing)
        self._view.addWidget(self._array)
        self._view.addWidget(self._error)

        spriteCodec = Qt.QVBoxLayout()
        spriteCodec.addWidget(self._dataTypeList)
        spriteCodec.addWidget(self._colorModeList)
        spriteCodec.addWidget(self._paletteCombo)
        spriteCodec.addWidget(self._shapeList)
        spriteCodec.addWidget(self._pixelOrderList)
        spriteCodec.setStretchFactor(self._dataTypeList, 0)
        spriteCodec.setStretchFactor(self._paletteCombo, 0)
        spriteCodec.setStretchFactor(self._colorModeList, 0)
        spriteCodec.setStretchFactor(self._shapeList, 1)
        spriteCodec.setStretchFactor(self._pixelOrderList, 0)

        main = Qt.QHBoxLayout(self)
        main.addLayout(toolbar)
        main.addWidget(self._memList)
        main.addLayout(spriteCodec)
        main.addLayout(self._view)
        main.setStretchFactor(self._view, 1)

    def setRom(self, rom: GBAFile):
        self._rom = rom
        self._paletteList.setRom(self._rom)

    def _scanAll(self):
        self._rom.scan_all()
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

        dialog.selectFile(f"{mem.byte_offset:08X}+{mem.byte_length}.raw")
        result = dialog.exec_()
        if not result:
            return

        data = self._rom.extract_raw(mem)

        filename = dialog.selectedFiles()[0]
        with open(filename, "wb") as f:
            f.write(data)

    def _loadInfo(self):
        with open(f"{self._rom.filename}.yml", "rt") as f:
            data = yaml.safe_load(f)
        self._rom.offsets.clear()
        for m in data["mapping"]:
            mem = MemoryMap.from_dict(m)
            self._rom.offsets.append(mem)
        self._syncMemoryMapList()

    def _syncMemoryMapList(self):
        self._memList.clear()
        for mem in self._rom.offsets:
            self._memList.addMemoryMap(mem)
        availablePalettes = self._rom.palettes()
        availablePalettes.insert(0, None)
        self._paletteList.setObjectList(availablePalettes)

    def _saveInfo(self):
        mapping = []
        for mem in self._rom.offsets:
            mapping.append(mem.to_dict())
        with open(f"{self._rom.filename}.yml", "wt") as f:
            yaml.dump({"mapping": mapping}, f)

    def _onMemoryMapSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        if mem.data_type is None:
            # Compatibility with old files
            mem.data_type = DataType.IMAGE

        if mem.image_color_mode is None and mem.image_shape is None and mem.image_pixel_order is None:
            previous = self._lastBySize.get(mem.byte_payload)
            if previous is not None:
                mem.image_color_mode = previous.image_color_mode
                mem.image_shape = previous.image_shape
                mem.image_pixel_order = previous.image_pixel_order

        self._lastBySize[mem.byte_payload] = mem

        try:
            old = self._dataTypeList.blockSignals(True)
            self._dataTypeList.selectDataType(mem.data_type)
        finally:
            self._dataTypeList.blockSignals(old)

        try:
            old = self._colorModeList.blockSignals(True)
            self._colorModeList.selectImageColorMode(mem.image_color_mode)
        finally:
            self._colorModeList.blockSignals(old)

        try:
            old = self._paletteCombo.blockSignals(True)
            if mem.image_palette_offset is None:
                palette_mem = None
            else:
                try:
                    palette_mem = self._rom.memory_map_from_offset(mem.image_palette_offset)
                except ValueError:
                    logging.warning("Palette 0x{mem.image_palette_offset:08X} does not exist")
                    palette_mem = None
            self._paletteCombo.selectMemoryMap(palette_mem)
        finally:
            self._paletteCombo.blockSignals(old)

        try:
            old = self._pixelOrderList.blockSignals(True)
            self._pixelOrderList.selectImagePixelOrder(mem.image_pixel_order)
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

        image_shape = self._rom.image_shape(mem)
        if image_shape is not None:
            shapes = guessed_shapes(image_shape[0] * image_shape[1])
            try:
                old = self._shapeList.blockSignals(True)
                self._shapeList.clear()
                for shape in shapes:
                    self._shapeList.addShape(shape)
                self._shapeList.selectShape(image_shape)
            finally:
                self._shapeList.blockSignals(old)

        self._updateImage()

    def _onImageColorModeSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        items = self._colorModeList.selectedItems() 
        if len(items) != 1:
            return
        colorMode = items[0].data(Qt.Qt.UserRole)
        if mem.image_color_mode == colorMode:
            return

        previousImageColorMode = mem.image_color_mode
        mem.image_color_mode = colorMode

        if mem.image_shape is not None:
            pnb = 1 if previousImageColorMode in [None, ImageColorMode.INDEXED_8BIT] else 2
            nb = 1 if colorMode in [None, ImageColorMode.INDEXED_8BIT] else 2
            if pnb != nb:
                mem.image_shape = mem.image_shape[0], int(mem.image_shape[1] * nb / pnb)

        self._syncShapes()

    def _onShapeSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        shape = self._shapeList.selectedShape()
        mem.image_shape = shape
        self._updateImage()

    def _onImagePixelOrderSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        pixelOrder = self._pixelOrderList.selectedImagePixelOrder()
        mem.image_pixel_order = pixelOrder
        self._updateImage()

    def _onPaletteSelected(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            return

        palette_mem = self._paletteCombo.selectedMemoryMap()
        if palette_mem is None:
            mem.image_palette_offset = None
        else:
            mem.image_palette_offset = palette_mem.byte_offset

        self._updateImage()

    def _updateImage(self):
        mem = self._memList.selectedMemoryMap()
        if mem is None:
            self._view.setCurrentWidget(self._nothing)
            return

        try:
            data = self._readImage(mem)
            self._array.setImage(data)
            self._view.setCurrentWidget(self._array)
        except Exception as e:
            self._error.clear()
            for line in traceback.format_exception(e):
                self._error.append(line)
            self._view.setCurrentWidget(self._error)

    def _readImage(self, mem: MemoryMap) -> numpy.ndarray:
        """
        Return a displayable array from a memory map.

        Raises:
            Exception: In case of problem
        """
        assert self._rom is not None
        if mem.data_type == DataType.PALETTE:
            return self._rom.palette_data(mem)

        if mem.data_type == DataType.IMAGE:
            return self._rom.image_data(mem)

        raise ValueError(f"No image representation for memory map of type {mem.data_type}")

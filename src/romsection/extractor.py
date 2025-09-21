import os
import sys
import logging
import yaml
import enum
import typing
import numpy
import traceback
import contextlib
from PyQt5 import Qt
from silx.gui.plot.ImageView import ImageView

from .lz77 import decompress as decompress_lz77
from .utils import prime_factors, guessed_shapes
from .widgets.memory_map_list_view import MemoryMapListView
from .widgets.memory_map_list_model import MemoryMapListModel
from .widgets.image_color_mode_list import ImageColorModeList
from .widgets.shape_list import ShapeList
from .widgets.image_pixel_order_list import ImagePixelOrderList
from .widgets.data_type_list import DataTypeList
from .widgets.palette_list_model import PaletteListModel
from .widgets.combo_box import ComboBox
from .widgets.palette_combo_box import PaletteComboBox
from .gba_file import GBAFile, MemoryMap, ImageColorMode, ImagePixelOrder, DataType


@contextlib.contextmanager
def blockSignals(widget: Qt.QWidget):
    try:
        old = widget.blockSignals(True)
        yield
    finally:
        widget.blockSignals(old)


class Extractor(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent)
        self._rom: GBAFile | None = None

        self._lastBySize: dict[int, MemoryMap] = {}
        self._paletteList =  PaletteListModel(self)
        self._memoryMapList = MemoryMapListModel(self)

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

        self._memView = MemoryMapListView(self)
        self._memView.setModel(self._memoryMapList)
        self._memView.selectionModel().selectionChanged.connect(self._onMemoryMapSelectionChanged)
        self._memView.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self._memView.customContextMenuRequested.connect(self._showSpriteContextMenu)
        self._memView.setSelectionMode(Qt.QAbstractItemView.ExtendedSelection)

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
        main.addWidget(self._memView)
        main.addLayout(spriteCodec)
        main.addLayout(self._view)
        main.setStretchFactor(self._view, 1)

        self._updateNoMemoryMapSelected()

    def setRom(self, rom: GBAFile):
        self._rom = rom
        self._paletteList.setRom(self._rom)

    def _scanAll(self):
        self._rom.scan_all()
        self._syncSpriteList()

    def _showSpriteContextMenu(self, pos: Qt.QPoint):
        globalPos = self._memView.mapToGlobal(pos)
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

        mem = self._memView.selectedMemoryMap()
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
        self._updateMemoryMapList()

    def _updateMemoryMapList(self):
        self._memoryMapList.setObjectList(self._rom.offsets)
        availablePalettes = self._rom.palettes()
        availablePalettes.insert(0, None)
        self._paletteList.setObjectList(availablePalettes)

    def _saveInfo(self):
        mapping = []
        for mem in self._rom.offsets:
            mapping.append(mem.to_dict())
        with open(f"{self._rom.filename}.yml", "wt") as f:
            yaml.dump({"mapping": mapping}, f)

    def _onMemoryMapSelectionChanged(self):
        # NOTE: Debounce the even in order to sync selection change and
        #       current item. Else the current item is not uptodate.
        Qt.QTimer.singleShot(0, self._debouncedMemoryMapSelectionChanged)

    def _debouncedMemoryMapSelectionChanged(self):
        mems = self._memView.selectedMemoryMaps()
        if len(mems) == 0:
            self._updateNoMemoryMapSelected()
        elif len(mems) == 1:
            self._updateMemoryMapSelected(mems[0])
        else:
            self._updateMultipleMemoryMapSelected(mems)

    def _updateNoMemoryMapSelected(self):
        self._dataTypeList.setEnabled(False)
        self._colorModeList.setEnabled(False)
        self._paletteCombo.setEnabled(False)
        self._shapeList.setEnabled(False)
        self._pixelOrderList.setEnabled(False)
        with blockSignals(self._dataTypeList):
            self._dataTypeList.selectDataType(None)
        with blockSignals(self._colorModeList):
            self._colorModeList.selectImageColorMode(None)
        with blockSignals(self._paletteCombo):
            self._paletteCombo.selectMemoryMap(None)
        with blockSignals(self._shapeList):
            self._shapeList.clear()
        with blockSignals(self._pixelOrderList):
            self._pixelOrderList.selectImagePixelOrder(None)
        self._view.setCurrentWidget(self._nothing)

    def _updateMultipleMemoryMapSelected(self, mems: list[MemoryMap]):
        """Allow to display and edit as much as possible.

        FIXME: Support display and edition of shape on some conditions
        """
        assert self._rom is not None
        self._dataTypeList.setEnabled(True)
        self._colorModeList.setEnabled(True)
        self._paletteCombo.setEnabled(True)
        self._shapeList.setEnabled(False)
        self._pixelOrderList.setEnabled(True)

        def uniqueValueElseNone(data: list[typing.Any]):
            reduced = set(data)
            if len(reduced) == 1:
                return data[0]
            return None

        with blockSignals(self._dataTypeList):
            reducedDataType = uniqueValueElseNone([m.data_type for m in mems])
            self._dataTypeList.selectDataType(reducedDataType)
        with blockSignals(self._colorModeList):
            reducedColorMode = uniqueValueElseNone([m.image_color_mode for m in mems])
            self._colorModeList.selectImageColorMode(reducedColorMode)
        with blockSignals(self._paletteCombo):
            reducedOffset = uniqueValueElseNone([m.image_palette_offset for m in mems])
            palette_mem = None
            if reducedOffset is not None:
                try:
                    palette_mem = self._rom.memory_map_from_offset(reducedOffset)
                except ValueError:
                    logging.warning("Palette 0x{mem.image_palette_offset:08X} does not exist")
                    palette_mem = None
            self._paletteCombo.selectMemoryMap(palette_mem)
        with blockSignals(self._shapeList):
            self._shapeList.clear()
        with blockSignals(self._pixelOrderList):
            reducedPixelOrder = uniqueValueElseNone([m.image_pixel_order for m in mems])
            self._pixelOrderList.selectImagePixelOrder(reducedPixelOrder)

        self._updateImage()

    def _updateMemoryMapSelected(self, mem: MemoryMap):
        assert self._rom is not None
        self._dataTypeList.setEnabled(True)
        self._colorModeList.setEnabled(True)
        self._paletteCombo.setEnabled(True)
        self._shapeList.setEnabled(True)
        self._pixelOrderList.setEnabled(True)

        if mem.byte_payload is not None:
            if mem.image_color_mode is None and mem.image_shape is None and mem.image_pixel_order is None:
                previous = self._lastBySize.get(mem.byte_payload)
                if previous is not None:
                    mem.image_color_mode = previous.image_color_mode
                    mem.image_shape = previous.image_shape
                    mem.image_pixel_order = previous.image_pixel_order

            self._lastBySize[mem.byte_payload] = mem

        with blockSignals(self._dataTypeList):
            self._dataTypeList.selectDataType(mem.data_type)

        with blockSignals(self._colorModeList):
            self._colorModeList.selectImageColorMode(mem.image_color_mode)

        with blockSignals(self._paletteCombo):
            image_palette_offset = mem.image_palette_offset
            if mem.image_palette_offset is None:
                palette_mem = None
            else:
                try:
                    palette_mem = self._rom.memory_map_from_offset(mem.image_palette_offset)
                except ValueError:
                    logging.warning("Palette 0x{mem.image_palette_offset:08X} does not exist")
                    palette_mem = None
            self._paletteCombo.selectMemoryMap(palette_mem)

        with blockSignals(self._pixelOrderList):
            self._pixelOrderList.selectImagePixelOrder(mem.image_pixel_order)

        self._updateShapes()
        self._updateImage()

    def _onDataTypeSelected(self):
        dataType = self._dataTypeList.selectedDataType()
        if dataType is None:
            return
        for mem in self._memView.selectedMemoryMaps():
            mem.data_type = dataType

        self._updateShapes()
        self._updateImage()

    def _updateShapes(self):
        mems = self._memView.selectedMemoryMaps()
        if len(mems) == 0:
            self._shapeList.setEnabled(False)
            with blockSignals(self._shapeList):
                self._shapeList.clear()
        elif len(mems) == 1:
            mem = mems[0]
            if mem.data_type != DataType.IMAGE:
                self._shapeList.setEnabled(False)
                with blockSignals(self._shapeList):
                    self._shapeList.clear()
            else:
                self._shapeList.setEnabled(True)
                image_shape = self._rom.image_shape(mem)
                with blockSignals(self._shapeList):
                    self._shapeList.clear()
                    if image_shape is not None:
                        shapes = guessed_shapes(image_shape[0] * image_shape[1])
                        for shape in shapes:
                            self._shapeList.addShape(shape)
                        self._shapeList.selectShape(image_shape)
        else:
            self._shapeList.setEnabled(False)
            with blockSignals(self._shapeList):
                self._shapeList.clear()

    def _onImageColorModeSelected(self):
        colorMode = self._colorModeList.selectedImageColorMode()
        for mem in self._memView.selectedMemoryMaps():
            if mem.image_color_mode == colorMode:
                continue

            previousImageColorMode = mem.image_color_mode
            mem.image_color_mode = colorMode

            if mem.image_shape is not None:
                pnb = 1 if previousImageColorMode in [None, ImageColorMode.INDEXED_8BIT] else 2
                nb = 1 if colorMode in [None, ImageColorMode.INDEXED_8BIT] else 2
                if pnb != nb:
                    mem.image_shape = mem.image_shape[0], int(mem.image_shape[1] * nb / pnb)

        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        self._updateShapes()
        self._updateImage()

    def _onShapeSelected(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return

        shape = self._shapeList.selectedShape()
        mem.image_shape = shape
        self._updateImage()

    def _onImagePixelOrderSelected(self):
        pixelOrder = self._pixelOrderList.selectedImagePixelOrder()
        for mem in self._memView.selectedMemoryMaps():
            mem.image_pixel_order = pixelOrder
        self._updateImage()

    def _onPaletteSelected(self):
        palette_mem = self._paletteCombo.selectedMemoryMap()
        for mem in self._memView.selectedMemoryMaps():
            if palette_mem is None:
                mem.image_palette_offset = None
            else:
                mem.image_palette_offset = palette_mem.byte_offset
        self._updateImage()

    def _updateImage(self):
        mem = self._memView.currentMemoryMap()
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

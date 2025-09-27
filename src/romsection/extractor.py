import os
import io
import sys
import logging
import rtoml
import enum
import typing
import numpy
import traceback
import contextlib
from PyQt5 import Qt

from .lz77 import decompress as decompress_lz77
from .utils import prime_factors, guessed_shapes
from .widgets.memory_map_list_view import MemoryMapListView
from .widgets.memory_map_list_model import MemoryMapListModel
from .widgets.image_color_mode_list import ImageColorModeList
from .widgets.shape_list import ShapeList
from .widgets.image_pixel_order_list import ImagePixelOrderList
from .widgets.byte_codec_list import ByteCodecList
from .widgets.data_type_list import DataTypeList
from .widgets.palette_filter_proxy_model import PaletteFilterProxyModel
from .widgets.combo_box import ComboBox
from .widgets.palette_combo_box import PaletteComboBox
from .widgets.gba_rom_header_view import GbaRomHeaderView
from .widgets.sprite_view import SpriteView
from .widgets.hexa_view import HexaView
from .widgets.palette_size_list import PaletteSizeList
from .widgets.pixel_browser import PixelBrowser
from .gba_file import GBAFile, MemoryMap, ImageColorMode, ImagePixelOrder, DataType


@contextlib.contextmanager
def blockSignals(widget: Qt.QWidget):
    try:
        old = widget.blockSignals(True)
        yield
    finally:
        widget.blockSignals(old)


def uniqueValueElseNone(data: list[typing.Any]):
    reduced = set(data)
    if len(reduced) == 1:
        return data[0]
    return None


class Extractor(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent)
        self._rom: GBAFile | None = None

        self._lastBySize: dict[int, MemoryMap] = {}
        self._memoryMapList = MemoryMapListModel(self)
        self._paletteList =  PaletteFilterProxyModel(self)
        self._paletteList.setSourceModel(self._memoryMapList)

        toolbar = Qt.QVBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
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

        extractUnknown = Qt.QPushButton(self)
        extractUnknown.clicked.connect(self._extractUnknown)
        extractUnknown.setText("Extract unknown")
        toolbar.addWidget(extractUnknown)

        removeUnknown = Qt.QPushButton(self)
        removeUnknown.clicked.connect(self._removeUnknown)
        removeUnknown.setText("Remove unknown")
        toolbar.addWidget(removeUnknown)

        toolbar.addStretch(1)

        self._memView = MemoryMapListView(self)
        self._memView.setModel(self._memoryMapList)
        self._memView.selectionModel().selectionChanged.connect(self._onMemoryMapSelectionChanged)
        self._memView.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self._memView.customContextMenuRequested.connect(self._showMemoryMapContextMenu)
        self._memView.setSelectionMode(Qt.QAbstractItemView.ExtendedSelection)

        self._byteCodecList = ByteCodecList(self)
        self._byteCodecList.itemSelectionChanged.connect(self._onByteCodecSelected)

        self._dataTypeList = DataTypeList(self)
        self._dataTypeList.itemSelectionChanged.connect(self._onDataTypeSelected)

        self._paletteSizeList = PaletteSizeList(self)
        self._paletteSizeList.itemSelectionChanged.connect(self._onPaletteSizeSelected)

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

        self._image = SpriteView(self)

        self._header = GbaRomHeaderView(self)

        self._hexa = HexaView(self)
        self._hexa.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self._hexa.customContextMenuRequested.connect(self._showHexaContextMenu)

        self._pixelBrowser = PixelBrowser(self)

        self._view = Qt.QStackedLayout()
        self._view.addWidget(self._nothing)
        self._view.addWidget(self._image)
        self._view.addWidget(self._error)
        self._view.addWidget(self._header)
        self._view.addWidget(self._hexa)
        self._view.addWidget(self._pixelBrowser)

        spriteCodec = Qt.QVBoxLayout()
        spriteCodec.setContentsMargins(0, 0, 0, 0)
        spriteCodec.addWidget(self._byteCodecList)
        spriteCodec.addWidget(self._dataTypeList)
        spriteCodec.addWidget(self._paletteSizeList)
        spriteCodec.addWidget(self._colorModeList)
        spriteCodec.addWidget(self._paletteCombo)
        spriteCodec.addWidget(self._shapeList)
        spriteCodec.addWidget(self._pixelOrderList)
        spriteCodec.setStretchFactor(self._byteCodecList, 0)
        spriteCodec.setStretchFactor(self._dataTypeList, 0)
        spriteCodec.setStretchFactor(self._paletteSizeList, 0)
        spriteCodec.setStretchFactor(self._paletteCombo, 0)
        spriteCodec.setStretchFactor(self._colorModeList, 0)
        spriteCodec.setStretchFactor(self._shapeList, 1)
        spriteCodec.setStretchFactor(self._pixelOrderList, 0)
        spriteCodec.addStretch(1)

        main = Qt.QHBoxLayout(self)
        main.addLayout(toolbar)
        main.addWidget(self._memView)
        main.addLayout(spriteCodec)
        main.addLayout(self._view)
        main.setStretchFactor(self._view, 1)

        self._updateNoMemoryMapSelected()

    def _extractUnknown(self):
        offsets = list(self._rom.offsets)
        # offsets = sorted(offsets, keys=lambda v: v.byte_offset)
        mem_end = MemoryMap(
            byte_offset=self._rom.size,
            byte_length=1,
            data_type=DataType.UNKNOWN,
        )
        offsets.append(mem_end)

        current_offset = 0
        index = 0
        for offset in offsets:
            if offset.byte_offset < current_offset:
                index += 1
                continue
            if current_offset != offset.byte_offset:
                length = offset.byte_offset - current_offset
                mem = MemoryMap(
                    byte_offset=current_offset,
                    byte_length=length,
                    data_type=DataType.UNKNOWN,
                )
                self._memoryMapList.insertObject(index, mem)
                index += 1
            index += 1
            current_offset = offset.byte_offset + (offset.byte_length or 1)

    def _removeUnknown(self):
        for mem in self._rom.offsets:
            if mem.data_type == DataType.UNKNOWN:
                self._memoryMapList.removeObject(mem)

    def setRom(self, rom: GBAFile):
        self._rom = rom
        self._paletteList.setRom(self._rom)

    def _scanAll(self):
        Qt.QGuiApplication.setOverrideCursor(Qt.QCursor(Qt.Qt.WaitCursor))
        try:
            self._rom.scan_all()
            self._updateMemoryMapList()
        finally:
            Qt.QGuiApplication.restoreOverrideCursor()

    def _showMemoryMapContextMenu(self, pos: Qt.QPoint):
        globalPos = self._memView.mapToGlobal(pos)
        menu = Qt.QMenu(self)

        mems = self._memView.selectedMemoryMaps()

        remove = Qt.QAction(menu)
        remove.setText("Remove memory map")
        remove.triggered.connect(self._removeMemoryMap)
        menu.addAction(remove)

        if len(mems) == 1:
            menu.addSeparator()

            rawHexa = Qt.QAction(menu)
            rawHexa.setText("Show raw as hexa")
            rawHexa.triggered.connect(self._showMemoryMapRawAsHexa)
            menu.addAction(rawHexa)

            dataHexa = Qt.QAction(menu)
            dataHexa.setText("Show data as hexa")
            dataHexa.triggered.connect(self._showMemoryMapDataAsHexa)
            menu.addAction(dataHexa)

            saveRaw = Qt.QAction(menu)
            saveRaw.setText("Save as raw...")
            saveRaw.triggered.connect(self._saveMemoryMapAsRaw)
            menu.addAction(saveRaw)

            saveDat = Qt.QAction(menu)
            saveDat.setText("Save as dat...")
            saveDat.triggered.connect(self._saveMemoryMapAsDat)
            menu.addAction(saveDat)

        menu.exec(globalPos)

    def _removeMemoryMap(self):
        """Save the memory as it is stored (compressed) into a file"""
        mems = self._memView.selectedMemoryMaps()
        if len(mems) == 0:
            return

        if len(mems) == 1:
            msg = f"the memory map {mems[0].byte_offset:08X}"
        else:
            msg = f"{len(mems)} memory maps"

        button = Qt.QMessageBox.question(
            None,
            "Confirm remove",
            f"Do you really want to remove {msg}?",
            Qt.QMessageBox.Yes | Qt.QMessageBox.No,
        )
        if button != Qt.QMessageBox.Yes:
            return

        for mem in mems:
            self._memoryMapList.removeObject(mem)

    def _showMemoryMapRawAsHexa(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        data = self._rom.extract_raw(mem)
        self._hexa.setData(data, address=mem.byte_offset)
        self._view.setCurrentWidget(self._hexa)

    def _showMemoryMapDataAsHexa(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        data = self._rom.extract_data(mem)
        self._hexa.setData(data, address=mem.byte_offset)
        self._view.setCurrentWidget(self._hexa)

    def _saveMemoryMapAsRaw(self):
        """Save the memory as it is stored (compressed) into a file"""
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

    def _saveMemoryMapAsDat(self):
        """Save the decompressed memory into a file"""
        dialog = Qt.QFileDialog(self)
        dialog.setWindowTitle("Save as DAT")
        dialog.setModal(True)
        filters = [
            "RAW files (*.dat)",
            "All files (*)",
        ]
        dialog.setNameFilters(filters)
        dialog.setFileMode(Qt.QFileDialog.AnyFile)
        dialog.setAcceptMode(Qt.QFileDialog.AcceptSave)

        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return

        dialog.selectFile(f"{mem.byte_offset:08X}+{mem.byte_length}.dat")
        result = dialog.exec_()
        if not result:
            return

        data = self._rom.extract_data(mem)

        filename = dialog.selectedFiles()[0]
        with open(filename, "wb") as f:
            f.write(data.tobytes())

    def _showHexaContextMenu(self, pos: Qt.QPoint):
        globalPos = self._hexa.mapToGlobal(pos)
        menu = Qt.QMenu(self)

        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return

        offset = self._hexa.selectedOffset()
        if offset is None:
            return

        split = Qt.QAction(menu)
        split.setText("Split memory map before this address")
        split.triggered.connect(self._splitMemoryMap)
        menu.addAction(split)

        menu.exec(globalPos)

    def _splitMemoryMap(self):
        """Split the memory map at the selection"""
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return

        offset = self._hexa.selectedOffset()
        if offset is None:
            return

        prevMem = MemoryMap(
            byte_offset=mem.byte_offset,
            byte_length=offset - mem.byte_offset,
            data_type=DataType.UNKNOWN,
        )

        nextMem = MemoryMap(
            byte_offset=offset,
            byte_length=mem.byte_offset + mem.byte_length - offset,
            data_type=DataType.UNKNOWN,
        )

        index = self._memoryMapList.objectIndex(mem).row()
        self._memoryMapList.removeObject(mem)
        self._memoryMapList.insertObject(index, prevMem)
        self._memoryMapList.insertObject(index + 1, nextMem)

    def _loadInfo(self):
        try:
            with open(f"{self._rom.filename}.toml", "rt") as f:
                data = rtoml.load(f)
            self._rom.offsets.clear()
            for k, v in data.items():
                if k.startswith("memory_map:"):
                    mem = MemoryMap.from_dict(v)
                    self._rom.offsets.append(mem)
        except Exception:
            # FIXME: Display it in a dialog
            logging.error("Error while loading file", exc_info=True)
        self._updateMemoryMapList()

    def _updateMemoryMapList(self):
        self._memoryMapList.setObjectList(self._rom.offsets)

    def _saveInfo(self):
        try:
            data = {}
            for mem in self._rom.offsets:
                data[f"memory_map:{mem.byte_offset:08X}"] = mem.to_dict()
            with open(f"{self._rom.filename}.toml", "wt") as f:
                rtoml.dump(data, f)
        except Exception:
            # FIXME: Display it in a dialog
            logging.error("Error while saving file", exc_info=True)

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
        self._byteCodecList.setEnabled(False)
        self._dataTypeList.setEnabled(False)
        self._colorModeList.setEnabled(False)
        self._paletteCombo.setEnabled(False)
        self._shapeList.setEnabled(False)
        self._pixelOrderList.setEnabled(False)
        self._paletteSizeList.setEnabled(False)
        with blockSignals(self._byteCodecList):
            self._byteCodecList.selectByteCodec(None)
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
        with blockSignals(self._paletteSizeList):
            self._paletteSizeList.selectPaletteSize(None)
        self._view.setCurrentWidget(self._nothing)

    def _updateMultipleMemoryMapSelected(self, mems: list[MemoryMap]):
        """
        Allow to display and edit as much as possible.
        """
        assert self._rom is not None
        self._byteCodecList.setEnabled(True)
        self._dataTypeList.setEnabled(True)
        self._colorModeList.setEnabled(True)
        self._paletteCombo.setEnabled(True)
        self._pixelOrderList.setEnabled(True)
        self._paletteSizeList.setEnabled(True)

        with blockSignals(self._byteCodecList):
            reducedByteCodec = uniqueValueElseNone([m.byte_codec for m in mems])
            self._byteCodecList.selectByteCodec(reducedByteCodec)
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
        with blockSignals(self._pixelOrderList):
            reducedPixelOrder = uniqueValueElseNone([m.image_pixel_order for m in mems])
            self._pixelOrderList.selectImagePixelOrder(reducedPixelOrder)
        with blockSignals(self._paletteSizeList):
            reducedPaletteSize = uniqueValueElseNone([m.palette_size for m in mems])
            self._paletteSizeList.selectPaletteSize(reducedPaletteSize)

        self._updateWidgets()
        self._updateShapes()
        self._updateImage()

    def _updateMemoryMapSelected(self, mem: MemoryMap):
        assert self._rom is not None
        self._byteCodecList.setEnabled(True)
        self._dataTypeList.setEnabled(True)
        self._colorModeList.setEnabled(True)
        self._paletteCombo.setEnabled(True)
        self._shapeList.setEnabled(True)
        self._pixelOrderList.setEnabled(True)
        self._paletteSizeList.setEnabled(True)

        if mem.byte_payload is not None:
            if mem.image_color_mode is None and mem.image_shape is None and mem.image_pixel_order is None:
                previous = self._lastBySize.get(mem.byte_payload)
                if previous is not None:
                    mem.image_color_mode = previous.image_color_mode
                    mem.image_shape = previous.image_shape
                    mem.image_pixel_order = previous.image_pixel_order

            self._lastBySize[mem.byte_payload] = mem

        with blockSignals(self._byteCodecList):
            self._byteCodecList.selectByteCodec(mem.byte_codec)

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

        with blockSignals(self._paletteSizeList):
            self._paletteSizeList.selectPaletteSize(mem.palette_size)

        self._updateWidgets()
        self._updateShapes()
        self._updateImage()

    def _onByteCodecSelected(self):
        byteCodec = self._byteCodecList.selectedByteCodec()
        if byteCodec is None:
            return
        for mem in self._memView.selectedMemoryMaps():
            mem.byte_codec = byteCodec
            mem.byte_payload = None
            self._memoryMapList.updatedObject(mem)

        self._updateShapes()
        self._updateImage()

    def _onDataTypeSelected(self):
        dataType = self._dataTypeList.selectedDataType()
        if dataType is None:
            return
        for mem in self._memView.selectedMemoryMaps():
            mem.data_type = dataType
            self._memoryMapList.updatedObject(mem)

        self._updateWidgets()
        self._updateShapes()
        self._updateImage()

    def _onPaletteSizeSelected(self):
        paletteSize = self._paletteSizeList.selectedPaletteSize()
        if paletteSize is None:
            return
        for mem in self._memView.selectedMemoryMaps():
            mem.palette_size = paletteSize
            self._memoryMapList.updatedObject(mem)

        self._updateWidgets()
        self._updateShapes()
        self._updateImage()

    def _updateWidgets(self):
        dataType = self._dataTypeList.selectedDataType()
        self._paletteSizeList.setVisible(dataType == DataType.PALETTE)
        self._colorModeList.setVisible(dataType == DataType.IMAGE)
        self._paletteCombo.setVisible(dataType == DataType.IMAGE)
        self._shapeList.setVisible(dataType == DataType.IMAGE)
        self._pixelOrderList.setVisible(dataType == DataType.IMAGE)

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
            reducedDataType = uniqueValueElseNone([m.data_type for m in mems])
            reducedBytePayload = uniqueValueElseNone([m.byte_payload for m in mems])
            reducedColorMap = uniqueValueElseNone([m.image_color_mode for m in mems])

            if reducedDataType != DataType.IMAGE or reducedBytePayload is None or reducedColorMap is None:
                self._shapeList.setEnabled(False)
                with blockSignals(self._shapeList):
                    self._shapeList.clear()
            else:
                reducedShape = uniqueValueElseNone([m.image_shape for m in mems])
                self._shapeList.setEnabled(True)
                with blockSignals(self._shapeList):
                    self._shapeList.clear()
                    if reducedShape is not None:
                        shapes = guessed_shapes(reducedShape[0] * reducedShape[1])
                        for shape in shapes:
                            self._shapeList.addShape(shape)
                        self._shapeList.selectShape(reducedShape)

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
        shape = self._shapeList.selectedShape()
        for mem in self._memView.selectedMemoryMaps():
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
            if mem.data_type == DataType.GBA_ROM_HEADER:
                data = self._rom.extract_raw(mem)
                self._header.setMemory(data)
                self._view.setCurrentWidget(self._header)
            elif mem.data_type == DataType.PADDING:
                data = self._rom.extract_raw(mem)
                self._hexa.setData(data, address=mem.byte_offset)
                self._view.setCurrentWidget(self._hexa)
            elif mem.data_type == DataType.UNKNOWN:
                data = self._rom.extract_data(mem)
                memory = io.BytesIO(data.tobytes())
                self._pixelBrowser.setMemory(memory)
                self._view.setCurrentWidget(self._pixelBrowser)
            else:
                data = self._readImage(mem)
                self._image.setData(data)
                self._view.setCurrentWidget(self._image)
        except Exception as e:
            self._image.setData(None)
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
            result = self._rom.palette_data(mem)
            # FIXME: Handle explicitly 16 and 256
            result.shape = -1, 16, result.shape[2]
            return result

        if mem.data_type == DataType.IMAGE:
            return self._rom.image_data(mem)

        raise ValueError(f"No image representation for memory map of type {mem.data_type}")

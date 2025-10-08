import os
import io
import sys
import logging
import rtoml
import enum
import typing
import numpy
import traceback
import queue
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
from .widgets.tile_set_browser import TileSetBrowser
from .widgets.sample_browser import SampleBrowser
from .widgets.music_browser import MusicBrowser
from .widgets.sample_view import SampleView
from .widgets.music_view import MusicView
from .gba_file import GBAFile, ByteCodec, MemoryMap, ImageColorMode, ImagePixelOrder, DataType
from .qt_utils import blockSignals, exceptionAsMessageBox
from .path_utils import resolve_abspath
from .behaviors import file_dialog
from .behaviors import search_lz77
from .behaviors import sappy_content
from .behaviors import unknown_content


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

        self._dialogDirectory = os.getcwd()
        self._filename: str | None = None

        style = Qt.QApplication.style()
        toolbar = Qt.QToolBar(self)

        loadAction = Qt.QAction(self)
        loadAction.triggered.connect(self.loadFromDialog)
        loadAction.setText("Load a ROM / a ROM dissection (TOML)")
        loadAction.setIcon(Qt.QIcon("icons:load.png"))
        toolbar.addAction(loadAction)

        saveAction = Qt.QAction(self)
        saveAction.triggered.connect(self.save)
        saveAction.setText("Save the ROM dissection")
        saveAction.setIcon(Qt.QIcon("icons:save.png"))
        toolbar.addAction(saveAction)

        saveAsAction = Qt.QAction(self)
        saveAsAction.triggered.connect(self.saveAs)
        saveAsAction.setText("Save the ROM dissection into another file")
        saveAsAction.setIcon(Qt.QIcon("icons:save-as.png"))
        toolbar.addAction(saveAsAction)

        spacer = Qt.QWidget(toolbar)
        spacer.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)
        toolbar.addWidget(spacer)

        toolButton = Qt.QToolButton(self)
        toolButton.setPopupMode(Qt.QToolButton.InstantPopup)
        toolButton.setIcon(Qt.QIcon("icons:tool.png"))
        toolbar.addWidget(toolButton)

        toolMenu = Qt.QMenu(toolbar)
        toolButton.setMenu(toolMenu)

        self.__searchSappyContent = sappy_content.SearchSappyTag()
        self.__searchSappyContent.setContext(self)
        self.__splitSappySample = sappy_content.SplitSappySample()
        self.__splitSappySample.setContext(self)

        self.__createUncovered = unknown_content.CreateUncoveredMemory()
        self.__createUncovered.setContext(self)

        self.__replaceUnknownByPadding = unknown_content.ReplaceUnknownByPadding()
        self.__replaceUnknownByPadding.setContext(self)

        self.__removeUnknown = unknown_content.RemoveUnknown()
        self.__removeUnknown.setContext(self)

        action = Qt.QAction(self)
        action.triggered.connect(self.__createUncovered.run)
        action.setText("Create sections for unmapped memory")
        action.setIcon(Qt.QIcon("icons:unknown.png"))
        toolMenu.addAction(action)

        action = Qt.QAction(self)
        action.triggered.connect(self.__removeUnknown.run)
        action.setText("Remove unknown mapped sections")
        action.setIcon(Qt.QIcon("icons:unknown-remove.png"))
        toolMenu.addAction(action)

        toolMenu.addSeparator()

        action = Qt.QAction(self)
        action.triggered.connect(self.__searchSappyContent.run)
        action.setText("Search for sappy content")
        action.setIcon(Qt.QIcon("icons:music.png"))
        toolMenu.addAction(action)

        action = Qt.QAction(self)
        action.triggered.connect(self.__replaceUnknownByPadding.run)
        action.setText("Replace matching unknown by padding")
        action.setIcon(Qt.QIcon("icons:padding.png"))
        toolMenu.addAction(action)

        self._memView = MemoryMapListView(self)
        self._memView.setModel(self._memoryMapList)
        self._memView.selectionModel().selectionChanged.connect(self._onMemoryMapSelectionChanged)
        self._memView.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self._memView.customContextMenuRequested.connect(self._showMemoryMapContextMenu)

        self._byteCodecList = ByteCodecList(self)
        self._byteCodecList.itemSelectionChanged.connect(self._onByteCodecSelected)

        self._dataTypeList = DataTypeList(self)
        self._dataTypeList.itemSelectionChanged.connect(self._onDataTypeSelected)
        self._dataTypeList.setMinimumWidth(180)
        self._dataTypeList.setMaximumWidth(180)

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

        self._pixelOrderList = ImagePixelOrderList(self)
        self._pixelOrderList.itemSelectionChanged.connect(self._onImagePixelOrderSelected)

        self._shapeList = ShapeList(self)
        self._shapeList.itemSelectionChanged.connect(self._onShapeSelected)
        self._shapeList.setMinimumWidth(180)
        self._shapeList.setMaximumWidth(180)

        self._nothing = Qt.QWidget(self)

        self._error = Qt.QTextEdit(self)
        self._error.setReadOnly(True)
        self._error.setStyleSheet(".QTextEdit { color: red; }")

        self._image = SpriteView(self)

        self._tilesetBrowser = TileSetBrowser(self)

        self._header = GbaRomHeaderView(self)

        self._hexa = HexaView(self)
        self._hexa.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self._hexa.customContextMenuRequested.connect(self._showHexaContextMenu)

        self._pixelBrowser = PixelBrowser(self)
        self._pixelBrowser.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self._pixelBrowser.customContextMenuRequested.connect(self._showPixelBrowserContextMenu)

        self._sampleBrowser = SampleBrowser(self)
        self._musicBrowser = MusicBrowser(self)
        self._sampleView = SampleView(self)
        self._musicView = MusicView(self)

        self._view = Qt.QStackedLayout()
        self._view.addWidget(self._nothing)
        self._view.addWidget(self._image)
        self._view.addWidget(self._tilesetBrowser)
        self._view.addWidget(self._error)
        self._view.addWidget(self._header)
        self._view.addWidget(self._hexa)
        self._view.addWidget(self._pixelBrowser)
        self._view.addWidget(self._sampleBrowser)
        self._view.addWidget(self._musicBrowser)
        self._view.addWidget(self._sampleView)
        self._view.addWidget(self._musicView)

        leftLayout = Qt.QVBoxLayout()
        leftLayout.addWidget(toolbar)
        leftLayout.addWidget(self._memView)

        spriteCodec = Qt.QVBoxLayout()
        spriteCodec.setContentsMargins(0, 0, 0, 0)
        spriteCodec.addWidget(self._byteCodecList)
        spriteCodec.addWidget(self._dataTypeList)
        spriteCodec.addWidget(self._paletteSizeList)
        spriteCodec.addWidget(self._colorModeList)
        spriteCodec.addWidget(self._pixelOrderList)
        spriteCodec.addWidget(self._paletteCombo)
        spriteCodec.addWidget(self._shapeList)
        spriteCodec.setStretchFactor(self._shapeList, 1)
        spriteCodec.addStretch(0)

        main = Qt.QHBoxLayout(self)
        main.addLayout(leftLayout)
        main.addLayout(spriteCodec)
        main.addLayout(self._view)
        main.setStretchFactor(self._view, 1)

        self.setRom(None)

    def loadFromDialog(self):
        filename = file_dialog.getTomlOrRomFilenameFromDialog(self)
        if filename is None:
            return
        self.loadFilename(filename)

    def loadFilename(self, filename: str):
        with exceptionAsMessageBox():
            if filename.endswith(".toml"):
                self._loadTomlFile(filename)
            else:
                self._loadRomFile(filename)

    def _loadRomFile(self, filename: str):
        try:
            rom = GBAFile(filename)
        except Exception:
            raise
        else:
            header = MemoryMap(
                byte_offset=0,
                byte_codec=ByteCodec.RAW,
                byte_length=192,
                data_type=DataType.GBA_ROM_HEADER,
            )
            other = MemoryMap(
                byte_offset=header.byte_end,
                byte_codec=ByteCodec.RAW,
                byte_length=rom.size - header.byte_length,
                data_type=DataType.UNKNOWN,
            )
            rom.offsets.append(header)
            rom.offsets.append(other)
            self.setRom(rom)

    def _loadTomlFile(self, filename: str):
        localDirectory = os.path.dirname(filename)
        with exceptionAsMessageBox():
            try:
                with open(filename, "rt") as f:
                    data = rtoml.load(f)
                try:
                    romInfo = data["rom"]
                    gameTitle = romInfo["game_title"]
                    romFilename = romInfo.get("local_filename")
                except Exception:
                    raise RuntimeError(f"Invalid file format '{filename}'")

                if romFilename is None:
                    Qt.QMessageBox.warning(self, "Error", "No ROM file defined")
                else:
                    romFilename = resolve_abspath(romFilename, localDirectory)
                    if not os.path.exists(romFilename):
                        Qt.QMessageBox.warning(self, "Error", f"ROM file for '{gameTitle}' not found")
                        romFilename = None
                if romFilename is None:
                    romFilename = file_dialog.getRomFilenameFromDialog(self)
                    if romFilename is None:
                        return

                rom = GBAFile(romFilename)
                for k, v in data.items():
                    if k.startswith("memory_map:"):
                        mem = MemoryMap.from_dict(v)
                        rom.offsets.append(mem)
            except Exception:
                raise
            else:
                self._filename = filename
                self.setRom(rom)

    def rom(self) -> GBAFile | None:
        return self._rom

    def setRom(self, rom: GBAFile | None):
        self._rom = rom
        self._paletteList.setRom(rom)
        self._sampleView.setRom(rom)
        self._musicView.setRom(rom)
        if rom is None:
            self._memoryMapList.setObjectList([])
            self.setWindowTitle("No ROM loaded")
        else:
            self._memoryMapList.setObjectList(rom.offsets)
            filename = os.path.basename(rom.filename)
            self.setWindowTitle(filename)
        self._updateNoMemoryMapSelected()

    def memoryMapList(self) -> MemoryMapListModel:
        return self._memoryMapList

    def _searchLZ77(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return

        assert self._rom is not None

        memoryMapQueue: queue.Queue[MemoryMap] = queue.Queue()

        Qt.QGuiApplication.setOverrideCursor(Qt.QCursor(Qt.Qt.WaitCursor))
        pool = Qt.QThreadPool.globalInstance()

        nbFound = 0

        def flushQueue():
            nonlocal nbFound
            try:
                lz77mem = memoryMapQueue.get(block=False)
                if nbFound == 0:
                    # At the first found we remove the parent memory
                    self._memoryMapList.removeObject(mem)
                nbFound += 1
                index = self._memoryMapList.indexAfterOffset(lz77mem.byte_offset)
                self._memoryMapList.insertObject(index, lz77mem)
            except queue.Empty:
                pass

        runnable = search_lz77.SearchLZ77Runnable(
            rom=self._rom,
            memoryRange=(mem.byte_offset, mem.byte_end),
            queue=memoryMapQueue,
        )

        dialog = search_lz77.WaitForSearchDialog(self)
        dialog.registerRunnable(runnable)
        pool.start(runnable)

        timer = Qt.QTimer(self)
        timer.timeout.connect(flushQueue)
        timer.start(1000)

        dialog.exec()

        timer.stop()
        flushQueue()
        Qt.QGuiApplication.restoreOverrideCursor()

        Qt.QMessageBox.information(
            self,
            "Seatch result",
            f"{nbFound} potential LZ77 location was found"
        )

    def _showMemoryMapContextMenu(self, pos: Qt.QPoint):
        globalPos = self._memView.mapToGlobal(pos)
        menu = Qt.QMenu(self)

        mems = self._memView.selectedMemoryMaps()

        if len(mems) == 1:
            mem = mems[0]

            showRawAsHexa = Qt.QAction(menu)
            showRawAsHexa.setText("Show raw as hexa")
            showRawAsHexa.triggered.connect(self._showMemoryMapRawAsHexa)
            menu.addAction(showRawAsHexa)

            saveRaw = Qt.QAction(menu)
            saveRaw.setText("Save raw...")
            saveRaw.triggered.connect(self._saveMemoryMapAsRaw)
            saveRaw.setIcon(Qt.QIcon("icons:save.png"))
            menu.addAction(saveRaw)

            showDataAsWave = Qt.QAction(menu)
            showDataAsWave.setText("Browse data for sample")
            showDataAsWave.triggered.connect(self._browseMemoryMapDataForSample)
            showDataAsWave.setIcon(Qt.QIcon("icons:sample.png"))
            menu.addAction(showDataAsWave)

            showDataAsWave = Qt.QAction(menu)
            showDataAsWave.setText("Browse data for music")
            showDataAsWave.triggered.connect(self._browseMemoryMapDataForMusic)
            showDataAsWave.setIcon(Qt.QIcon("icons:music.png"))
            menu.addAction(showDataAsWave)

            if mem.data_type == DataType.UNKNOWN:
                menu.addSeparator()

                searchLZ77 = Qt.QAction(menu)
                searchLZ77.triggered.connect(self._searchLZ77)
                searchLZ77.setText("Search for LZ77 data...")
                searchLZ77.setIcon(Qt.QIcon("icons:search.png"))
                menu.addAction(searchLZ77)

            if mem.byte_codec not in (None, ByteCodec.RAW):
                menu.addSeparator()

                showDataAsHexa = Qt.QAction(menu)
                showDataAsHexa.setText("Show data as hexa")
                showDataAsHexa.triggered.connect(self._showMemoryMapDataAsHexa)
                menu.addAction(showDataAsHexa)

                saveDat = Qt.QAction(menu)
                saveDat.setText("Save decompressed...")
                saveDat.triggered.connect(self._saveMemoryMapAsDat)
                saveDat.setIcon(Qt.QIcon("icons:save.png"))
                menu.addAction(saveDat)

            menu.addSeparator()

        remove = Qt.QAction(menu)
        remove.setText("Remove memory map")
        remove.triggered.connect(self._removeMemoryMap)
        remove.setIcon(Qt.QIcon("icons:remove.png"))
        menu.addAction(remove)

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
        address = mem.byte_offset
        self._hexa.setData(data, address=address)
        self._view.setCurrentWidget(self._hexa)

    def _browseMemoryMapDataForSample(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        data = self._rom.extract_data(mem)
        memory = io.BytesIO(data.tobytes())
        if mem.byte_codec in (None, ByteCodec.RAW):
            address = mem.byte_offset
        else:
            # Absolute ROM location have no meaning here
            address = 0
        self._sampleBrowser.setMemory(memory, address=address)
        self._view.setCurrentWidget(self._sampleBrowser)

    def _browseMemoryMapDataForMusic(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        data = self._rom.extract_data(mem)
        memory = io.BytesIO(data.tobytes())
        if mem.byte_codec in (None, ByteCodec.RAW):
            address = mem.byte_offset
        else:
            # Absolute ROM location have no meaning here
            address = 0
        self._musicBrowser.setMemory(memory, address=address)
        self._view.setCurrentWidget(self._musicBrowser)

    def _showMemoryMapDataAsHexa(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        data = self._rom.extract_data(mem)
        if mem.byte_codec in (None, ByteCodec.RAW):
            address = mem.byte_offset
        else:
            # Absolute ROM location have no meaning here
            address = 0
        self._hexa.setData(data, address=address)
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

        if mem.byte_codec not in (None, ByteCodec.RAW):
            # Actually we can't split such memory
            return

        offset = self._hexa.selectedOffset()
        if offset is None:
            return

        split = Qt.QAction(menu)
        split.setText("Split memory map before this address")
        split.triggered.connect(self._splitMemoryMap)
        menu.addAction(split)

        split = Qt.QAction(menu)
        split.setText("Split memory map as sappy sample")
        split.setIcon(Qt.QIcon("icons:sample.png"))
        split.triggered.connect(self.__splitSappySample.run)
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

    def _showPixelBrowserContextMenu(self, pos: Qt.QPoint):
        globalPos = self._pixelBrowser.mapToGlobal(pos)
        menu = Qt.QMenu(self)

        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return

        if mem.byte_codec not in (None, ByteCodec.RAW):
            # Actually we can't split such memory
            return

        split = Qt.QAction(menu)
        split.setText("Extract memory map")
        split.triggered.connect(self._extractMemoryMapFromPixelBrowser)
        menu.addAction(split)

        menu.exec(globalPos)

    def _extractMemoryMapFromPixelBrowser(self):
        """Split the memory map at the selection"""
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return

        selection = self._pixelBrowser.selection()
        if selection is None:
            return

        if selection[0] != mem.byte_offset:
            prevMem = MemoryMap(
                byte_offset=mem.byte_offset,
                byte_length=selection[0] - mem.byte_offset,
                byte_codec=mem.byte_codec,
                data_type=DataType.UNKNOWN,
            )
        else:
            prevMem = None

        selectedMem = MemoryMap(
            byte_offset=selection[0],
            byte_length=selection[1] - selection[0],
            byte_codec=mem.byte_codec,
            data_type=DataType.IMAGE,
            image_color_mode=self._pixelBrowser.colorMode(),
            image_pixel_order=self._pixelBrowser.pixelOrder(),
        )

        if selection[1] != mem.byte_offset + mem.byte_length:
            nextMem = MemoryMap(
                byte_offset=selection[1],
                byte_length=mem.byte_offset + mem.byte_length - selection[1],
                byte_codec=mem.byte_codec,
                data_type=DataType.UNKNOWN,
            )
        else:
            nextMem = None

        index = self._memoryMapList.objectIndex(mem).row()
        self._memoryMapList.removeObject(mem)
        if prevMem is not None:
            self._memoryMapList.insertObject(index, prevMem)
            index += 1
        if selectedMem is not None:
            self._memoryMapList.insertObject(index, selectedMem)
            index += 1
        if nextMem is not None:
            self._memoryMapList.insertObject(index, nextMem)

    def save(self):
        """Save to the loadined file"""
        self._saveFilename(self._filename)

    def saveAs(self):
        """Save as a new file from a file dialog."""
        self._saveFilename(None)

    def _saveFilename(self, filename: str | None):
        if self._rom is None:
            raise ValueError()

        if filename is None:
            filename = file_dialog.getSaveTomlFilenameFromDialog(self)
            if filename is None:
                return

        assert filename is not None

        try:
            rom = {}
            rom["game_title"] = self._rom.game_title
            rom["sha256"] = self._rom.sha256
            localDir = os.path.dirname(filename)
            relativePath = os.path.relpath(self._rom.filename, start=localDir)
            rom["local_filename"] = relativePath

            data = {}
            data["rom"] = rom
            for mem in self._rom.offsets:
                data[f"memory_map:{mem.byte_offset:08X}"] = mem.to_dict()
            with open(filename, "wt") as f:
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
        self._colorModeList.setVisible(dataType in (DataType.IMAGE,DataType.TILE_SET))
        self._paletteCombo.setVisible(dataType in (DataType.IMAGE,DataType.TILE_SET))
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
            reducedByteLength = uniqueValueElseNone([(m.byte_payload or m.byte_length) for m in mems])
            reducedColorMap = uniqueValueElseNone([m.image_color_mode for m in mems])

            if reducedDataType != DataType.IMAGE or reducedByteLength is None or reducedColorMap is None:
                self._shapeList.setEnabled(False)
                with blockSignals(self._shapeList):
                    self._shapeList.clear()
            else:
                reducedShape = uniqueValueElseNone([m.image_shape for m in mems])
                self._shapeList.setEnabled(True)
                with blockSignals(self._shapeList):
                    self._shapeList.clear()
                    oneShape = self._rom.image_shape(mems[0])
                    shapes = guessed_shapes(oneShape[0] * oneShape[1])
                    for shape in shapes:
                        self._shapeList.addShape(shape)
                    if reducedShape is not None:
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
            data_type_name = "" if mem.data_type is None else mem.data_type.name
            if mem.data_type == DataType.GBA_ROM_HEADER:
                data = self._rom.extract_raw(mem)
                self._header.setMemory(data)
                self._view.setCurrentWidget(self._header)
            elif mem.data_type == DataType.PADDING:
                data = self._rom.extract_raw(mem)
                self._hexa.setData(data, address=mem.byte_offset)
                self._view.setCurrentWidget(self._hexa)
            elif data_type_name.startswith("SAMPLE_"):
                self._sampleView.setMemoryMap(mem)
                self._view.setCurrentWidget(self._sampleView)
            elif data_type_name.startswith("MUSIC_"):
                self._musicView.setMemoryMap(mem)
                self._view.setCurrentWidget(self._musicView)
            elif mem.data_type == DataType.UNKNOWN:
                data = self._rom.extract_data(mem)
                memory = io.BytesIO(data.tobytes())
                if mem.byte_codec in (None, ByteCodec.RAW):
                    address = mem.byte_offset
                else:
                    # Absolute ROM location have no meaning here
                    address = 0
                self._pixelBrowser.setMemory(memory, address=address)
                self._view.setCurrentWidget(self._pixelBrowser)
            elif mem.data_type == DataType.TILE_SET:
                data = self._rom.tile_set_data(mem)
                self._tilesetBrowser.setData(data)
                self._view.setCurrentWidget(self._tilesetBrowser)
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

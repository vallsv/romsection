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

from .context import Context
from .utils import prime_factors, guessed_shapes
from .widgets.data_browser import DataBrowser
from .widgets.memory_map_list_view import MemoryMapListView
from .widgets.image_color_mode_list import ImageColorModeList
from .widgets.shape_list import ShapeList
from .widgets.image_pixel_order_list import ImagePixelOrderList
from .widgets.byte_codec_list import ByteCodecList
from .widgets.data_type_list import DataTypeList
from .widgets.palette_filter_proxy_model import PaletteFilterProxyModel
from .widgets.combo_box import ComboBox
from .widgets.palette_combo_box import PaletteComboBox
from .widgets.sprite_view import SpriteView
from .widgets.hexa_view import HexaView
from .widgets.palette_size_list import PaletteSizeList
from .widgets.tile_set_view import TileSetView
from .widgets.music_browser import MusicBrowser
from .widgets.sample_view import SampleView
from .widgets.data_view import DataView
from .widgets.sample_codec_list import SampleCodecList
from .widgets.memory_map_filter_drop import MemoryMapFilterDrop
from .widgets.memory_map_proxy_model import MemoryMapFilter
from .gba_file import GBAFile, ByteCodec, MemoryMap, ImageColorMode, ImagePixelOrder, DataType
from .qt_utils import blockSignals, exceptionAsMessageBox
from .path_utils import resolve_abspath
from .behaviors import file_dialog
from .behaviors import lz77_content
from .behaviors import huffman_content
from .behaviors import sappy_content
from .behaviors import unknown_content
from .behaviors.info import InfoDialog
from .parsers import gba_utils
from .commands.remove_memorymap import RemoveMemoryMapCommand
from .commands.insert_memorymap import InsertMemoryMapCommand


def uniqueValueElseNone(data: list[typing.Any]):
    reduced = set(data)
    if len(reduced) == 1:
        return data[0]
    return None


class Extractor(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent)

        context = Context(self)
        context._mainWidget = self
        self._context = context

        self._lastBySize: dict[int, MemoryMap] = {}
        self._paletteList =  PaletteFilterProxyModel(self)
        self._paletteList.setSourceModel(context.memoryMapList())

        self._dialogDirectory = os.getcwd()
        self._filename: str | None = None
        self._displayedMemoryMap: MemoryMap | None = None

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

        toolbar.addSeparator()

        undoStack = context.undoStack()
        undoAction = undoStack.createUndoAction(self)
        undoAction.setIcon(Qt.QIcon("icons:undo.png"))
        toolbar.addAction(undoAction)

        redoAction = undoStack.createRedoAction(self)
        redoAction.setIcon(Qt.QIcon("icons:redo.png"))
        toolbar.addAction(redoAction)

        toolbar.addSeparator()

        infoAction = Qt.QAction(self)
        infoAction.triggered.connect(self._showInfo)
        infoAction.setText("Display info")
        infoAction.setIcon(Qt.QIcon("icons:info.png"))
        toolbar.addAction(infoAction)

        toolbar.addSeparator()

        self._memoryMapFilter = MemoryMapFilterDrop(self)
        toolbar.addWidget(self._memoryMapFilter)

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
        self.__searchSappyContent.setContext(context)
        self.__searchSappySong = sappy_content.SearchSappySongHeaderFromInstrument()
        self.__searchSappySong.setContext(context)

        self.__searchForLZ77 = lz77_content.SearchLZ77Content()
        self.__searchForLZ77.setContext(context)
        self.__searchForHuffman = huffman_content.SearchHuffmanContent()
        self.__searchForHuffman.setContext(context)

        self.__createUncovered = unknown_content.CreateUncoveredMemory()
        self.__createUncovered.setContext(context)

        self.__replaceUnknownByPadding = unknown_content.ReplaceUnknownByPadding()
        self.__replaceUnknownByPadding.setContext(context)

        self.__removeUnknown = unknown_content.RemoveUnknown()
        self.__removeUnknown.setContext(context)

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
        action.triggered.connect(self.__searchSappySong.run)
        action.setText("Search for sappy song header (from instrument table)")
        action.setIcon(Qt.QIcon("icons:music.png"))
        toolMenu.addAction(action)

        toolMenu.addSeparator()

        action = Qt.QAction(self)
        action.triggered.connect(self.__replaceUnknownByPadding.run)
        action.setText("Replace matching unknown by padding")
        action.setIcon(Qt.QIcon("icons:padding.png"))
        toolMenu.addAction(action)

        self._memView = MemoryMapListView(self)
        self._memView.setModel(context.memoryMapList())
        self._memView.selectionModel().selectionChanged.connect(self._onMemoryMapSelectionChanged)
        self._memView.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self._memView.customContextMenuRequested.connect(self._showMemoryMapContextMenu)

        self._byteCodecList = ByteCodecList(self)
        self._byteCodecList.valueChanged.connect(self._onByteCodecSelected)

        self._dataTypeList = DataTypeList(self)
        self._dataTypeList.valueChanged.connect(self._onDataTypeSelected)
        self._dataTypeList.setMinimumWidth(180)
        self._dataTypeList.setMaximumWidth(180)

        self._paletteSizeList = PaletteSizeList(self)
        self._paletteSizeList.valueChanged.connect(self._onPaletteSizeSelected)

        self._paletteCombo = PaletteComboBox(self)
        self._paletteCombo.setModel(self._paletteList)
        self._paletteCombo.setMaxVisibleItems(15)
        self._paletteCombo.setSizeAdjustPolicy(
            Qt.QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self._paletteCombo.valueChanged.connect(self._onPaletteSelected)

        self._colorModeList = ImageColorModeList(self)
        self._colorModeList.valueChanged.connect(self._onImageColorModeSelected)

        self._pixelOrderList = ImagePixelOrderList(self)
        self._pixelOrderList.valueChanged.connect(self._onImagePixelOrderSelected)

        self._shapeList = ShapeList(self)
        self._shapeList.itemSelectionChanged.connect(self._onShapeSelected)
        self._shapeList.setMinimumWidth(180)
        self._shapeList.setMaximumWidth(180)

        self._sampleCodecList = SampleCodecList(self)
        self._sampleCodecList.valueChanged.connect(self._onSampleCodecSelected)
        self._sampleCodecList.setMinimumWidth(180)
        self._sampleCodecList.setMaximumWidth(180)

        self._nothing = Qt.QWidget(self)

        self._error = Qt.QTextEdit(self)
        self._error.setReadOnly(True)
        self._error.setStyleSheet(".QTextEdit { color: red; }")

        self._image = SpriteView(self)

        self._tileSetView = TileSetView(self)

        self._dataBrowser = DataBrowser(self)
        self._dataBrowser.setContext(context)

        self._musicBrowser = MusicBrowser(self)
        self._sampleView = SampleView(self)
        self._dataView = DataView(self)
        self._dataView.setContext(context)
        self._hexaView = HexaView(self)

        self._view = Qt.QStackedLayout()
        self._view.addWidget(self._nothing)
        self._view.addWidget(self._image)
        self._view.addWidget(self._tileSetView)
        self._view.addWidget(self._error)
        self._view.addWidget(self._hexaView)
        self._view.addWidget(self._dataBrowser)
        self._view.addWidget(self._musicBrowser)
        self._view.addWidget(self._sampleView)
        self._view.addWidget(self._dataView)

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
        spriteCodec.addWidget(self._sampleCodecList)
        spriteCodec.setStretchFactor(self._shapeList, 1)
        spriteCodec.addStretch(0)

        main = Qt.QHBoxLayout(self)
        main.addLayout(leftLayout)
        main.addLayout(spriteCodec)
        main.addLayout(self._view)
        main.setStretchFactor(self._view, 1)

        self._memoryMapFilter.filterChanged.connect(self.__setMemoryMapFilter)
        context.romChanged.connect(self._onRomChanged)
        undoAction.triggered.connect(self._onMemoryMapSelectionChanged)
        redoAction.triggered.connect(self._onMemoryMapSelectionChanged)
        self._onRomChanged(None)

    def _showInfo(self):
        dialog = InfoDialog(self)
        dialog.setContext(self._context)
        dialog.exec()

    def __setMemoryMapFilter(self, filter: MemoryMapFilter | None):
        mem = self._memView.selectedMemoryMap()
        self._memView.filterModel().setFilter(filter)
        if mem is not None:
            self._memView.scrollTo(mem)

    def loadFromDialog(self):
        filename = file_dialog.getTomlOrRomFilenameFromDialog(self)
        if filename is None:
            return
        self.loadFilename(filename)

    def loadFilename(self, filename: str):
        with exceptionAsMessageBox(self):
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
            self._filename = None
            header = MemoryMap(
                byte_offset=0,
                byte_codec=ByteCodec.RAW,
                byte_length=gba_utils.EXTANDED_GBA_HEADER_SIZE,
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
            self._context.setRom(rom)

    def _loadTomlFile(self, filename: str):
        localDirectory = os.path.dirname(filename)
        with exceptionAsMessageBox(self):
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
                self._context.setRom(rom)

    def context(self) -> Context:
        return self._context

    def _onRomChanged(self, rom: GBAFile | None):
        self._paletteList.setRom(rom)
        self._sampleView.setRom(rom)
        self._dataView.setRom(rom)
        self._dataBrowser.setRom(rom)
        if rom is None:
            self.setWindowTitle("No ROM loaded")
        else:
            filename = os.path.basename(rom.filename)
            self.setWindowTitle(filename)
        self._updateNoMemoryMapSelected()

    def _showMemoryMapContextMenu(self, pos: Qt.QPoint):
        globalPos = self._memView.mapToGlobal(pos)
        menu = Qt.QMenu(self)

        mems = self._memView.selectedMemoryMaps()

        if len(mems) == 1:
            mem = mems[0]

            browseData = Qt.QAction(menu)
            browseData.setText("Browse data memory")
            browseData.triggered.connect(self._browseMemoryMapData)
            menu.addAction(browseData)

            if mem.byte_codec not in (None, ByteCodec.RAW):
                browseRaw = Qt.QAction(menu)
                browseRaw.setText("Browse compressed memory")
                browseRaw.triggered.connect(self._browseMemoryMapRaw)
                menu.addAction(browseRaw)

            showDataAsMusic = Qt.QAction(menu)
            showDataAsMusic.setText("Browse data for music")
            showDataAsMusic.triggered.connect(self._browseMemoryMapDataForMusic)
            showDataAsMusic.setIcon(Qt.QIcon("icons:music.png"))
            menu.addAction(showDataAsMusic)

            if mem.data_type == DataType.UNKNOWN:
                menu.addSeparator()

                searchLZ77 = Qt.QAction(menu)
                searchLZ77.triggered.connect(self.__searchForLZ77.run)
                searchLZ77.setText("Search for LZ77 data...")
                searchLZ77.setIcon(Qt.QIcon("icons:search.png"))
                menu.addAction(searchLZ77)

                searchHuffman = Qt.QAction(menu)
                searchHuffman.triggered.connect(self.__searchForHuffman.run)
                searchHuffman.setText("Search for huffman data...")
                searchHuffman.setIcon(Qt.QIcon("icons:search.png"))
                menu.addAction(searchHuffman)

            menu.addSeparator()

            saveRaw = Qt.QAction(menu)
            saveRaw.setText("Save data...")
            saveRaw.triggered.connect(self._saveMemoryMapData)
            saveRaw.setIcon(Qt.QIcon("icons:save.png"))
            menu.addAction(saveRaw)

            if mem.byte_codec not in (None, ByteCodec.RAW):
                saveDat = Qt.QAction(menu)
                saveDat.setText("Save compressed...")
                saveDat.triggered.connect(self._saveMemoryMapRaw)
                saveDat.setIcon(Qt.QIcon("icons:save.png"))
                menu.addAction(saveDat)

            menu.addSeparator()

        if len(mems) > 1:
            merge = Qt.QAction(menu)
            merge.setText("Merge contiguous memory map")
            merge.triggered.connect(self._mergeMemoryMap)
            menu.addAction(merge)

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

        context = self._context
        with context.macroCommands("Remove selected memorymap"):
            for mem in reversed(mems):
                command = RemoveMemoryMapCommand()
                command.setCommand(mem)
                context.pushCommand(command)

    def _mergeMemoryMap(self):
        """Replace contiguous memory mpa by a new UNKNOWN one"""
        mems = self._memView.selectedMemoryMaps()
        if len(mems) == 0:
            return
        context = self._context

        if len(mems) == 1:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "At least 2 contiguous memory map have to be selected"
            )
            return

        # Reorder by offset
        mems = sorted(mems, key=lambda m: m.byte_offset)

        def contiguousRange(mems: list[MemoryMap]) -> tuple[int, int] | None:
            # At this stage memory maps have to be ordered
            start = mems[0]
            startOffset = start.byte_offset
            endOffset = start.byte_end
            for m in mems[1:]:
                if m.byte_offset > endOffset:
                    return None
                endOffset = max(endOffset, m.byte_end)
            return startOffset, endOffset

        offsetRange = contiguousRange(mems)
        if offsetRange is None:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected memory maps are not contiguous"
            )
            return

        with context.macroCommands("Merge selected memorymap"):
            index = context.memoryMapList().objectIndex(mems[0]).row()
            print(index)
            for mem in reversed(mems):
                command = RemoveMemoryMapCommand()
                command.setCommand(mem)
                context.pushCommand(command)

            newMem = MemoryMap(
                byte_codec=ByteCodec.RAW,
                byte_offset=offsetRange[0],
                byte_length=offsetRange[1] - offsetRange[0],
                data_type=DataType.UNKNOWN,
            )
            command = InsertMemoryMapCommand()
            command.setCommand(index, newMem)
            context.pushCommand(command)

    def _showMemoryMapRawAsHexa(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        rom = self._context.rom()
        data = rom.extract_raw(mem)
        address = mem.byte_offset
        self._hexaView.setData(data, address=address)
        self._view.setCurrentWidget(self._hexaView)

    def _browseMemoryMapRaw(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        self._dataBrowser.showMemoryMapRaw(mem)
        self._view.setCurrentWidget(self._dataBrowser)

    def _browseMemoryMapData(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        self._dataBrowser.showMemoryMapData(mem)
        self._view.setCurrentWidget(self._dataBrowser)

    def _browseMemoryMapDataForMusic(self):
        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        rom = self._context.rom()
        data = rom.extract_data(mem)
        memory = io.BytesIO(data)
        if mem.byte_codec in (None, ByteCodec.RAW):
            address = mem.byte_offset
        else:
            # Absolute ROM location have no meaning here
            address = 0
        self._musicBrowser.setMemory(memory, address=address)
        self._view.setCurrentWidget(self._musicBrowser)

    def _saveMemoryMapRaw(self):
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

        rom = self._context.rom()
        data = rom.extract_raw(mem)

        filename = dialog.selectedFiles()[0]
        with open(filename, "wb") as f:
            f.write(data)

    def _saveMemoryMapData(self):
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

        rom = self._context.rom()
        data = rom.extract_data(mem)

        filename = dialog.selectedFiles()[0]
        with open(filename, "wb") as f:
            f.write(data)

    def save(self):
        """Save to the loadined file"""
        self._saveFilename(self._filename)

    def saveAs(self):
        """Save as a new file from a file dialog."""
        self._saveFilename(None)

    def _saveFilename(self, filename: str | None):
        rom = self._context.romOrNone()
        if rom is None:
            raise ValueError()

        if filename is None:
            filename = file_dialog.getSaveTomlFilenameFromDialog(self)
            if filename is None:
                return

        assert filename is not None

        try:
            romData: dict[str, typing.Any] = {}
            romData["game_title"] = rom.game_title
            romData["sha256"] = rom.sha256
            localDir = os.path.dirname(filename)
            relativePath = os.path.relpath(rom.filename, start=localDir)
            romData["local_filename"] = relativePath

            data: dict[str, typing.Any] = {}
            data["rom"] = romData
            for mem in rom.offsets:
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
        current = self._memView.currentMemoryMap()
        self._context._setCurrentMemoryMap(current)
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
        self._sampleCodecList.setEnabled(False)
        with blockSignals(self._byteCodecList):
            self._byteCodecList.selectValue(None)
        with blockSignals(self._dataTypeList):
            self._dataTypeList.selectValue(None)
        with blockSignals(self._colorModeList):
            self._colorModeList.selectValue(None)
        with blockSignals(self._paletteCombo):
            self._paletteCombo.selectValue(None)
        with blockSignals(self._shapeList):
            self._shapeList.clear()
        with blockSignals(self._pixelOrderList):
            self._pixelOrderList.selectValue(None)
        with blockSignals(self._paletteSizeList):
            self._paletteSizeList.selectValue(None)
        with blockSignals(self._sampleCodecList):
            self._sampleCodecList.selectValue(None)
        self._view.setCurrentWidget(self._nothing)

    def _updateMultipleMemoryMapSelected(self, mems: list[MemoryMap]):
        """
        Allow to display and edit as much as possible.
        """
        self._byteCodecList.setEnabled(True)
        self._dataTypeList.setEnabled(True)
        self._colorModeList.setEnabled(True)
        self._paletteCombo.setEnabled(True)
        self._pixelOrderList.setEnabled(True)
        self._paletteSizeList.setEnabled(True)
        self._sampleCodecList.setEnabled(True)

        with blockSignals(self._byteCodecList):
            reducedByteCodec = uniqueValueElseNone([m.byte_codec for m in mems])
            self._byteCodecList.selectValue(reducedByteCodec)
        with blockSignals(self._dataTypeList):
            reducedDataType = uniqueValueElseNone([m.data_type for m in mems])
            self._dataTypeList.selectValue(reducedDataType)
        with blockSignals(self._colorModeList):
            reducedColorMode = uniqueValueElseNone([m.image_color_mode for m in mems])
            self._colorModeList.selectValue(reducedColorMode)
        with blockSignals(self._paletteCombo):
            reducedOffset = uniqueValueElseNone([m.image_palette_offset for m in mems])
            palette_mem = None
            if reducedOffset is not None:
                rom = self._context.rom()
                try:
                    palette_mem = rom.memory_map_from_offset(reducedOffset)
                except ValueError:
                    logging.warning("Palette 0x{mem.image_palette_offset:08X} does not exist")
                    palette_mem = None
            self._paletteCombo.selectValue(palette_mem)
        with blockSignals(self._pixelOrderList):
            reducedPixelOrder = uniqueValueElseNone([m.image_pixel_order for m in mems])
            self._pixelOrderList.selectValue(reducedPixelOrder)
        with blockSignals(self._paletteSizeList):
            reducedPaletteSize = uniqueValueElseNone([m.palette_size for m in mems])
            self._paletteSizeList.selectValue(reducedPaletteSize)
        with blockSignals(self._sampleCodecList):
            sampleCodec = uniqueValueElseNone([m.sample_codec for m in mems])
            self._sampleCodecList.selectValue(sampleCodec)

        self._updateWidgets()
        self._updateShapes()
        self._updateImage()

    def _updateMemoryMapSelected(self, mem: MemoryMap):
        self._byteCodecList.setEnabled(True)
        self._dataTypeList.setEnabled(True)
        self._colorModeList.setEnabled(True)
        self._paletteCombo.setEnabled(True)
        self._shapeList.setEnabled(True)
        self._pixelOrderList.setEnabled(True)
        self._paletteSizeList.setEnabled(True)
        self._sampleCodecList.setEnabled(True)

        if mem.byte_payload is not None:
            if mem.image_color_mode is None and mem.image_shape is None and mem.image_pixel_order is None:
                previous = self._lastBySize.get(mem.byte_payload)
                if previous is not None:
                    newMem = mem.replace(
                        image_color_mode=previous.image_color_mode,
                        image_shape=previous.image_shape,
                        image_pixel_order=previous.image_pixel_order,
                    )
                    self._context.updateMemoryMap(mem, newMem)
                    self._lastBySize[mem.byte_payload] = newMem
            else:
                self._lastBySize[mem.byte_payload] = mem

        with blockSignals(self._byteCodecList):
            self._byteCodecList.selectValue(mem.byte_codec)

        with blockSignals(self._dataTypeList):
            self._dataTypeList.selectValue(mem.data_type)

        with blockSignals(self._colorModeList):
            self._colorModeList.selectValue(mem.image_color_mode)

        with blockSignals(self._paletteCombo):
            image_palette_offset = mem.image_palette_offset
            if mem.image_palette_offset is None:
                palette_mem = None
            else:
                rom = self._context.rom()
                try:
                    palette_mem = rom.memory_map_from_offset(mem.image_palette_offset)
                except ValueError:
                    logging.warning("Palette 0x{mem.image_palette_offset:08X} does not exist")
                    palette_mem = None
            self._paletteCombo.selectValue(palette_mem)

        with blockSignals(self._pixelOrderList):
            self._pixelOrderList.selectValue(mem.image_pixel_order)

        with blockSignals(self._paletteSizeList):
            self._paletteSizeList.selectValue(mem.palette_size)

        with blockSignals(self._sampleCodecList):
            self._sampleCodecList.selectValue(mem.sample_codec)

        self._updateWidgets()
        self._updateShapes()
        self._updateImage()

    def _onByteCodecSelected(self):
        byteCodec = self._byteCodecList.selectedValue()
        if byteCodec is None:
            return

        context = self._context
        for mem in self._memView.selectedMemoryMaps():
            newMem = mem.replace(
                byte_codec=byteCodec,
                byte_payload=None,
            )
            context.updateMemoryMap(mem, newMem)

        self._updateShapes()
        self._updateImage()

    def _onDataTypeSelected(self):
        dataType = self._dataTypeList.selectedValue()
        if dataType is None:
            return

        context = self._context
        for mem in self._memView.selectedMemoryMaps():
            newMem = mem.replace(data_type=dataType)
            context.updateMemoryMap(mem, newMem)

        self._updateWidgets()
        self._updateShapes()
        self._updateImage()

    def _onPaletteSizeSelected(self):
        paletteSize = self._paletteSizeList.selectedValue()
        if paletteSize is None:
            return

        context = self._context
        for mem in self._memView.selectedMemoryMaps():
            newMem = mem.replace(
                palette_size=paletteSize,
            )
            context.updateMemoryMap(mem, newMem)

        self._updateWidgets()
        self._updateShapes()
        self._updateImage()

    def _updateWidgets(self):
        dataType = self._dataTypeList.selectedValue()
        self._paletteSizeList.setVisible(dataType == DataType.PALETTE)
        self._colorModeList.setVisible(dataType in (DataType.IMAGE,DataType.TILE_SET))
        self._paletteCombo.setVisible(dataType in (DataType.IMAGE,DataType.TILE_SET))
        self._shapeList.setVisible(dataType == DataType.IMAGE)
        self._pixelOrderList.setVisible(dataType == DataType.IMAGE)
        self._sampleCodecList.setVisible(dataType == DataType.SAMPLE_SAPPY)

    def _updateShapes(self):
        mems = self._memView.selectedMemoryMaps()
        rom = self._context.rom()
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
                image_shape = rom.image_shape(mem)
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
                    oneShape = rom.image_shape(mems[0])
                    shapes = guessed_shapes(oneShape[0] * oneShape[1])
                    for shape in shapes:
                        self._shapeList.addShape(shape)
                    if reducedShape is not None:
                        self._shapeList.selectShape(reducedShape)

    def _onImageColorModeSelected(self):
        colorMode = self._colorModeList.selectedValue()

        context = self._context
        for mem in self._memView.selectedMemoryMaps():
            if mem.image_color_mode == colorMode:
                continue

            previousImageColorMode = mem.image_color_mode
            newMem = mem.replace(image_color_mode=colorMode)

            if mem.image_shape is not None:
                pnb = 1 if previousImageColorMode in [None, ImageColorMode.INDEXED_8BIT] else 2
                nb = 1 if colorMode in [None, ImageColorMode.INDEXED_8BIT] else 2
                if pnb != nb:
                    shape = mem.image_shape[0], int(mem.image_shape[1] * nb / pnb)
                    newMem = newMem.replace(image_shape=shape)
            context.updateMemoryMap(mem, newMem)

        mem = self._memView.selectedMemoryMap()
        if mem is None:
            return
        self._updateShapes()
        self._updateImage()

    def _onShapeSelected(self):
        shape = self._shapeList.selectedShape()

        context = self._context
        for mem in self._memView.selectedMemoryMaps():
            newMem = mem.replace(
                image_shape=shape,
            )
            context.updateMemoryMap(mem, newMem)

        self._updateImage()

    def _onImagePixelOrderSelected(self):
        pixelOrder = self._pixelOrderList.selectedValue()

        context = self._context
        for mem in self._memView.selectedMemoryMaps():
            newMem = mem.replace(
                image_pixel_order=pixelOrder,
            )
            context.updateMemoryMap(mem, newMem)

        self._updateImage()

    def _onPaletteSelected(self):
        paletteMem = self._paletteCombo.selectedValue()
        if paletteMem is not None:
            paletteOffset = paletteMem.byte_offset
        else:
            paletteOffset = None

        context = self._context
        for mem in self._memView.selectedMemoryMaps():
            newMem = mem.replace(
                image_palette_offset=paletteOffset,
            )
            context.updateMemoryMap(mem, newMem)

        self._updateImage()

    def _onSampleCodecSelected(self):
        sampleCodec = self._sampleCodecList.selectedValue()

        context = self._context
        for mem in self._memView.selectedMemoryMaps():
            newMem = mem.replace(
                sample_codec=sampleCodec,
            )
            context.updateMemoryMap(mem, newMem)

        self._updateImage()

    def _updatePayload(self, mem: MemoryMap) -> MemoryMap:
        """
        Synchronize memory map with cached information.

        FIXME: Maybe the cached information should be handled in a side way
               outside of the MemoryMap itself
        """
        if mem.byte_codec is None or mem.byte_codec == ByteCodec.RAW:
            return mem
        if mem.byte_payload is not None:
            return mem
        rom = self._context.rom()
        try:
            size, payload = rom.check_codec(mem.byte_offset, mem.byte_codec)
        except Exception:
            # FIXME: This have to be cached
            return mem

        newMem = mem.replace(
            byte_payload=payload,
            byte_length=size,
        )
        self._context.updateMemoryMap(mem, newMem)
        return newMem

    def _updateImage(self):
        mem = self._memView.currentMemoryMap()
        if mem is None:
            self._view.setCurrentWidget(self._nothing)
            self._displayedMemoryMap = None
            return

        mem = self._updatePayload(mem)
        if self._displayedMemoryMap is mem:
            return
        self._displayedMemoryMap = mem

        rom = self._context.rom()
        try:
            data_type_name = "" if mem.data_type is None else mem.data_type.name
            if mem.data_type == DataType.GBA_ROM_HEADER:
                self._dataView.setMemoryMap(mem)
                self._view.setCurrentWidget(self._dataView)
            elif mem.data_type == DataType.PADDING:
                self._showMemoryMapRawAsHexa()
            elif data_type_name.startswith("SAMPLE_"):
                self._sampleView.setMemoryMap(mem)
                self._view.setCurrentWidget(self._sampleView)
            elif data_type_name.startswith("MUSIC_"):
                self._dataView.setMemoryMap(mem)
                self._view.setCurrentWidget(self._dataView)
            elif mem.data_type == DataType.UNKNOWN:
                self._browseMemoryMapData()
            elif mem.data_type == DataType.TILE_SET:
                data = rom.tile_set_data(mem)
                self._tileSetView.setData(data)
                self._view.setCurrentWidget(self._tileSetView)
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
        rom = self._context.rom()
        if mem.data_type == DataType.PALETTE:
            result = rom.palette_data(mem)
            # FIXME: Handle explicitly 16 and 256
            result.shape = -1, 16, result.shape[2]
            return result

        if mem.data_type == DataType.IMAGE:
            return rom.image_data(mem)

        raise ValueError(f"No image representation for memory map of type {mem.data_type}")

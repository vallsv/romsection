import os
import io
import numpy
from PyQt5 import Qt

from ..qt_utils import blockSignals
from ..gba_file import GBAFile
from ..behaviors import sappy_content
from ..format_utils import format_address as f_address
from ..model import MemoryMap, ByteCodec, DataType
from .sample_browser_widget import SampleBrowserWidget
from .pixel_browser_widget import PixelBrowserWidget
from .sample_codec_combo_box import SampleCodecComboBox
from .pixel_browser_widget import PixelBrowserWidget
from .image_pixel_order_combo import ImagePixelOrderCombo
from .image_color_mode_combo import ImageColorModeCombo
from .combo_box import ComboBox
from .hexa_view import HexaView


class PixelTools:
    """Holder for tools related to pixel browsing"""
    def __init__(self, toolBar: Qt.QToolBar):
        self.__view: PixelBrowserWidget | None = None
        self.__actions: list[Qt.QAction] = []

        self.__zoom = Qt.QSpinBox(toolBar)
        self.__zoom.setRange(1, 16)
        action = toolBar.addWidget(self.__zoom)
        self.__actions.append(action)

        self.__pixelWidth = Qt.QSpinBox(toolBar)
        self.__pixelWidth.setRange(1, 128 * 4)
        action = toolBar.addWidget(self.__pixelWidth)
        self.__actions.append(action)

        self.__colorMode = ImageColorModeCombo(toolBar)
        action = toolBar.addWidget(self.__colorMode)
        self.__actions.append(action)

        self.__pixelOrder = ImagePixelOrderCombo(toolBar)
        action = toolBar.addWidget(self.__pixelOrder)
        self.__actions.append(action)

    def setView(self, view: PixelBrowserWidget | None):
        if self.__view is view:
            return
        if self.__view is not None:
            self.__zoom.valueChanged.disconnect(self.__view.setZoom)
            self.__pixelWidth.valueChanged.disconnect(self.__view.setPixelWidth)
            self.__colorMode.valueChanged.disconnect(self.__view.setColorMode)
            self.__pixelOrder.valueChanged.disconnect(self.__view.setPixelOrder)
        self.__view = view
        if self.__view is not None:
            self.__zoom.valueChanged.connect(self.__view.setZoom)
            self.__pixelWidth.valueChanged.connect(self.__view.setPixelWidth)
            self.__colorMode.valueChanged.connect(self.__view.setColorMode)
            self.__pixelOrder.valueChanged.connect(self.__view.setPixelOrder)
            self.__zoom.setValue(self.__view.zoom())
        # Setup the state
        if self.__view is not None:
            self.__pixelWidth.setValue(self.__view.pixelWidth())
            self.__colorMode.selectValue(self.__view.colorMode())
            self.__pixelOrder.selectValue(self.__view.pixelOrder())
        self.__pixelWidth.setEnabled(self.__view is not None)
        self.__colorMode.setEnabled(self.__view is not None)
        self.__pixelOrder.setEnabled(self.__view is not None)

    def setVisible(self, visible: bool):
        for action in self.__actions:
            action.setVisible(visible)


class SampleTools:
    """Holder for tools related to sample browsing"""
    def __init__(self, toolBar: Qt.QToolBar):
        self.__view: SampleBrowserWidget | None = None
        self.__actions: list[Qt.QAction] = []

        self.__samplePerPixels = Qt.QSpinBox(toolBar)
        self.__samplePerPixels.setRange(1, 128)
        action = toolBar.addWidget(self.__samplePerPixels)
        self.__actions.append(action)

        self.__sampleCodec = SampleCodecComboBox(toolBar)
        action = toolBar.addWidget(self.__sampleCodec)
        self.__actions.append(action)

        self.__playButton = Qt.QPushButton(toolBar)
        self.__playButton.clicked.connect(self._playback)
        self.__playButton.setToolTip("Playback visible data only")
        self.__playButton.setIcon(Qt.QIcon("icons:play.png"))
        action = toolBar.addWidget(self.__playButton)
        self.__actions.append(action)

    def setView(self, view: SampleBrowserWidget | None):
        if self.__view is view:
            return
        if self.__view is not None:
            self.__samplePerPixels.valueChanged.disconnect(self.__view.setNbSamplePerPixels)
            self.__sampleCodec.valueChanged.disconnect(self.__view.setSampleCodec)
            self.__view.playbackChanged.disconnect(self._onPlaybackChanged)
        self.__view = view
        if self.__view is not None:
            self.__samplePerPixels.valueChanged.connect(self.__view.setNbSamplePerPixels)
            self.__sampleCodec.valueChanged.connect(self.__view.setSampleCodec)
            self.__view.playbackChanged.connect(self._onPlaybackChanged)
        # Setup the state
        if self.__view is not None:
            self.__samplePerPixels.setValue(self.__view.nbSamplePerPixels())
        self.__samplePerPixels.setEnabled(self.__view is not None)

    def setVisible(self, visible: bool):
        for action in self.__actions:
            action.setVisible(visible)

    def _playback(self):
        view = self.__view
        if view is None:
            return
        if view.isPlaying():
            view.stop()
        else:
            view.playVisible()

    def _onPlaybackChanged(self, playing: bool):
        if playing:
            self.__playButton.setIcon(Qt.QIcon("icons:stop.png"))
        else:
            self.__playButton.setIcon(Qt.QIcon("icons:play.png"))


class DataBrowser(Qt.QWidget):
    """
    Browse random memory to check it with diffent kind of representation.
    """
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)
        context = parent

        self.__address: int = 0
        self.__rom: GBAFile | None = None
        self.__mem: MemoryMap | None = None

        self.__toolbar = Qt.QToolBar(self)
        self.__statusbar = Qt.QStatusBar(self)

        self.__pixel = PixelBrowserWidget(self)
        self.__pixel.positionChanged.connect(self.__positionChanged)
        self.__pixel.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self.__pixel.customContextMenuRequested.connect(self._showPixelContextMenu)

        self.__wave = SampleBrowserWidget(self)
        self.__wave.setNbSamplePerPixels(8)
        self.__wave.positionChanged.connect(self.__positionChanged)

        self.__hexa = HexaView(self)
        self.__hexa.setVisible(False)
        self.__hexa.setContextMenuPolicy(Qt.Qt.CustomContextMenu)
        self.__hexa.customContextMenuRequested.connect(self._showHexaContextMenu)

        self.__splitSappySample = sappy_content.SplitSappySample()
        self.__splitSappySample.setContext(context)

        action = Qt.QAction(self)
        action.setIcon(Qt.QIcon("icons:hexa.png"))
        action.setCheckable(True)
        action.setText("Hex viewer")
        action.setToolTip("Show hexa viewer")
        action.toggled.connect(self.setHexaVisible)
        action.setChecked(not self.__hexa.isHidden())
        self.__showHexaAction = action
        self.__toolbar.addAction(self.__showHexaAction)

        self.__toolbar.addSeparator()

        action = Qt.QAction(self)
        action.setIcon(Qt.QIcon("icons:image.png"))
        action.setCheckable(True)
        action.setText("Pixel viewer")
        action.setToolTip("Show pixel viewer")
        action.setChecked(not self.__pixel.isHidden())
        action.toggled.connect(self.setPixelVisible)
        self.__showPixelAction = action
        self.__toolbar.addAction(self.__showPixelAction)

        self.__pixelTools = PixelTools(self.__toolbar)
        self.__pixelTools.setView(self.__pixel)

        self.__toolbar.addSeparator()

        action = Qt.QAction(self)
        action.setIcon(Qt.QIcon("icons:sample.png"))
        action.setCheckable(True)
        action.setText("Audio wave viewer")
        action.setToolTip("Show audio wave viewer")
        action.setChecked(not self.__wave.isHidden())
        action.toggled.connect(self.setWaveVisible)
        self.__showWaveAction = action
        self.__toolbar.addAction(self.__showWaveAction)

        self.__waveTools = SampleTools(self.__toolbar)
        self.__waveTools.setView(self.__wave)

        self.__selectionOffset = Qt.QLabel(self.__statusbar)
        self.__selectionSize = Qt.QLabel(self.__statusbar)
        self.__statusbar.addWidget(Qt.QLabel("Selection:"), 0)
        self.__statusbar.addWidget(self.__selectionOffset, 0)
        self.__statusbar.addWidget(self.__selectionSize, 0)

        layout = Qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__toolbar)
        layout.addWidget(self.__pixel)
        layout.addWidget(self.__wave)
        layout.addWidget(self.__hexa)
        layout.addWidget(self.__statusbar)
        layout.setStretchFactor(self.__pixel, 1)
        layout.setStretchFactor(self.__wave, 1)
        layout.setStretchFactor(self.__hexa, 1)

        self.__pixel.selectionChanged.connect(self.__onSelectionChanged)
        self._updateSelection(self.selection())

    def __onSelectionChanged(self, selection: tuple[int, int] | None):
        # Assume each widget have the same address origin
        with blockSignals(self.__wave):
            self.__wave.setSelection(selection)
        with blockSignals(self.__pixel):
            self.__pixel.setSelection(selection)
        with blockSignals(self.__hexa):
            if selection is None:
                address = None
            else:
                address = (
                    self.__address + selection[0],
                    self.__address + selection[1]
                )
            self.__hexa.setAddressSelection(address)
        self._updateSelection(self.selection())

    def _updateSelection(self, selection: tuple[int, int] | None):
        if selection is None:
            self.__selectionOffset.setText("No selection")
            self.__selectionSize.setText("")
        else:
            s = selection
            self.__selectionOffset.setText(f"{f_address(s[0])}...{f_address(s[1]-1)}")
            size = s[1] - s[0]
            self.__selectionSize.setText(f"{size}B")

    def selection(self) -> tuple[int, int] | None:
        """Return the address selection"""
        selection = self.__pixel.selection()
        if selection is None:
            return None
        return self.__address + selection[0], self.__address + selection[1]

    def __positionChanged(self, position: int):
        with blockSignals(self.__pixel):
            self.__pixel.setPosition(position)
        with blockSignals(self.__wave):
            self.__wave.setPosition(position)
        with blockSignals(self.__hexa):
            self.__hexa.setPosition(position)

    def setPixelVisible(self, visible: bool):
        self.__pixel.setVisible(visible)
        self.__pixelTools.setVisible(visible)

    def setWaveVisible(self, visible: bool):
        self.__wave.setVisible(visible)
        self.__waveTools.setVisible(visible)

    def setHexaVisible(self, visible: bool):
        self.__hexa.setVisible(visible)

    def rom(self) -> GBAFile | None:
        return self.__rom

    def setRom(self, rom: GBAFile | None):
        self.__rom = rom

    def setPosition(self, pos: int):
        self.__pixel.setPosition(pos)
        self.__wave.setPosition(pos)
        self.__hexa.setPosition(pos)

    def moveToPreviousByte(self):
        pos = self.__wave.position() - 1
        pos = max(pos, 0)
        self.setPosition(pos)

    def keyPressEvent(self, event: Qt.QKeyEvent):
        if event.key() == Qt.Qt.Key_Left:
            self.moveToPreviousByte()
        elif event.key() == Qt.Qt.Key_Right:
            self.moveToNextByte()
        elif event.key() == Qt.Qt.Key_PageUp:
            self.moveToPreviousPage()
        elif event.key() == Qt.Qt.Key_PageDown:
            self.moveToNextPage()

    def moveToNextByte(self):
        pos = self.__wave.position() + 1
        pos = min(pos, self.__wave.memoryLength())
        self.setPosition(pos)

    def moveToPreviousPage(self):
        # FIXME: Have to be improved
        pos = self.__wave.position() - self.__wave.width()
        pos = max(pos, 0)
        self.setPosition(pos)

    def moveToNextPage(self):
        # FIXME: Have to be improved
        pos = self.__wave.position() + self.__wave.width()
        pos = min(pos, self.__wave.memoryLength())
        self.setPosition(pos)

    def memory(self) -> io.IOBase:
        return self.__wave.memory()

    def setMemory(self, memory: io.IOBase, address: int = 0):
        self.__address = address
        self.__pixel.setMemory(memory)
        self.__wave.setMemory(memory)
        self.__hexa.setMemory(memory, address=address)

    def address(self) -> int:
        return self.__address

    def showMemoryMapRaw(self, mem: MemoryMap):
        rom = self.__rom
        if rom is None:
            return
        self.__mem = mem
        data = rom.extract_raw(mem)
        memory = io.BytesIO(data)
        address = mem.byte_offset
        self.setMemory(memory, address=address)

    def showMemoryMapData(self, mem: MemoryMap):
        rom = self.__rom
        if rom is None:
            return
        data = rom.extract_data(mem)
        memory = io.BytesIO(data.tobytes())
        if mem.byte_codec in (None, ByteCodec.RAW):
            address = mem.byte_offset
            self.__mem = mem
        else:
            # Absolute ROM location have no meaning here
            address = 0
            self.__mem = None
        self.setMemory(memory, address=address)

    def _showPixelContextMenu(self, pos: Qt.QPoint):
        globalPos = self.__pixel.mapToGlobal(pos)
        menu = Qt.QMenu(self)

        mem = self.__mem
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
        mem = self.__mem
        if mem is None:
            return

        selection = self.selection()
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
            image_color_mode=self.__pixel.colorMode(),
            image_pixel_order=self.__pixel.pixelOrder(),
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

        context = self.parent()
        memoryMapList = context.memoryMapList()
        index = memoryMapList.objectIndex(mem).row()
        memoryMapList.removeObject(mem)
        if prevMem is not None:
            memoryMapList.insertObject(index, prevMem)
            index += 1
        if selectedMem is not None:
            memoryMapList.insertObject(index, selectedMem)
            index += 1
        if nextMem is not None:
            memoryMapList.insertObject(index, nextMem)

    def _showHexaContextMenu(self, pos: Qt.QPoint):
        globalPos = self.__hexa.mapToGlobal(pos)
        menu = Qt.QMenu(self)

        mem = self.__mem
        if mem is None:
            return

        if mem.byte_codec not in (None, ByteCodec.RAW):
            # Actually we can't split such memory
            return

        offset = self.__hexa.selectedOffset()
        if offset is None:
            return

        split = Qt.QAction(menu)
        split.setText("Split memory map before this address")
        split.triggered.connect(self._splitMemoryMap)
        menu.addAction(split)

        self.__splitSappySample.setOffset(offset)

        split = Qt.QAction(menu)
        split.setText("Extract as sappy sample")
        split.setIcon(Qt.QIcon("icons:sample.png"))
        split.triggered.connect(self.__splitSappySample.run)
        menu.addAction(split)

        split = Qt.QAction(menu)
        split.setText("Extract as sappy sample +1 byte")
        split.setIcon(Qt.QIcon("icons:sample.png"))
        split.triggered.connect(self.__splitSappySample.runPlusOne)
        menu.addAction(split)

        menu.exec(globalPos)

    def _splitMemoryMap(self):
        """Split the memory map at the selection"""
        mem = self.__mem
        if mem is None:
            return

        offset = self.__hexa.selectedOffset()
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

        context = self.parent()
        memoryMapList = context.memoryMapList()
        index = memoryMapList.objectIndex(mem).row()
        memoryMapList.removeObject(mem)
        if prevMem.byte_length:
            memoryMapList.insertObject(index, prevMem)
            index = index + 1
        if nextMem.byte_length:
            memoryMapList.insertObject(index, nextMem)

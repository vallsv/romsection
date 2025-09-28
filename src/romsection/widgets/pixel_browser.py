import os
import io
import numpy
from PyQt5 import Qt

from ..gba_file import ImageColorMode, ImagePixelOrder
from .. import array_utils
from .pixel_browser_widget import PixelBrowserWidget
from .image_pixel_order_combo import ImagePixelOrderCombo
from .image_color_mode_combo import ImageColorModeCombo


class PixelBrowser(Qt.QFrame):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QFrame.__init__(self, parent=parent)
        self.setFrameShadow(Qt.QFrame.Sunken)
        self.setFrameShape(Qt.QFrame.StyledPanel)

        self.__widget = PixelBrowserWidget(self)
        self.__scroll = Qt.QScrollBar(self)
        self.__scroll.setTracking(True)
        self.__toolbar = Qt.QToolBar(self)

        self.__zoom = Qt.QSpinBox(self.__toolbar)
        self.__zoom.setRange(1, 16)
        self.__zoom.setValue(self.__widget.zoom())
        self.__toolbar.addWidget(self.__zoom)

        self.__pixelWidth = Qt.QSpinBox(self.__toolbar)
        self.__pixelWidth.setRange(1, 128)
        self.__pixelWidth.setValue(self.__widget.pixelWidth())
        self.__toolbar.addWidget(self.__pixelWidth)

        self.__colorMode = ImageColorModeCombo(self.__toolbar)
        self.__colorMode.selectValue(self.__widget.colorMode())
        self.__toolbar.addWidget(self.__colorMode)

        self.__pixelOrder = ImagePixelOrderCombo(self.__toolbar)
        self.__pixelOrder.selectValue(self.__widget.pixelOrder())
        self.__toolbar.addWidget(self.__pixelOrder)

        layout = Qt.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self.__toolbar, 0, 0, 1, 1)
        layout.addWidget(self.__widget, 1, 0)
        layout.addWidget(self.__scroll, 1, 1)
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(1, 1)

        self.__zoom.valueChanged.connect(self.__zoomChanged)
        self.__pixelWidth.valueChanged.connect(self.__pixelWidthChanged)
        self.__colorMode.currentIndexChanged.connect(self.__colorModeChanged)
        self.__pixelOrder.currentIndexChanged.connect(self.__pixelOrderChanged)
        self.__scroll.valueChanged.connect(self.__positionChanged)

        shortcut = Qt.QShortcut(Qt.QKeySequence("Left"), self)
        shortcut.activated.connect(self.moveToPreviousByte)
        shortcut = Qt.QShortcut(Qt.QKeySequence("Right"), self)
        shortcut.activated.connect(self.moveToNextByte)
        shortcut = Qt.QShortcut(Qt.QKeySequence("Up"), self)
        shortcut.activated.connect(self.moveToPreviousLine)
        shortcut = Qt.QShortcut(Qt.QKeySequence("Down"), self)
        shortcut.activated.connect(self.moveToNextLine)

    def moveToPreviousByte(self):
        pos = self.__widget.position() - 1
        pos = max(pos, 0)
        self.__widget.setPosition(pos)

    def moveToNextByte(self):
        pos = self.__widget.position() + 1
        pos = min(pos, self.__widget.memoryLength())
        self.__widget.setPosition(pos)

    def moveToPreviousLine(self):
        pos = self.__widget.position() - self.__widget.bytesPerLine()
        pos = max(pos, 0)
        self.__widget.setPosition(pos)

    def moveToNextLine(self):
        pos = self.__widget.position() + self.__widget.bytesPerLine()
        pos = min(pos, self.__widget.memoryLength())
        self.__widget.setPosition(pos)

    def __zoomChanged(self, zoom: int):
        self.__widget.setZoom(zoom)

    def __pixelWidthChanged(self, pixelWidth: int):
        self.__widget.setPixelWidth(pixelWidth)

    def __colorModeChanged(self, index: int):
        value = self.__colorMode.itemData(index)
        self.__widget.setColorMode(value)

    def __pixelOrderChanged(self, index: int):
        value = self.__pixelOrder.itemData(index)
        self.__widget.setPixelOrder(value)

    def __positionChanged(self, position: int):
        self.__widget.setPosition(position)

    def pixelWidth(self) -> int:
        return self.__widget.pixelWidth()

    def setPixelWidth(self, width: int):
        return self.__widget.setPixelWidth(width)

    def memory(self) -> io.IOBase:
        return self.__widget.memory()

    def setMemory(self, memory: io.IOBase):
        self.__widget.setMemory(memory)
        self.__scroll.setValue(0)
        self.__scroll.setRange(0, self.__widget.memoryLength())

    def colorMode(self) -> ImageColorMode:
        return self.__widget.colorMode()

    def setColorMode(self, colorMode: ImageColorMode):
        self.__widget.setColorMode(colorMode)

    def pixelOrder(self) -> ImagePixelOrder:
        return self.__widget.pixelOrder()

    def setPixelOrder(self, pixelOrder: ImagePixelOrder):
        self.__widget.setPixelOrder(pixelOrder)

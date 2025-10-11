import os
import io
import numpy
from PyQt5 import Qt

from ..gba_file import ImageColorMode, ImagePixelOrder
from .. import array_utils
from ..format_utils import format_address as f_address
from .pixel_browser_widget import PixelBrowserWidget
from .image_pixel_order_combo import ImagePixelOrderCombo
from .image_color_mode_combo import ImageColorModeCombo


class PixelBrowser(Qt.QWidget):
    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)

        self.__address: int = 0

        self.__widget = PixelBrowserWidget(self)
        self.__toolbar = Qt.QToolBar(self)
        self.__statusbar = Qt.QStatusBar(self)

        self.__selectionOffset = Qt.QLabel(self.__statusbar)
        self.__selectionSize = Qt.QLabel(self.__statusbar)
        self.__statusbar.addWidget(Qt.QLabel("Selection:"), 0)
        self.__statusbar.addWidget(self.__selectionOffset, 0)
        self.__statusbar.addWidget(self.__selectionSize, 0)

        self.__zoom = Qt.QSpinBox(self.__toolbar)
        self.__zoom.setRange(1, 16)
        self.__zoom.setValue(self.__widget.zoom())
        self.__toolbar.addWidget(self.__zoom)

        self.__pixelWidth = Qt.QSpinBox(self.__toolbar)
        self.__pixelWidth.setRange(1, 128 * 4)
        self.__pixelWidth.setValue(self.__widget.pixelWidth())
        self.__toolbar.addWidget(self.__pixelWidth)

        self.__colorMode = ImageColorModeCombo(self.__toolbar)
        self.__colorMode.selectValue(self.__widget.colorMode())
        self.__toolbar.addWidget(self.__colorMode)

        self.__pixelOrder = ImagePixelOrderCombo(self.__toolbar)
        self.__pixelOrder.selectValue(self.__widget.pixelOrder())
        self.__toolbar.addWidget(self.__pixelOrder)

        layout = Qt.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self.__toolbar)
        layout.addWidget(self.__widget)
        layout.addWidget(self.__statusbar)
        layout.setStretchFactor(self.__widget, 1)

        self.__zoom.valueChanged.connect(self.__zoomChanged)
        self.__pixelWidth.valueChanged.connect(self.__pixelWidthChanged)
        self.__colorMode.currentIndexChanged.connect(self.__colorModeChanged)
        self.__pixelOrder.currentIndexChanged.connect(self.__pixelOrderChanged)
        self.__widget.selectionChanged.connect(self.__onSelectionChanged)

        self._updateSelection(self.selection())

    def __onSelectionChanged(self, selection: tuple[int, int] | None):
        self._updateSelection(self.selection())

    def _updateSelection(self, selection: tuple[int, int] | None):
        if selection is None:
            self.__selectionOffset.setText("No selection")
            self.__selectionSize.setText("")
        else:
            s = self.__address + selection[0], self.__address + selection[1]
            self.__selectionOffset.setText(f"{f_address(s[0])}...{f_address(s[1]-1)}")
            size = s[1] - s[0]
            self.__selectionSize.setText(f"{size}B")

    def selection(self) -> tuple[int, int] | None:
        selection = self.__widget.selection()
        if selection is None:
            return selection
        return self.__address + selection[0], self.__address + selection[1]

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

    def pixelWidth(self) -> int:
        return self.__widget.pixelWidth()

    def setPixelWidth(self, width: int):
        return self.__widget.setPixelWidth(width)

    def memory(self) -> io.IOBase:
        return self.__widget.memory()

    def setMemory(self, memory: io.IOBase, address: int = 0):
        self.__address = address
        self.__widget.setMemory(memory)
        self.__widget.setPosition(0)

    def address(self) -> int:
        return self.__address

    def colorMode(self) -> ImageColorMode:
        return self.__widget.colorMode()

    def setColorMode(self, colorMode: ImageColorMode):
        self.__widget.setColorMode(colorMode)

    def pixelOrder(self) -> ImagePixelOrder:
        return self.__widget.pixelOrder()

    def setPixelOrder(self, pixelOrder: ImagePixelOrder):
        self.__widget.setPixelOrder(pixelOrder)

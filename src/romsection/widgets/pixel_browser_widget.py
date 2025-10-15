import os
import io
import numpy
import dataclasses
from PyQt5 import Qt

from ..gba_file import ImageColorMode, ImagePixelOrder
from .. import array_utils
from ..codec import byte_per_element, pixel_per_element
from ..qt_utils import blockSignals


@dataclasses.dataclass
class PixelSelection:
    x: int
    y: int
    tileX: int | None
    tileY: int | None


def contiguousMemorySelection(
    indexFrom: int,
    indexToInside: int,
    indexToOutside: int,
    byteWidth: int,
    pixelSize: int,
    left: int,
    right: int,
    pixelFromBytePosition,
    bytesPerLine,
) -> Qt.QPainterPath:
    """Create a selection of continuous memory in an image"""
    path = Qt.QPainterPath()

    if indexToOutside - indexFrom <= bytesPerLine:
        pfrom = pixelFromBytePosition(indexFrom)
        pto = pixelFromBytePosition(indexToInside)
        if pfrom.y == pto.y:
            # Same line
            path.moveTo(pfrom.x, pfrom.y + pixelSize)
            path.lineTo(pfrom.x, pfrom.y)
            path.lineTo(pto.x + byteWidth, pto.y)
            path.lineTo(pto.x + byteWidth, pto.y + pixelSize)
            path.closeSubpath()
        else:
            # Non contiguous
            path.moveTo(pfrom.x, pfrom.y + pixelSize)
            path.lineTo(pfrom.x, pfrom.y)
            path.lineTo(right, pfrom.y)
            path.lineTo(right, pfrom.y + pixelSize)
            path.closeSubpath()
            path.moveTo(pto.x + byteWidth, pto.y + pixelSize)
            path.lineTo(pto.x + byteWidth, pto.y)
            path.lineTo(left, pto.y)
            path.lineTo(left, pto.y + pixelSize)
            path.closeSubpath()
    else:
        # General case
        pfrom = pixelFromBytePosition(indexFrom)
        pto = pixelFromBytePosition(indexToOutside)
        path.moveTo(left, pfrom.y + pixelSize)
        path.lineTo(pfrom.x, pfrom.y + pixelSize)
        path.lineTo(pfrom.x, pfrom.y)
        path.lineTo(right, pfrom.y)
        path.lineTo(right, pto.y)
        path.lineTo(pto.x, pto.y)
        path.lineTo(pto.x, pto.y + pixelSize)
        path.lineTo(left, pto.y + pixelSize)
        path.closeSubpath()

    return path


class PixelBrowserView(Qt.QWidget):

    selectionChanged = Qt.pyqtSignal(object)

    positionChanged = Qt.pyqtSignal(int)

    pageSizeChanged = Qt.pyqtSignal(int)

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)

        self.__colorMode = ImageColorMode.INDEXED_8BIT
        self.__pixelOrder = ImagePixelOrder.NORMAL
        self.__memory: io.IOBase = io.BytesIO(b"")
        self.__pos: int = 0
        self.__len: int = 0
        self.__pixelWidth: int = 48
        self.__zoom: int = 8
        self.__selectionFrom: int = -1
        self.__selectionTo: int = -1
        self.__inSelection = False

    def paintEvent(self, event: Qt.QPaintEvent):
        painter = Qt.QPainter(self)
        self._paintAll(painter)

    def _paintAll(self, painter: Qt.QPainter):
        painter.save()
        parent = self.parent()

        transform = Qt.QTransform()
        transform = transform.scale(self.__zoom, self.__zoom)
        painter.setTransform(transform)

        visibleHeight = self.height() // self.__zoom
        if self.height() % self.__zoom != 0:
            visibleHeight += 1

        height = self._getConstrainedHeight(visibleHeight)
        width = self._getConstrainedWidth(self.__pixelWidth)

        nb_pixels = width * height
        nb_bytes = self._getNbBytesPerPixels(nb_pixels)

        binaryData = self._readBytes(self.__pos, nb_bytes)
        nbEasyBytes = self._getNbBytesForEasyDisplay(len(binaryData), width)
        easyBytes = binaryData[0:nbEasyBytes]
        image = self._toImage(easyBytes, width)
        painter.drawImage(Qt.QPoint(0, 0), image)

        pos = image.height()
        remainingBytes = binaryData[nbEasyBytes:]
        image = self._toImageFromLastRow(remainingBytes)
        if image is not None:
            painter.drawImage(Qt.QPoint(0, pos), image)

        painter.resetTransform()

        path = self._createSelectionPath()
        if path is not None:
            pen = Qt.QPen(Qt.QColor(0, 0, 255))
            pen.setWidth(min(max(self.__zoom // 3, 1), 4))
            painter.setPen(pen)
            painter.drawPath(path)

        painter.restore()

    def setSelection(self, selection: tuple[int, int] | None):
        if self.__inSelection:
            # In the mouse selection interaction
            # Cancel the request from outside
            return
        if selection is None:
            selection = (-1, -1)
        if selection == (self.__selectionFrom, self.__selectionTo):
            return
        self.__selectionFrom, self.__selectionTo = selection
        bpe = byte_per_element(self.__colorMode)
        self.__selectionTo -= bpe
        self.update()

    def selection(self) -> tuple[int, int] | None:
        """
        Return the selection.

        Return:
            A tuple with the position range.
            The first is included, the second is excluded.
        """
        if self.__selectionFrom == -1 or self.__selectionTo == -1:
            return None
        bpe = byte_per_element(self.__colorMode)
        if self.__selectionFrom <= self.__selectionTo:
            return self.__selectionFrom, self.__selectionTo + bpe
        else:
            return self.__selectionTo, self.__selectionFrom + bpe

    def zoom(self) -> int:
        return self.__zoom

    def setZoom(self, zoom: int):
        if zoom == self.__zoom:
            return
        self.__zoom = zoom
        self._updatePageSize()
        self.update()

    def position(self) -> int:
        return self.__pos

    def setPosition(self, position: int):
        if position == self.__pos:
            return
        self.__pos = position
        self.positionChanged.emit(position)
        self.update()

    def pixelWidth(self) -> int:
        return self.__pixelWidth

    def setPixelWidth(self, pixelWidth: int):
        if pixelWidth == self.__pixelWidth:
            return
        self.__pixelWidth = pixelWidth
        self._updatePageSize()
        self.update()

    def memory(self) -> io.IOBase:
        return self.__memory

    def setMemory(self, memory: io.IOBase):
        if self.__memory == memory:
            return
        self.__memory = memory

        self.__memory.seek(0, os.SEEK_END)
        self.__len = self.__memory.tell()
        self.__memory.seek(0, os.SEEK_SET)
        self.__pos = 0

        self._updatePageSize()
        self.update()

    def memoryLength(self) -> int:
        return self.__len

    def colorMode(self) -> ImageColorMode:
        return self.__colorMode

    def setColorMode(self, colorMode: ImageColorMode):
        if self.__colorMode == colorMode:
            return
        self.__colorMode = colorMode
        self._updatePageSize()
        self.update()

    def pixelOrder(self) -> ImagePixelOrder:
        return self.__pixelOrder

    def setPixelOrder(self, pixelOrder: ImagePixelOrder):
        if self.__pixelOrder == pixelOrder:
            return
        self.__pixelOrder = pixelOrder
        self._updatePageSize()
        self.update()

    def _updatePageSize(self):
        self.pageSizeChanged.emit(self.pageSize())

    def _readBytes(self, pos: int, length: int) -> bytes:
        """
        Read an amount of bytes.

        The amount of bytes can differ from the request if the
        steam is empty.
        """
        self.__memory.seek(pos, os.SEEK_SET)
        return self.__memory.read(length)

    def _getNbBytesPerPixels(self, nb_pixels: int) -> int:
        """Return the minimal nb bytes mandatory to display `nb_pixels`."""
        if self.__pixelOrder == ImagePixelOrder.NORMAL:
            pass
        elif self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            # Have to be aligned to the next 8x8 pixels
            remained = nb_pixels % 8 * 8
            if remained != 0:
                nb_pixels += 8 * 8 - remained
        else:
            raise ValueError(f"Unsupported {self.__pixelOrder}")

        if self.__colorMode == ImageColorMode.INDEXED_8BIT:
            result = nb_pixels
        elif self.__colorMode == ImageColorMode.INDEXED_4BIT:
            remainded = nb_pixels % 2
            result = nb_pixels // 2
            if remainded != 0:
                # Have to be aligned to the next 2 pixels
                result += 1
        elif self.__colorMode == ImageColorMode.A1RGB15:
            result = nb_pixels * 2
        elif self.__colorMode == ImageColorMode.RGB15:
            result = nb_pixels * 2
        else:
            raise ValueError(f"Unsupported {self.__colorMode}")

        return result

    def _getConstrainedHeight(self, height: int) -> int:
        """
        Use the codec constraint to allow to display at least this `height`.
        """
        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            remaining = height % 8
            if remaining != 0:
                height += 8 - remaining
        return height

    def _getConstrainedWidth(self, width: int) -> int:
        """
        Use the codec constraint to allow to display at least this `width`.
        """
        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            remaining = width % 8
            if remaining != 0:
                width += 8 - remaining
        if self.__colorMode == ImageColorMode.INDEXED_4BIT:
            # Only display lines aligned to a byte
            if width % 2 != 0:
                width += 1
        return width

    def _getNbBytesForEasyDisplay(self, max_bytes: int, width: int) -> int:
        """
        Return the nb bytes which are easy to display.

        It's the minimal nb bytes, smaller or equal than this `nb_bytes`,
        which can be used to dispklay a full rectangle of the requested
        `width`.
        """
        if self.__pixelOrder == ImagePixelOrder.NORMAL:
            nb_pixels_for_width = width
        elif self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            # The width should already be properly constrainted
            assert width % 8 == 0
            nb_tile_per_width = width // 8
            nb_pixels_for_width = nb_tile_per_width * 8 * 8
        else:
            raise ValueError(f"Unsupported {self.__pixelOrder}")

        if self.__colorMode == ImageColorMode.INDEXED_8BIT:
            nb_bytes_for_width = nb_pixels_for_width
        elif self.__colorMode == ImageColorMode.INDEXED_4BIT:
            # The width should already be properly constrainted
            assert width % 2 == 0
            nb_bytes_for_width = nb_pixels_for_width // 2
        elif self.__colorMode == ImageColorMode.A1RGB15:
            nb_bytes_for_width = nb_pixels_for_width * 2
        elif self.__colorMode == ImageColorMode.RGB15:
            nb_bytes_for_width = nb_pixels_for_width * 2
        else:
            raise ValueError(f"Unsupported {self.__colorMode}")

        nb_bytes = max_bytes - max_bytes % nb_bytes_for_width
        return nb_bytes

    def _getBytesPerLine(self, width: int) -> int:
        if self.__colorMode == ImageColorMode.INDEXED_8BIT:
            return width
        elif self.__colorMode == ImageColorMode.INDEXED_4BIT:
            assert width % 2 == 0
            return width // 2
        elif self.__colorMode == ImageColorMode.A1RGB15:
            return width * 2
        elif self.__colorMode == ImageColorMode.RGB15:
            return width * 2
        raise ValueError(f"Unsupported {self.__colorMode}")

    def bytesPerLine(self) -> int:
        width = self._getConstrainedWidth(self.__pixelWidth)
        return self._getBytesPerLine(width)

    def _toImage(self, data: bytes, width: int) -> Qt.QImage:
        if len(data) == 0:
            return Qt.QImage()

        if self.__pixelOrder == ImagePixelOrder.NORMAL:
            pass

        bytes_per_line = self._getBytesPerLine(width)
        height = len(data) // bytes_per_line

        # FIXME: Some cases can have shortcuts

        if self.__colorMode == ImageColorMode.INDEXED_8BIT:
            array = numpy.frombuffer(data, dtype=numpy.uint8)
        elif self.__colorMode == ImageColorMode.INDEXED_4BIT:
            array = numpy.frombuffer(data, dtype=numpy.uint8)
            array = array_utils.convert_8bx1_to_4bx2(array)
            # FIXME: While there is no palette
            array *= 0xF
        elif self.__colorMode == ImageColorMode.A1RGB15:
            array = numpy.frombuffer(data, dtype=numpy.uint16)
            array = array_utils.convert_a1rgb15_to_argb32(array, use_alpha=True)
        elif self.__colorMode == ImageColorMode.RGB15:
            array = numpy.frombuffer(data, dtype=numpy.uint16)
            array = array_utils.convert_a1rgb15_to_argb32(array, use_alpha=False)
        else:
            raise ValueError(f"Unsupported {self.__colorMode}")

        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            array.shape = height, width, -1
            array = array_utils.convert_to_tiled_8x8(array)

        if self.__colorMode in [ImageColorMode.INDEXED_8BIT, ImageColorMode.INDEXED_4BIT]:
            image = Qt.QImage(
                array.tobytes(),
                width,
                height,
                Qt.QImage.Format_Grayscale8,
            )
        else:
            image = Qt.QImage(
                array.tobytes(),
                width,
                height,
                Qt.QImage.Format_ARGB32,
            )
        return image

    def _toImageFromLastRow(self, data: bytes):
        ppe = pixel_per_element(self.__colorMode)
        bpe = byte_per_element(self.__colorMode)

        lostSize = len(data) % bpe
        useData = data[:len(data) - lostSize]
        # FIXME: It would be good to display something when lostSize is not 0

        if self.__pixelOrder != ImagePixelOrder.TILED_8X8:
            width = len(useData) // bpe * ppe
            return self._toImage(useData, width)

        bytesPerTiles = (8 * 8) // ppe * bpe
        missingSize = bytesPerTiles - len(useData) % bytesPerTiles
        useData += b"\x00" * missingSize
        width = (len(useData) // bytesPerTiles) * 8
        # FIXME: It would be good to display something at the place there is no more data
        return self._toImage(useData, width)

    def _pixelFromBytePosition(self, position: int) -> PixelSelection:
        """Return the left-top pcorner position of a memory position."""
        relativePosition = position - self.__pos
        ppe = pixel_per_element(self.__colorMode)
        bpe = byte_per_element(self.__colorMode)
        width = self._getConstrainedWidth(self.__pixelWidth)
        pixelIndex = (relativePosition // bpe) * ppe
        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            bytesPerLine = self.bytesPerLine()
            nbTilesPerLine = width // 8
            nbTiles, tp = divmod(pixelIndex, 8 * 8)
            ty, tx = divmod(nbTiles, nbTilesPerLine)
            y, x = divmod(tp, 8)
            return PixelSelection(
                x=(tx * 8 + x) * self.__zoom,
                y=(ty * 8 + y) * self.__zoom,
                tileX=(tx * 8) * self.__zoom,
                tileY=(ty * 8) * self.__zoom,
            )
        else:
            y, x = divmod(pixelIndex, width)
            return PixelSelection(
                x=x * self.__zoom,
                y=y * self.__zoom,
                tileX=None,
                tileY=None
            )

    def _createSelectionPath(self) -> Qt.QPainterPath | None:
        selection = self.selection()
        if selection is None:
            return None
        width = self._getConstrainedWidth(self.__pixelWidth)
        bytesPerLine = self.bytesPerLine()
        ppe = pixel_per_element(self.__colorMode)
        bpe = byte_per_element(self.__colorMode)
        byteWidth = self.__zoom * ppe
        pixelSize = self.__zoom

        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            pfrom = self._pixelFromBytePosition(selection[0])
            pto = self._pixelFromBytePosition(selection[1])
            assert pfrom.tileX is not None
            assert pfrom.tileY is not None
            assert pto.tileX is not None
            assert pto.tileY is not None

            if pfrom.tileX == pto.tileX and pfrom.tileY == pto.tileY:
                # Back to the contiguous memory
                assert pfrom.tileX is not None
                return contiguousMemorySelection(
                    indexFrom=selection[0],
                    indexToInside=selection[1] - bpe,
                    indexToOutside=selection[1],
                    left=pfrom.tileX,
                    right=pfrom.tileX + 8 * self.__zoom,
                    byteWidth=byteWidth,
                    pixelSize=self.__zoom,
                    bytesPerLine=8 // ppe * bpe,
                    pixelFromBytePosition=self._pixelFromBytePosition,
                )
            else:
                # General tile case
                sameTileY = pfrom.tileY == pto.tileY
                path = Qt.QPainterPath()
                # part on top
                path.moveTo(pfrom.x, pfrom.y + 1 * pixelSize)
                path.lineTo(pfrom.x, pfrom.y)
                path.lineTo(pfrom.tileX + 8 * pixelSize, pfrom.y)
                path.lineTo(pfrom.tileX + 8 * pixelSize, pfrom.tileY)
                if not sameTileY:
                    path.lineTo(width * pixelSize, pfrom.tileY)
                    # part on bottom
                    path.lineTo(width * pixelSize, pto.tileY)
                if not sameTileY or pto.y != pto.tileY:
                    path.lineTo(pto.tileX + 8 * pixelSize, pto.tileY)
                    path.lineTo(pto.tileX + 8 * pixelSize, pto.y)
                path.lineTo(pto.x, pto.y)
                path.lineTo(pto.x, pto.y + pixelSize)
                path.lineTo(pto.tileX, pto.y + pixelSize)
                path.lineTo(pto.tileX, pto.tileY + 8 * pixelSize)
                if not sameTileY:
                    path.lineTo(0, pto.tileY + 8 * pixelSize)
                    # back on top
                    path.lineTo(0, pfrom.tileY + 8 * pixelSize)
                if not sameTileY or pfrom.y != pfrom.tileY + 7 * pixelSize:
                    path.lineTo(pfrom.tileX, pfrom.tileY + 8 * pixelSize)
                    path.lineTo(pfrom.tileX, pfrom.y + 1 * pixelSize)
                path.closeSubpath()
                return path
        else:
            return contiguousMemorySelection(
                indexFrom=selection[0],
                indexToInside=selection[1] - bpe,
                indexToOutside=selection[1],
                left=0,
                right=width * self.__zoom,
                byteWidth=byteWidth,
                pixelSize=self.__zoom,
                bytesPerLine=bytesPerLine,
                pixelFromBytePosition=self._pixelFromBytePosition,
            )

    def _positionFromPixel(self, pos: Qt.QPoint) -> int:
        x = pos.x() // self.__zoom
        y = pos.y() // self.__zoom
        width = self._getConstrainedWidth(self.__pixelWidth)
        x = min(x, width)

        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            tx, x = divmod(x, 8)
            ty, y = divmod(y, 8)
            pixelIndex = ty * width * 8 + tx * 8 * 8 + y * 8 + x
        else:
            pixelIndex = x + width * y
        ppe = pixel_per_element(self.__colorMode)
        bpe = byte_per_element(self.__colorMode)
        byteIndex = (pixelIndex // ppe) * bpe
        return min(max(self.__pos + byteIndex, 0), self.__len)

    def pageSize(self) -> int:
        height = self.height()
        zoom = self.__zoom
        pixelHeight, _ = divmod(height, zoom)
        if self.__pixelOrder == ImagePixelOrder.TILED_8X8:
            tileHeight, _ = divmod(pixelHeight, 8)
            pixelHeight = tileHeight * 8
        bytesPerLine = self.bytesPerLine()
        return pixelHeight * bytesPerLine

    def resizeEvent(self, event):
        self.update()
        self.pageSizeChanged.emit(self.pageSize())

    def mousePressEvent(self, event: Qt.QMouseEvent):
        if event.button() == Qt.Qt.LeftButton:
            self.grabMouse()
            pos = self._positionFromPixel(event.pos())
            self.__selectionFrom = pos
            self.__selectionTo = -1
            self.__inSelection = True
            self.update()
            self.selectionChanged.emit(self.selection())

    def mouseMoveEvent(self, event: Qt.QMouseEvent):
        if self.mouseGrabber() is self:
            pos = self._positionFromPixel(event.pos())
            self.__selectionTo = pos
            self.update()
            self.selectionChanged.emit(self.selection())

    def mouseReleaseEvent(self, event: Qt.QMouseEvent):
        if event.button() == Qt.Qt.LeftButton:
            self.releaseMouse()
            if self.__selectionTo == -1:
                # The mouse have not moved, that's a way to deselect
                return
            pos = self._positionFromPixel(event.pos())
            self.__selectionTo = pos
            self.__inSelection = False
            self.update()
            self.selectionChanged.emit(self.selection())
        else:
            self.__inSelection = False

    def wheelEvent(self, event: Qt.QWheelEvent):
        deltaY = event.angleDelta().y()
        if deltaY != 0:
            pos = self.position() - self.bytesPerLine() * deltaY
            pos = min(max(pos, 0), max(self.memoryLength() - self.pageSize(), 0))
            self.setPosition(pos)


class PixelBrowserWidget(Qt.QFrame):

    positionChanged = Qt.pyqtSignal(int)

    selectionChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QFrame.__init__(self, parent=parent)
        self.setSizePolicy(Qt.QSizePolicy.Expanding, Qt.QSizePolicy.Expanding)
        self.setFrameShadow(Qt.QFrame.Sunken)
        self.setFrameShape(Qt.QFrame.StyledPanel)
        self.setFocusPolicy(Qt.Qt.StrongFocus)

        self.__view = PixelBrowserView(self)

        self.__scroll = Qt.QScrollBar(self)
        self.__scroll.setTracking(True)
        self.__scroll.setOrientation(Qt.Qt.Vertical)

        layout = Qt.QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__view)
        layout.addWidget(self.__scroll)
        layout.setStretchFactor(self.__view, 1)

        self.__scroll.valueChanged.connect(self.setPosition)
        self.__view.pageSizeChanged.connect(self.__pageChanged)
        self.__view.positionChanged.connect(self.__positionChanged)
        self.__view.selectionChanged.connect(self.__selectionChanged)

    def __pageChanged(self, pageSize: int):
        self.__scroll.setPageStep(pageSize)
        self.__scroll.setRange(0, self.memoryLength() - pageSize)

    def __positionChanged(self, position: int):
        with blockSignals(self.__scroll):
            self.__scroll.setValue(position)
        self.positionChanged.emit(position)

    def __selectionChanged(self, selection: tuple[int, int] | None):
        self.selectionChanged.emit(selection)

    def selection(self) -> tuple[int, int] | None:
        """
        Return the selection.

        Return:
            A tuple with the position range.
            The first is included, the second is excluded.
        """
        return self.__view.selection()

    def setSelection(self, selection: tuple[int, int] | None):
        self.__view.setSelection(selection)

    def zoom(self) -> int:
        return self.__view.zoom()

    def setZoom(self, zoom: int):
        self.__view.setZoom(zoom)

    def position(self) -> int:
        return self.__view.position()

    def setPosition(self, position: int):
        self.__view.setPosition(position)

    def pixelWidth(self) -> int:
        return self.__view.pixelWidth()

    def setPixelWidth(self, pixelWidth: int):
        self.__view.setPixelWidth(pixelWidth)

    def memory(self) -> io.IOBase:
        return self.__view.memory()

    def setMemory(self, memory: io.IOBase):
        self.__view.setMemory(memory)
        pageSize = self.__view.pageSize()
        self.__scroll.setRange(0, self.memoryLength() - pageSize)

    def memoryLength(self) -> int:
        return self.__view.memoryLength()

    def colorMode(self) -> ImageColorMode:
        return self.__view.colorMode()

    def setColorMode(self, colorMode: ImageColorMode):
        self.__view.setColorMode(colorMode)

    def pixelOrder(self) -> ImagePixelOrder:
        return self.__view.pixelOrder()

    def setPixelOrder(self, pixelOrder: ImagePixelOrder):
        self.__view.setPixelOrder(pixelOrder)

    def keyPressEvent(self, event: Qt.QKeyEvent):
        if event.key() == Qt.Qt.Key_Down:
            self.moveToNextLine()
        elif event.key() == Qt.Qt.Key_Up:
            self.moveToPreviousLine()
        elif event.key() == Qt.Qt.Key_Left:
            self.moveToPreviousByte()
        elif event.key() == Qt.Qt.Key_Right:
            self.moveToNextByte()
        elif event.key() == Qt.Qt.Key_PageUp:
            self.moveToPreviousPage()
        elif event.key() == Qt.Qt.Key_PageDown:
            self.moveToNextPage()

    def moveToPreviousByte(self):
        pos = self.__view.position() - 1
        pos = max(pos, 0)
        self.__view.setPosition(pos)

    def moveToNextByte(self):
        pos = self.__view.position() + 1
        pos = min(pos, self.__view.memoryLength())
        self.__view.setPosition(pos)

    def moveToPreviousLine(self):
        pos = self.__view.position() - self.__view.bytesPerLine()
        pos = max(pos, 0)
        self.__view.setPosition(pos)

    def moveToNextLine(self):
        pos = self.__view.position() + self.__view.bytesPerLine()
        pos = min(pos, self.__view.memoryLength())
        self.__view.setPosition(pos)

    def moveToPreviousPage(self):
        pos = self.__view.position() - self.__view.bytesPerLine() * 8
        pos = max(pos, 0)
        self.__view.setPosition(pos)

    def moveToNextPage(self):
        pos = self.__view.position() + self.__view.bytesPerLine() * 8
        pos = min(pos, self.__view.memoryLength())
        self.__view.setPosition(pos)

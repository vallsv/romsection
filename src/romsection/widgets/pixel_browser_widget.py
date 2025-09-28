import os
import io
import numpy
from PyQt5 import Qt

from ..gba_file import ImageColorMode, ImagePixelOrder
from .. import array_utils


def byte_per_element(color_mode: ImageColorMode) -> int:
    """Number of bytes to store a single data element."""
    if color_mode in (ImageColorMode.A1RGB15, ImageColorMode.RGB15):
        return 2
    else:
        return 1


def pixel_per_element(color_mode: ImageColorMode) -> int:
    """Number of pixels stored in a single data element."""
    if color_mode == ImageColorMode.INDEXED_4BIT:
        return 2
    else:
        return 1


class PixelBrowserWidget(Qt.QWidget):

    selectionChanged = Qt.pyqtSignal(object)

    def __init__(self, parent: Qt.QWidget | None = None):
        Qt.QWidget.__init__(self, parent=parent)
        self.__colorMode = ImageColorMode.INDEXED_8BIT
        self.__pixelOrder = ImagePixelOrder.NORMAL
        self.__memory: io.IOBase = io.BytesIO(b"")
        self.__pos: int = 0
        self.__len: int = 0
        self.__pixelWidth: int = 48
        self.__zoom: int = 8
        self.__selectionFrom: int = -1
        self.__selectionTo: int = -1

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
        self.update()

    def position(self) -> int:
        return self.__pos

    def setPosition(self, position: int):
        if position == self.__pos:
            return
        self.__pos = position
        self.update()

    def pixelWidth(self) -> int:
        return self.__pixelWidth

    def setPixelWidth(self, pixelWidth: int):
        if pixelWidth == self.__pixelWidth:
            return
        self.__pixelWidth = pixelWidth
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

        self.update()

    def memoryLength(self) -> int:
        return self.__len

    def colorMode(self) -> ImageColorMode:
        return self.__colorMode

    def setColorMode(self, colorMode: ImageColorMode):
        if self.__colorMode == colorMode:
            return
        self.__colorMode = colorMode
        self.update()

    def pixelOrder(self) -> ImagePixelOrder:
        return self.__pixelOrder

    def setPixelOrder(self, pixelOrder: ImagePixelOrder):
        if self.__pixelOrder == pixelOrder:
            return
        self.__pixelOrder = pixelOrder
        self.update()

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

    def paintEvent(self, event: Qt.QPaintEvent):
        painter = Qt.QPainter(self)
        self._paintAll(painter)

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

    def _paintAll(self, painter: Qt.QPainter):
        painter.save()

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

    def _pixelFromBytePosition(self, position: int) -> Qt.QPoint:
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
            return Qt.QPoint(tx * 8 + x, ty * 8 + y) * self.__zoom
        else:
            y, x = divmod(pixelIndex, width)
            return Qt.QPoint(x, y) * self.__zoom

    def _createSelectionPath(self) -> Qt.QPainterPath | None:
        selection = self.selection()
        if selection is None:
            return None
        width = self._getConstrainedWidth(self.__pixelWidth)
        bytesPerLine = self.bytesPerLine()
        ppe = pixel_per_element(self.__colorMode)
        bpe = byte_per_element(self.__colorMode)
        pwidth = self.__zoom * ppe

        # FIXME: Implement when it's tiled
        path = Qt.QPainterPath()

        if selection[1] - selection[0] <= bytesPerLine:
            pfrom  =self._pixelFromBytePosition(selection[0])
            pto  =self._pixelFromBytePosition(selection[1] - bpe)
            if pfrom.y() == pto.y():
                # Same line
                path.moveTo(pfrom.x(), pfrom.y() + self.__zoom)
                path.lineTo(pfrom)
                path.lineTo(pto.x() + pwidth, pto.y())
                path.lineTo(pto.x() + pwidth, pto.y() + self.__zoom)
                path.closeSubpath()
            else:
                # Non contiguous
                path.moveTo(pfrom.x(), pfrom.y() + self.__zoom)
                path.lineTo(pfrom)
                path.lineTo(width * self.__zoom, pfrom.y())
                path.lineTo(width * self.__zoom, pfrom.y() + self.__zoom)
                path.closeSubpath()
                path.moveTo(pto.x() + pwidth, pto.y() + self.__zoom)
                path.lineTo(pto.x() + pwidth, pto.y())
                path.lineTo(0, pto.y())
                path.lineTo(0, pto.y() + self.__zoom)
                path.closeSubpath()
        else:
            # General case
            pfrom  =self._pixelFromBytePosition(selection[0])
            pto  =self._pixelFromBytePosition(selection[1])
            path.moveTo(0, pfrom.y() + self.__zoom)
            path.lineTo(pfrom.x(), pfrom.y() + self.__zoom)
            path.lineTo(pfrom)
            path.lineTo(width * self.__zoom, pfrom.y())
            path.lineTo(width * self.__zoom, pto.y())
            path.lineTo(pto)
            path.lineTo(pto.x(), pto.y() + self.__zoom)
            path.lineTo(0, pto.y() + self.__zoom)
            path.closeSubpath()

        return path

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
        return self.__pos + byteIndex

    def mousePressEvent(self, event: Qt.QMouseEvent):
        if event.button() == Qt.Qt.LeftButton:
            self.grabMouse()
            pos = self._positionFromPixel(event.pos())
            self.__selectionFrom = pos
            self.__selectionTo = -1
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
                # The mouse habe not moved, it a way to deselect
                return
            pos = self._positionFromPixel(event.pos())
            self.__selectionTo = pos
            self.update()
            self.selectionChanged.emit(self.selection())

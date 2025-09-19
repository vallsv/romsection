import os
import sys
import logging
import yaml
import enum
import numpy

from .lz77 import decompress as decompress_lz77
from .utils import convert_16bx1_to_5bx3, convert_8bx1_to_4bx2, convert_to_tiled_8x8


class DataType(enum.Enum):
    IMAGE = enum.auto()
    PALETTE = enum.auto()


class ColorMode(enum.Enum):
    INDEXED_8BIT = enum.auto()
    INDEXED_4BIT = enum.auto()


class PixelOrder(enum.Enum):
    NORMAL = enum.auto()
    TILED_8X8 = enum.auto()


class MemoryMap:
    def __init__(
        self,
        offset,
        nb_pixels,
        shape: tuple[int, int] | None = None,
        color_mode: ColorMode | None = None,
        length: int | None = None,
        pixel_order: PixelOrder | None = None,
        data_type: DataType | None = None,
    ):
        self.offset = offset
        self.length = length
        self.nb_pixels = nb_pixels
        self.shape = shape
        self.color_mode: ColorMode | None = color_mode
        self.pixel_order: PixelOrder | None = pixel_order
        self.data_type: DataType | None = data_type

    def to_dict(self):
        description = {"offset": self.offset, "nb_pixels": self.nb_pixels}
        if self.shape is not None:
            description["shape"] = list(self.shape)
        if self.color_mode is not None:
            description["color_mode"] = self.color_mode.name
        if self.pixel_order is not None:
            description["pixel_order"] = self.pixel_order.name
        if self.data_type is not None:
            description["data_type"] = self.data_type.name
        if self.length is not None:
            description["length"] = self.length
        return description

    @staticmethod
    def from_dict(description: dict):
        offset = description["offset"]
        nb_pixels = description.get("nb_pixels")
        shape = description.get("shape")
        color_mode = description.get("color_mode")
        pixel_order = description.get("pixel_order")
        data_type = description.get("data_type")
        length = description.get("length")
        if shape is not None:
            shape = tuple(shape)
        if color_mode is not None:
            color_mode = ColorMode[color_mode]
        if pixel_order is not None:
            pixel_order = PixelOrder[pixel_order]
        if data_type is not None:
            data_type = DataType[data_type]
        return MemoryMap(
            offset,
            nb_pixels,
            length=length,
            shape=shape,
            color_mode=color_mode,
            pixel_order=pixel_order,
            data_type=data_type,
        )


class GBAFile:

    def __init__(self, filename: str):
        self._filename = filename
        f = open(filename, "rb")
        self.offsets: list[MemoryMap] = []
        f.seek(0, os.SEEK_END)
        self._size = f.tell()
        f.seek(0, os.SEEK_SET)
        self._f = f

    @property
    def filename(self):
        return self._filename

    @property
    def size(self):
        return self._size

    def scan_all(self):
        self.offsets.clear()
        f = self._f
        f.seek(0, os.SEEK_SET)
        offset = 0
        while offset < self._size:
            try:
                data = decompress_lz77(f)
            except ValueError:
                pass
            else:
                mem = MemoryMap(
                    offset,
                    data.size,
                    data_type=data_type,
                )
                self.offsets.append(mem)
            offset += 1
            f.seek(offset, os.SEEK_SET)

    def extract_raw(self, mem: MemoryMap) -> bytes:
        f = self._f
        f.seek(mem.offset, os.SEEK_SET)
        data = f.read(mem.length)
        return data

    def extract_lz77(self, mem: MemoryMap):
        f = self._f
        f.seek(mem.offset, os.SEEK_SET)
        result = decompress_lz77(f)
        offset_end = f.tell()
        mem.length = offset_end - mem.offset
        return result

    def palette_data(self, mem: MemoryMap) -> numpy.ndarray:
        """
        Return palette data from a memory map.

        Return a 3D array, indexed by palette index, then color index, then RGB components.

        The RBG values are in range of 0..1.

        Raises:
            ValueError: If the memory can't be read as a palette.
        """
        data = self.extract_lz77(mem)

        if mem.data_type != DataType.PALETTE:
            raise ValueError(f"Memory map 0x{mem.offset:08X} is not a palette")

        if data.size % 32 != 0:
            raise ValueError(f"Memory map 0x{mem.offset:08X} don't have the right size")

        nb = data.size // 32
        data = data.view(numpy.uint16)
        data = convert_16bx1_to_5bx3(data)
        data = data / 0x1F
        data.shape = nb, -1, 3
        return data

    def guess_first_shape(self, data):
        if data.size == 240 * 160:
            # LCD mode
            return 160, 240
        if data.size == 160 * 128:
            # LCD mode
            return 128, 160
        # FIXME: Guess something closer to a square
        return 1, data.size

    def image_data(self, mem: MemoryMap) -> numpy.ndarray:
        """
        Return image data from a memory map.

        It can return:
        - A 2D array with indexed data as integer, shaped with axes Y, X
        - A 3D array with 0..1 float, shaped with axes Y, X, RGB

        Raises:
            ValueError: If the memory can't be read.
        """
        if mem.data_type != DataType.IMAGE:
            raise ValueError(f"Memory map 0x{mem.offset:08X} is not an image")

        data = self.extract_lz77(mem)

        if mem.color_mode == ColorMode.INDEXED_4BIT:
            data = convert_8bx1_to_4bx2(data)

        if mem.shape is not None:
            try:
                data.shape = mem.shape
            except Exception:
                data.shape = self.guess_first_shape(data)
        else:
            data.shape = self.guess_first_shape(data)

        if mem.pixel_order == PixelOrder.TILED_8X8:
            if data.shape[0] % 8 != 0 or data.shape[1] % 8 != 0:
                raise ValueError(f"Memory map 0x{mem.offset:08X} use incompatible option: shape {data.shape} can't used with tiled 8x8")
            data = convert_to_tiled_8x8(data)

        return data

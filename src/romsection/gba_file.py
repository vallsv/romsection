import os
import sys
import logging
import yaml
import enum

from .lz77 import decompress as decompress_lz77


class ColorMode(enum.Enum):
    INDEXED_8BIT = enum.auto()
    INDEXED_4BIT = enum.auto()


class MemoryMap:
    def __init__(
        self,
        offset,
        nb_pixels,
        shape: tuple[int, int] | None = None,
        color_mode: ColorMode | None = None,
        length: int | None = None,
    ):
        self.offset = offset
        self.length = length
        self.nb_pixels = nb_pixels
        self.shape = shape
        self.color_mode: ColorMode | None = color_mode

    def to_dict(self):
        description = {"offset": self.offset, "nb_pixels": self.nb_pixels}
        if self.shape is not None:
            description["shape"] = list(self.shape)
        if self.color_mode is not None:
            description["color_mode"] = self.color_mode.name
        if self.length is not None:
            description["length"] = self.length
        return description

    @staticmethod
    def from_dict(description: dict):
        offset = description["offset"]
        nb_pixels = description.get("nb_pixels")
        shape = description.get("shape")
        color_mode = description.get("color_mode")
        length = description.get("length")
        if shape is not None:
            shape = tuple(shape)
        if color_mode is not None:
            color_mode = ColorMode[color_mode]
        return MemoryMap(
            offset,
            nb_pixels,
            shape=shape,
            color_mode=color_mode,
            length=length,
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
                self.offsets.append(MemoryMap(offset, data.size))
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

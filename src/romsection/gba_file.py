import os
import io
import sys
import logging
import enum
import time
import numpy
import typing
import dataclasses
import hashlib

from .parsers import lz77
from .parsers import huffman
from .array_utils import convert_a1rgb15_to_argb32, convert_8bx1_to_4bx2, convert_to_tiled_8x8
from .codec import pixels_per_byte_length
from .model import ByteCodec, DataType, ImageColorMode, ImagePixelOrder, MemoryMap


class GBAFile:

    def __init__(self, filename: str):
        self._filename = filename
        f = open(filename, "rb")
        self.offsets: list[MemoryMap] = []
        f.seek(0, os.SEEK_END)
        self._size = f.tell()
        if self._size < 0xE4:
            raise ValueError(f"File '{filename}' is smaller than the GBA header")
        f.seek(0xB2, os.SEEK_SET)
        fixed_value = f.read(1)
        if fixed_value[0] != 0x96:
            raise ValueError(f"File '{filename}' does not have a valid GBA header")
        f.seek(0, os.SEEK_SET)
        self._f = f

    def memory_map_from_offset(self, byte_offset: int):
        mem = [m for m in self.offsets if m.byte_offset == byte_offset]
        if len(mem) == 0:
            raise ValueError(f"No memory map found at 0x{byte_offset:08X}")
        if len(mem) > 1:
            raise ValueError(f"Multiple memory map found at 0x{byte_offset:08X}")
        return mem[0]

    def memory_map_containing_offset(self, byte_offset: int):
        mem = [m for m in self.offsets if m.byte_offset <= byte_offset < m.byte_end]
        if len(mem) == 0:
            raise ValueError(f"No memory map found at 0x{byte_offset:08X}")
        if len(mem) > 1:
            raise ValueError(f"Multiple memory map found at 0x{byte_offset:08X}")
        return mem[0]

    def palettes(self) -> list[MemoryMap]:
        return [m for m in self.offsets if m.data_type == DataType.PALETTE]

    @property
    def game_title(self):
        f = self._f
        f.seek(0xA0, os.SEEK_SET)
        data = f.read(12)
        title = data.rstrip(b"\x00").decode()
        return title

    @property
    def sha256(self) -> str:
        f = self._f
        f.seek(0, os.SEEK_SET)
        m = hashlib.file_digest(f, "sha256")
        return m.hexdigest()

    @property
    def filename(self):
        return self._filename

    @property
    def size(self):
        return self._size

    def search_for_bytes(self,
        offset_from: int,
        offset_to: int,
        data: bytes
    ) -> list[int]:
        """
        Search for this `data` sequence of bytes in the ROM.

        Return the found offsets.
        """
        size = len(data)
        f = self._f
        offset = offset_from
        result: list[int] = []
        while offset < offset_to:
            f.seek(offset, os.SEEK_SET)
            d = f.read(size)
            if len(d) != size:
                break
            if d == data:
                result.append(offset)
            # FIXME: d can be used to skip even more steps
            offset += 1
        return result

    def search_for_bytes_in_data(self,
        mem: MemoryMap,
        data: bytes
    ) -> list[int]:
        """
        Search for this `data` sequence of bytes in the ROM.

        Return the found offsets.
        """
        decompressed = self.extract_data(mem)
        size = len(data)
        f = io.BytesIO(decompressed)
        offset = 0
        result: list[int] = []
        while offset < len(data):
            f.seek(offset, os.SEEK_SET)
            d = f.read(size)
            if len(d) != size:
                break
            if d == data:
                result.append(offset)
            # FIXME: d can be used to skip even more steps
            offset += 1
        return result

    def extract_raw(self, mem: MemoryMap) -> bytes:
        f = self._f
        f.seek(mem.byte_offset, os.SEEK_SET)
        data = f.read(mem.byte_length)
        return data

    def extract_lz77(self, mem: MemoryMap) -> bytes:
        f = self._f
        f.seek(mem.byte_offset, os.SEEK_SET)
        result = lz77.decompress(f)
        offset_end = f.tell()
        mem.byte_length = offset_end - mem.byte_offset
        mem.byte_payload = len(result)
        return result.tobytes()

    def extract_huffman(self, mem: MemoryMap) -> bytes:
        f = self._f
        f.seek(mem.byte_offset, os.SEEK_SET)
        result = huffman.decompress(f)
        offset_end = f.tell()
        mem.byte_length = offset_end - mem.byte_offset
        mem.byte_payload = len(result)
        return result

    def extract_data(self, mem: MemoryMap) -> bytes:
        """
        Return data after byte codec decompression.
        """
        if mem.byte_codec in [None, ByteCodec.RAW]:
            result = self.extract_raw(mem)
        elif mem.byte_codec == ByteCodec.LZ77:
            result = self.extract_lz77(mem)
        elif mem.byte_codec == ByteCodec.HUFFMAN:
            result = self.extract_huffman(mem)
        return result

    def palette_data(self, mem: MemoryMap) -> numpy.ndarray:
        """
        Return palette data from a memory map.

        Return a 3D array, indexed by palette index, then color index, then RGB components.

        The RBG values are in range of 0..255.

        Raises:
            ValueError: If the memory can't be read as a palette.
        """
        data = self.extract_data(mem)
        array = numpy.frombuffer(data, dtype=numpy.uint8)

        if mem.data_type != DataType.PALETTE:
            raise ValueError(f"Memory map 0x{mem.byte_offset:08X} is not a palette")

        size = mem.palette_size if mem.palette_size is not None else 16
        byte_per_color = 2

        if array.size % (size * byte_per_color) != 0:
            raise ValueError(f"Memory map 0x{mem.byte_offset:08X} don't have the right size")

        nb = array.size // (size * byte_per_color)
        array = convert_a1rgb15_to_argb32(array)
        array.shape = nb, -1, 4
        return array

    def guess_first_image_shape(self, nb_pixels) -> tuple[int, int]:
        if nb_pixels == 240 * 160:
            # LCD mode
            return 160, 240
        if nb_pixels == 160 * 128:
            # LCD mode
            return 128, 160
        # FIXME: Guess something closer to a square
        return 1, nb_pixels

    def byte_payload(self, mem: MemoryMap) -> int:
        """Return the size of the data content, in bytes"""
        if mem.byte_codec in [None, ByteCodec.RAW]:
            if mem.byte_length is None:
                raise ValueError(f"Memory map 0x{mem.byte_offset:08X} have inconcistente description")
            return mem.byte_length

        if mem.byte_payload is not None:
            return mem.byte_payload

        stream = self._f
        stream.seek(mem.byte_offset, os.SEEK_SET)
        if mem.byte_codec == ByteCodec.LZ77:
            return lz77.dryrun(stream)

        if mem.byte_codec == ByteCodec.HUFFMAN:
            return huffman.dryrun(stream)

        raise ValueError(f"Memory map 0x{mem.byte_offset:08X} have unexpected codec {mem.byte_codec}")

    def image_shape(self, mem: MemoryMap) -> tuple[int, int] | None:
        """Only return the image shape.

        FIXME: Could probably be even more simplified.
        """
        if mem.data_type != DataType.IMAGE:
            return None

        if mem.image_shape is not None:
            return mem.image_shape
        else:
            size = self.byte_payload(mem)
            nb_pixels = pixels_per_byte_length(mem.image_color_mode or ImageColorMode.INDEXED_8BIT, size)
            return self.guess_first_image_shape(nb_pixels)

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
            raise ValueError(f"Memory map 0x{mem.byte_offset:08X} is not an image")

        data = self.extract_data(mem)
        array = numpy.frombuffer(data, dtype=numpy.uint8)

        if mem.image_color_mode == ImageColorMode.INDEXED_4BIT:
            array = convert_8bx1_to_4bx2(array)

        if mem.image_shape is not None:
            try:
                array.shape = mem.image_shape
            except Exception:
                array.shape = self.guess_first_image_shape(array.size)
        else:
            array.shape = self.guess_first_image_shape(array.size)

        if mem.image_pixel_order == ImagePixelOrder.TILED_8X8:
            if array.shape[0] % 8 != 0 or array.shape[1] % 8 != 0:
                raise ValueError(f"Memory map 0x{mem.byte_offset:08X} use incompatible option: shape {array.shape} can't used with tiled 8x8")
            array = convert_to_tiled_8x8(array)

        palette_array = None
        if mem.image_palette_offset is not None:
            try:
                palette_map = self.memory_map_from_offset(mem.image_palette_offset)
            except ValueError:
                logging.warning("Error while accessing palette memory map", exc_info=True)
                pass
            else:
                try:
                    palette_array = self.palette_data(palette_map)
                except ValueError:
                    logging.warning("Error while accessing palette data", exc_info=True)
                    pass

        if palette_array is not None:
            try:
                # FIXME: Implement index different than 0
                return palette_array[0][array]
            except Exception:
                logging.warning("Error while processing RGB data from palette", exc_info=True)
                pass
        else:
            if mem.image_color_mode == ImageColorMode.INDEXED_4BIT:
                array *= 16

        return array

    def tile_set_data(self, mem: MemoryMap) -> numpy.ndarray:
        """
        Return tile set data from a memory map.

        It can return:
        - A 3D array with indexed data as integer, shaped with axes TILE_ID, Y, X
        - A 4D array with 0..255 integer, shaped with axes TILE_ID,Y, X, ARGB

        Raises:
            ValueError: If the memory can't be read.
        """
        if mem.data_type != DataType.TILE_SET:
            raise ValueError(f"Memory map 0x{mem.byte_offset:08X} is not an image")

        data = self.extract_data(mem)
        array = numpy.frombuffer(data, dtype=numpy.uint8)

        if mem.image_color_mode == ImageColorMode.INDEXED_4BIT:
            array = convert_8bx1_to_4bx2(array)

        if mem.image_shape is not None:
            try:
                array.shape = -1, 8, 8
            except Exception:
                array.shape = -1, 8, 8
        else:
            array.shape = -1, 8, 8

        palette_array = None
        if mem.image_palette_offset is not None:
            try:
                palette_map = self.memory_map_from_offset(mem.image_palette_offset)
            except ValueError:
                logging.warning("Error while accessing palette memory map", exc_info=True)
                pass
            else:
                try:
                    palette_array = self.palette_data(palette_map)
                except ValueError:
                    logging.warning("Error while accessing palette data", exc_info=True)
                    pass

        if palette_array is not None:
            try:
                array = palette_array[0][array]
            except Exception:
                logging.warning("Error while processing RGB data from palette", exc_info=True)
                pass
        else:
            if mem.image_color_mode == ImageColorMode.INDEXED_4BIT:
                # Better grey scale
                array *= 16

        return array

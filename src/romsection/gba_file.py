import os
import io
import sys
import logging
import enum
import time
import numpy
import typing
import dataclasses

from .lz77 import decompress as decompress_lz77
from .lz77 import dryrun as dryrun_lz77
from .array_utils import convert_a1rgb15_to_argb32, convert_8bx1_to_4bx2, convert_to_tiled_8x8


class ByteCodec(enum.Enum):
    RAW = enum.auto()
    LZ77 = enum.auto()


class DataType(enum.Enum):
    IMAGE = enum.auto()
    """Memory map which can be represented as a image."""

    PALETTE = enum.auto()
    """Memory map compound by a set of colors."""

    UNKNOWN = enum.auto()
    """Memory map which is not yet identified."""

    GBA_ROM_HEADER = enum.auto()
    """
    Memory map containing GBA description.

    See http://problemkaputt.de/gbatek.htm#gbacartridgeheader
    """

    PADDING = enum.auto()
    """
    Memory map which fill the memory with anything (usually 0) for
    better alignement of the next memory map.
    """


class ImageColorMode(enum.Enum):
    INDEXED_8BIT = enum.auto()
    INDEXED_4BIT = enum.auto()


class ImagePixelOrder(enum.Enum):
    NORMAL = enum.auto()
    TILED_8X8 = enum.auto()


@dataclasses.dataclass
class MemoryMap:
    byte_offset: int
    """Offset of the memory related to the ROM."""

    byte_length: int | None = None
    """
    Size of this memory map in  the ROM.

    None means it is not yet precisly identified, for example if compressed.
    """

    byte_codec: ByteCodec | None = None
    """
    Codec use to store the data.
    """

    byte_payload: int | None = None
    """
    Useful byte length.

    This can differe from the `byte_length` depending on the memory codec,
    for example if the data block have some header, or use compression filter.
    """

    data_type: DataType | None = None
    """
    Categorize the data type.

    This influe the interpretation of this data, including the expected metadata.
    """

    palette_size: int | None = None
    """
    Number of color of the palette.
    """

    image_shape: tuple[int, int] | None = None
    """Shape of the image, in numpy order: Y then X"""

    image_color_mode: ImageColorMode | None = None
    """
    Way to interprete the bytes into color.

    This can influe on the size of the image.
    """

    image_pixel_order: ImagePixelOrder | None = None
    """
    Way the pixels are ordered in the memory to be displayed.
    """

    image_palette_offset: int | None = None
    """
    Byte offset from the ROM for the palette to be used, when the image use
    an indexed color mode.
    """

    comment: str | None = None
    """
    Human comment
    """

    def to_dict(self) -> dict[str, typing.Any]:
        description:  dict[str, typing.Any] = {
            "byte_offset": self.byte_offset,
        }
        if self.byte_codec is not None:
            description["byte_codec"] = self.byte_codec.name
        if self.byte_length is not None:
            description["byte_length"] = self.byte_length
        if self.byte_payload is not None:
            description["byte_payload"] = self.byte_payload
        if self.data_type is not None:
            description["data_type"] = self.data_type.name
        if self.image_shape is not None:
            description["image_shape"] = list(self.image_shape)
        if self.image_color_mode is not None:
            description["image_color_mode"] = self.image_color_mode.name
        if self.image_pixel_order is not None:
            description["image_pixel_order"] = self.image_pixel_order.name
        if self.image_palette_offset is not None:
            description["image_palette_offset"] = self.image_palette_offset
        if self.palette_size is not None:
            description["palette_size"] = self.palette_size
        if self.comment is not None:
            description["comment"] = self.comment
        return description

    @staticmethod
    def from_dict(description: dict[str, typing.Any]):
        byte_codec = description.get("byte_codec")
        if byte_codec is not None:
            byte_codec = ByteCodec[byte_codec]
        byte_offset = description["byte_offset"]
        byte_length = description.get("byte_length")
        byte_payload = description.get("byte_payload")
        data_type = description.get("data_type")
        if data_type is not None:
            data_type = DataType[data_type]
        image_shape = description.get("image_shape")
        image_color_mode = description.get("image_color_mode")
        image_pixel_order = description.get("image_pixel_order")
        image_palette_offset = description.get("image_palette_offset")
        if image_shape is not None:
            image_shape = tuple(image_shape)
        if image_color_mode is not None:
            image_color_mode = ImageColorMode[image_color_mode]
        if image_pixel_order is not None:
            image_pixel_order = ImagePixelOrder[image_pixel_order]
        palette_size = description.get("palette_size")
        comment = description.get("comment")
        return MemoryMap(
            byte_offset=byte_offset,
            byte_codec=byte_codec,
            byte_length=byte_length,
            byte_payload=byte_payload,
            data_type=data_type,
            image_shape=image_shape,
            image_color_mode=image_color_mode,
            image_pixel_order=image_pixel_order,
            image_palette_offset=image_palette_offset,
            palette_size=palette_size,
            comment=comment,
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

    def memory_map_from_offset(self, byte_offset: int):
        mem = [m for m in self.offsets if m.byte_offset == byte_offset]
        if len(mem) == 0:
            raise ValueError(f"No memory map found at 0x{byte_offset:08X}")
        if len(mem) > 1:
            raise ValueError(f"Multiple memory map found at 0x{byte_offset:08X}")
        return mem[0]

    def palettes(self) -> list[MemoryMap]:
        return [m for m in self.offsets if m.data_type == DataType.PALETTE]

    @property
    def filename(self):
        return self._filename

    @property
    def size(self):
        return self._size

    def scan_all(self, skip_valid_blocks=False):
        self.offsets.clear()
        f = self._f
        f.seek(0, os.SEEK_SET)
        offset = 0
        stream = f
        while offset < self._size:
            try:
                size = dryrun_lz77(
                    stream,
                    min_length=16,
                    max_length=600*400*2,
                )
            except ValueError:
                size = None
            except RuntimeError:
                logging.warning(f"{offset:08X}h skipped")
                size = None
            else:
                mem = MemoryMap(
                    byte_offset=offset,
                    byte_length=stream.tell() - offset,
                    byte_payload=size,
                    byte_codec=ByteCodec.LZ77,
                    data_type=DataType.IMAGE,
                )
                self.offsets.append(mem)
            if not skip_valid_blocks:
                offset += 1
                stream.seek(offset, os.SEEK_SET)
            else:
                if size is None:
                    offset += 1
                    stream.seek(offset, os.SEEK_SET)
                else:
                    offset += size

    def extract_raw(self, mem: MemoryMap) -> bytes:
        f = self._f
        f.seek(mem.byte_offset, os.SEEK_SET)
        data = f.read(mem.byte_length)
        return data

    def extract_lz77(self, mem: MemoryMap):
        f = self._f
        f.seek(mem.byte_offset, os.SEEK_SET)
        result = decompress_lz77(f)
        offset_end = f.tell()
        mem.byte_length = offset_end - mem.byte_offset
        return result

    def extract_data(self, mem: MemoryMap) -> numpy.ndarray:
        """
        Return data after byte codec decompression.

        FIXME: Return bytes instead.
        """
        if mem.byte_codec in [None, ByteCodec.RAW]:
            raw = self.extract_raw(mem)
            result = numpy.frombuffer(raw, dtype=numpy.uint8)
        elif mem.byte_codec == ByteCodec.LZ77:
            result = self.extract_lz77(mem)
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

        if mem.data_type != DataType.PALETTE:
            raise ValueError(f"Memory map 0x{mem.byte_offset:08X} is not a palette")

        size = mem.palette_size if mem.palette_size is not None else 16
        byte_per_color = 2

        if data.size % (size * byte_per_color) != 0:
            raise ValueError(f"Memory map 0x{mem.byte_offset:08X} don't have the right size")

        nb = data.size // (size * byte_per_color)
        data = convert_a1rgb15_to_argb32(data)
        data.shape = nb, -1, 4
        return data

    def guess_first_image_shape(self, nb_pixels) -> tuple[int, int]:
        if nb_pixels == 240 * 160:
            # LCD mode
            return 160, 240
        if nb_pixels == 160 * 128:
            # LCD mode
            return 128, 160
        # FIXME: Guess something closer to a square
        return 1, nb_pixels

    def image_shape(self, mem: MemoryMap) -> tuple[int, int] | None:
        """Only return the image shape.

        FIXME: Could probably be even more simplified.
        """
        if mem.data_type != DataType.IMAGE:
            return None

        if mem.byte_payload is None:
            if mem.byte_codec in [None, ByteCodec.RAW]:
                if mem.byte_length is None:
                    raise ValueError(f"Memory map 0x{mem.byte_offset:08X} have inconcistente description")
                size = mem.byte_length
            elif mem.byte_codec == ByteCodec.LZ77:
                f = self._f
                f.seek(mem.byte_offset, os.SEEK_SET)
                try:
                    size = dryrun_lz77(f)
                except Exception:
                    return None
            else:
                raise ValueError(f"Memory map 0x{mem.byte_offset:08X} have inconcistente description")
        else:
            size = mem.byte_payload

        if mem.image_color_mode == ImageColorMode.INDEXED_4BIT:
            size *= 2

        if mem.image_shape is not None:
            return mem.image_shape
        else:
            return self.guess_first_image_shape(size)

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

        if mem.image_color_mode == ImageColorMode.INDEXED_4BIT:
            data = convert_8bx1_to_4bx2(data)

        if mem.image_shape is not None:
            try:
                data.shape = mem.image_shape
            except Exception:
                data.shape = self.guess_first_image_shape(data.size)
        else:
            data.shape = self.guess_first_image_shape(data.size)

        if mem.image_pixel_order == ImagePixelOrder.TILED_8X8:
            if data.shape[0] % 8 != 0 or data.shape[1] % 8 != 0:
                raise ValueError(f"Memory map 0x{mem.byte_offset:08X} use incompatible option: shape {data.shape} can't used with tiled 8x8")
            data = convert_to_tiled_8x8(data)

        palette_data = None
        if mem.image_palette_offset is not None:
            try:
                palette_map = self.memory_map_from_offset(mem.image_palette_offset)
            except ValueError:
                logging.warning("Error while accessing palette memory map", exc_info=True)
                pass
            else:
                try:
                    palette_data = self.palette_data(palette_map)
                except ValueError:
                    logging.warning("Error while accessing palette data", exc_info=True)
                    pass

        if palette_data is not None:
            try:
                # FIXME: Implement index different than 0
                return palette_data[0][data]
            except Exception:
                logging.warning("Error while processing RGB data from palette", exc_info=True)
                pass

        return data

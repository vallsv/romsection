import enum
import typing
import dataclasses


class ByteCodec(enum.Enum):
    RAW = enum.auto()
    """Uncompressed memory"""

    LZ77 = enum.auto()
    """Compressed as LZ77"""


class DataTypeGroup(enum.Enum):
    IMAGE = enum.auto()
    PALETTE = enum.auto()
    TILE_SET = enum.auto()
    SAMPLE = enum.auto()
    MUSIC = enum.auto()
    OTHER = enum.auto()


@dataclasses.dataclass(frozen=True, eq=False)
class DataTypeDesc:
    group: DataTypeGroup


class DataType(enum.Enum):
    IMAGE = DataTypeDesc(group=DataTypeGroup.IMAGE)
    """Memory map which can be represented as a image."""

    PALETTE = DataTypeDesc(group=DataTypeGroup.PALETTE)
    """Memory map compound by a set of colors."""

    TILE_SET = DataTypeDesc(group=DataTypeGroup.TILE_SET)
    """
    Memory map compound by a set of tiles of the same size.

    The properties of the IMAGE are used, but are applied to a single tile.
    """

    SAMPLE_INT8 = DataTypeDesc(group=DataTypeGroup.SAMPLE)
    """Sample raw data encoded in int8."""

    SAMPLE_SAPPY = DataTypeDesc(group=DataTypeGroup.SAMPLE)
    """
    Sample as stored by sappy.

    See https://www.romhacking.net/documents/462/
    """

    MUSIC_INSTRUMENT_SAPPY = DataTypeDesc(group=DataTypeGroup.MUSIC)
    """
    Music instrument bank as stored by sappy

    See https://www.romhacking.net/documents/462/
    """

    UNKNOWN = DataTypeDesc(group=DataTypeGroup.OTHER)
    """Memory map which is not yet identified."""

    GBA_ROM_HEADER = DataTypeDesc(group=DataTypeGroup.OTHER)
    """
    Memory map containing GBA description.

    See http://problemkaputt.de/gbatek.htm#gbacartridgeheader
    """

    PADDING = DataTypeDesc(group=DataTypeGroup.OTHER)
    """
    Memory map which fill the memory with anything (usually 0) for
    better alignement of the next memory map.
    """


class ImageColorMode(enum.Enum):
    INDEXED_8BIT = enum.auto()
    """8 bits data displayed with a color from a palette"""

    INDEXED_4BIT = enum.auto()
    """4 bits data (2 pixels per byte) displayed with a color from a palette"""

    RGB15 = enum.auto()
    """16 bits true color (2 bytes per pixels).

    Each RGB component use a 5 bits depth.

    The remaining 16th bit is lost.
    """

    A1RGB15 = enum.auto()
    """
    16 bits true color (2 bytes per pixels) with alpha component.

    Each RGB components use a 5 bits depth.

    When alpha=0 -> transparent, when alpha=1 -> opaque.
    """


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

    @property
    def byte_end(self) -> int:
        return self.byte_offset + (self.byte_length or 0)

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

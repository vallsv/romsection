import typing
from PyQt5 import Qt

from .. model import DataTypeGroup, DataType


ICONS = {
    # DataTypeGroup
    DataTypeGroup.IMAGE: "icons:image.png",
    DataTypeGroup.PALETTE: "icons:palette.png",
    DataTypeGroup.TILE_SET: "icons:tileset.png",
    DataTypeGroup.SAMPLE: "icons:sample.png",
    DataTypeGroup.MUSIC: "icons:music.png",
    # DataType
    DataType.PADDING: "icons:padding.png",
    DataType.UNKNOWN: "icons:unknown.png",
    DataType.GBA_ROM_HEADER: "icons:gba.png",
    DataType.MUSIC_INSTRUMENT_SAPPY: "icons:instrument.png",
    DataType.MUSIC_KEY_SPLIT_TABLE_SAPPY: "icons:instrument.png",
}


def getIcon(obj: typing.Any) -> Qt.QIcon:
    name = ICONS.get(obj, None)
    if name is None:
        if isinstance(obj, DataType):
            name = ICONS.get(obj.value.group, None)
    if name is None:
        return Qt.QIcon("icons:empty.png")
    return Qt.QIcon(name)

import os
import io
import struct
from PyQt5 import Qt

from ..gba_file import GBAFile
from .behavior import Behavior
from ..format_utils import format_address
from ..model import MemoryMap, ByteCodec, DataType
from ..parsers import sappy_utils
from ..widgets.memory_map_list_model import MemoryMapListModel
from ..commands.extract_memorymap import ExtractMemoryMapCommand
from .common import BehaviorAtRomOffset
from .. import qt_utils


class SearchSappyTag(Behavior):
    """
    Search for sappy empty bank.

    See https://www.romhacking.net/documents/462/
    """
    def run(self):
        context = self.context()
        rom = context.rom()
        result = rom.search_for_bytes(0, rom.size, sappy_utils.UNUSED_INSTRUMENT)

        if result:
            offsets = [format_address(offset) for offset in result]
            string = ", ".join(offsets)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"The following offsets looks like SAPPY empty instrument bank:\n{string}"
            )
        else:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                "Nothing was found"
            )


class SearchContent(Behavior):
    NAME = "content"

    def __init__(self):
        Behavior.__init__(self)
        self.__data = None

    def setData(self, data: bytes):
        self.__data = data

    def setAddress(self, address: int):
        dataAddress = (address + 0x8000000).to_bytes(4, 'little')
        self.setData(dataAddress)

    def run(self):
        context = self.context()
        if self.__data is None:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                "No content selected"
            )
            return
        rom = context.rom()
        result = rom.search_for_bytes(0, rom.size, self.__data)

        if result:
            offsets = [format_address(offset) for offset in result]
            string = ", ".join(offsets)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"The following offsets looks to use this {self.NAME}:\n{string}"
            )
        else:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                "Nothing was found"
            )


class SearchInstrumentAddress(SearchContent):
    NAME = "SAPPY instrument address"


class SearchSongHeaderAddress(SearchContent):
    NAME = "SAPPY song header"


class SplitSappySample(BehaviorAtRomOffset):

    EXTRA_BYTE = 0

    def headerSize(self):
        return sappy_utils.SAMPLE_HEADER_SIZE

    def isValidHeader(self, data: bytes):
        header = sappy_utils.SampleHeader.parse(data)
        return header.is_valid()

    def createAction(self, parent: Qt.QObject) -> Qt.QAction:
        action = Qt.QAction(parent)
        action.setText("Extract sappy sample content")
        action.setIcon(Qt.QIcon("icons:sample.png"))
        action.triggered.connect(self.run)
        return action

    def run(self):
        context = self.context()
        rom = context.rom()

        mem = context.currentMemoryMap()
        if mem is None:
            return

        if mem.byte_codec not in (None, ByteCodec.RAW):
            return

        address = self.offset()
        if address is None:
            return

        headerMap = MemoryMap(
            byte_offset=address,
            byte_length=sappy_utils.SAMPLE_HEADER_SIZE,
            data_type=DataType.UNKNOWN,
        )
        data = rom.extract_raw(headerMap)

        with qt_utils.exceptionAsMessageBox(context.mainWidget()):
            header = sappy_utils.SampleHeader.parse(data)

            sampleMem = MemoryMap(
                byte_offset=address,
                byte_length=sappy_utils.SAMPLE_HEADER_SIZE + header.size + self.EXTRA_BYTE,
                byte_codec=ByteCodec.RAW,
                data_type=DataType.SAMPLE_SAPPY,
            )
            # FIXME: Have to be merged with the prevous one
            command = ExtractMemoryMapCommand()
            command.setCommand(mem, sampleMem)
            context.pushCommand(command)


class SplitSappySamplePlusOne(SplitSappySample):
    """
    Sounds like some games store the samples with an extra byte than
    the described size in the sample header.

    This is maybe related to a problem of interpolation in the
    mixer which allow to use data outside the sample location.
    """
    EXTRA_BYTE = 1

    def createAction(self, parent: Qt.QObject) -> Qt.QAction:
        action = Qt.QAction(parent)
        action.setText("Extract sappy sample content +1")
        action.setIcon(Qt.QIcon("icons:sample.png"))
        action.triggered.connect(self.run)
        return action


class SearchSappySongHeaderFromInstrument(Behavior):
    """
    Search for the address of an instrument table.

    An instrument table is linked from a Song header.

    See https://www.romhacking.net/documents/462/
    """
    def run(self):
        context = self.context()
        rom = context.rom()
        mem = context.currentMemoryMap()
        if mem is None:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "No selected memory map. A single Sappy instrument table have to be selected."
            )
            return

        if mem.data_type != DataType.MUSIC_INSTRUMENT_SAPPY:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected memory map is not a Sappy Instrument Sappy instrument table"
            )
            return

        ramAddress = mem.byte_offset + 0x8000000
        byteAddress = struct.pack("<L", ramAddress)
        result = rom.search_for_bytes(0, rom.size, byteAddress)

        if True:
            # Seach inside compressed data
            # That's maybe not needed
            memoryMapList = context.memoryMapList()
            for mem in memoryMapList:
                if mem.data_type != DataType.UNKNOWN:
                    continue
                if mem.byte_codec == ByteCodec.RAW:
                    continue
                result2 = rom.search_for_bytes_in_data(mem, byteAddress)
                if len(result2) != 0:
                    result.append(mem.byte_offset)

        if result:
            offsets = [format_address(offset) for offset in result]
            string = ", ".join(offsets)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"The following offsets looks to link this SAPPY instrument table:\n{string}"
            )
        else:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                "Nothing was found"
            )


def message_from_offsets(offsets: list[int]) -> str:
    if len(offsets) <= 4:
        foffsets = [format_address(offset) for offset in offsets]
        msg = ", ".join(foffsets)
    else:
        nb = len(offsets)
        foffsets = [format_address(offset) for offset in offsets[:4]]
        msg = ", ".join(foffsets) + f"... +{nb - 4}"
    return msg


class SearchSappySongHeadersFromSongTable(Behavior):
    """
    Search and extract SongHeader from SongAddress table.
    """
    def run(self):
        context = self.context()
        rom = context.rom()
        mem = context.currentMemoryMap()
        if mem is None:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "No selected memory map. A single Sappy song table have to be selected."
            )
            return

        if mem.data_type != DataType.MUSIC_SONG_TABLE_SAPPY:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected memory map is not a Sappy song table"
            )
            return

        data = rom.extract_data(mem)
        songHeaders = []
        while data:
            if len(data) < sappy_utils.SONG_TABLE_ITEM_SIZE:
                break
            itemData, data = data[:8], data[8:]
            item = sappy_utils.SongTableItem.parse(itemData)
            songHeaders.append(item.song_header_address)

        # Drop the dups
        songHeaders = set(songHeaders)
        songHeaders.discard(None)
        songHeaders = sorted([d - 0x8000000 for d in songHeaders])
        mems = {}
        already_extracted = 0
        to_be_extracted = 0
        cant_be_extracted = []
        for offset in songHeaders:
            mem = rom.memory_map_containing_offset(offset)
            if mem.data_type == DataType.MUSIC_SONG_HEADER_SAPPY and mem.byte_offset == offset:
                already_extracted += 1
                continue
            if mem.data_type != DataType.UNKNOWN or mem.byte_codec not in [None, ByteCodec.RAW]:
                cant_be_extracted.append(offset)
                continue
            to_be_extracted += 1
            mems.setdefault(mem.byte_offset, []).append(offset)

        if to_be_extracted == 0:
            if len(cant_be_extracted) == 0:
                Qt.QMessageBox.information(
                    context.mainWidget(),
                    "Result",
                    f"Every item found ({already_extracted}) was already extracted. Nothing was modified."
                )
            else:
                msg = message_from_offsets(cant_be_extracted)
                Qt.QMessageBox.information(
                    context.mainWidget(),
                    "Error",
                    f"Some items ({msg}) can't be extracted. Nothing was modified."
                )
            return

        invalid_header = []
        was_extracted = 0

        for _, songHeaders in mems.items():
            for songHeader in songHeaders:
                mem = rom.memory_map_containing_offset(songHeader)
                data = rom.extract_raw(mem)
                relAddress = songHeader - mem.byte_offset
                stream = io.BytesIO(data)
                stream.seek(relAddress, os.SEEK_SET)
                size = sappy_utils.SongHeader.parse_size(stream)
                if size is None:
                    invalid_header.append(songHeader)
                    continue

                newMem = MemoryMap(
                    byte_offset=songHeader,
                    byte_length=size,
                    byte_codec=ByteCodec.RAW,
                    data_type=DataType.MUSIC_SONG_HEADER_SAPPY,
                )

                # FIXME: Have to be merged with the prevous one
                command = ExtractMemoryMapCommand()
                command.setCommand(mem, newMem)
                context.pushCommand(command)
                was_extracted += 1

        if was_extracted:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"Some items ({was_extracted}) was extracted."
            )

        if cant_be_extracted:
            msg = message_from_offsets(cant_be_extracted)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                f"Some items can't be extracted because of the memory map description. See {msg}"
            )

        if invalid_header:
            msg = message_from_offsets(invalid_header)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                f"Some items can't be extracted because it was not possible to parse them. See {msg}"
            )


class SearchSappyTracksFromSongTable(Behavior):
    """
    Search and extract SongHeader from SongAddress table.
    """
    def run(self):
        context = self.context()
        rom = context.rom()
        mem = context.currentMemoryMap()
        if mem is None:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "No selected memory map. A single Sappy song table have to be selected."
            )
            return

        if mem.data_type != DataType.MUSIC_SONG_TABLE_SAPPY:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected memory map is not a Sappy song table."
            )
            return

        data = rom.extract_data(mem)
        songHeaders = []
        while data:
            if len(data) < sappy_utils.SONG_TABLE_ITEM_SIZE:
                break
            itemData, data = data[:8], data[8:]
            item = sappy_utils.SongTableItem.parse(itemData)
            songHeaders.append(item.song_header_address)

        # Drop the dups
        songHeaders = set(songHeaders)
        songHeaders.discard(None)
        songHeaders = sorted([d - 0x8000000 for d in songHeaders])
        trackOffsets = []
        for offset in songHeaders:
            try:
                mem = rom.memory_map_from_offset(offset)
            except ValueError:
                continue

            if mem.data_type != DataType.MUSIC_SONG_HEADER_SAPPY:
                continue

            data = rom.extract_raw(mem)
            songHeader = sappy_utils.SongHeader.parse(data)
            trackOffsets.extend(songHeader.track_data_addresses or [])

        # Remove dups
        trackOffsets = [d - 0x8000000 for d in trackOffsets]
        trackOffsets = sorted(list( set(trackOffsets)))

        invalid_description = []
        invalid_content = []
        was_extracted = 0

        for offset in trackOffsets:
            try:
                mem = rom.memory_map_containing_offset(offset)
            except ValueError:
                print(f"Offset {offset:08X}h not found")
                continue
            if mem.byte_offset == offset:
                if mem.data_type == DataType.MUSIC_TRACK_SAPPY:
                    continue
            if mem.data_type != DataType.UNKNOWN:
                invalid_description.append(offset)
                continue

            data = rom.extract_raw(mem)
            relOffset = offset - mem.byte_offset
            stream = io.BytesIO(data)
            stream.seek(relOffset, os.SEEK_SET)
            size = sappy_utils.Track.parse_size(stream)
            if size is None:
                invalid_content.append(offset)
                continue

            newMem = MemoryMap(
                byte_offset=offset,
                byte_length=size,
                byte_codec=ByteCodec.RAW,
                data_type=DataType.MUSIC_TRACK_SAPPY,
            )

            # FIXME: Have to be merged with the prevous one
            command = ExtractMemoryMapCommand()
            command.setCommand(mem, newMem)
            context.pushCommand(command)
            was_extracted += 1

        if was_extracted:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"Some items ({was_extracted}) was extracted."
            )

        if invalid_description:
            msg = message_from_offsets(invalid_description)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                f"Some items can't be extracted because of the memory map description. See {msg}"
            )

        if invalid_content:
            msg = message_from_offsets(invalid_content)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                f"Some items can't be extracted because it was not possible to parse them. See {msg}"
            )


class SearchSappyKeySplitTableFromInstrumentTable(Behavior):
    """
    Search and extract SongHeader from SongAddress table.
    """
    def run(self):
        context = self.context()
        rom = context.rom()
        mem = context.currentMemoryMap()
        if mem is None:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "No selected memory map. A single Sappy song table have to be selected."
            )
            return

        if mem.data_type != DataType.MUSIC_INSTRUMENT_SAPPY:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected memory map is not a Sappy instrument table"
            )
            return

        data = rom.extract_data(mem)
        keySplitTableAddress = []
        item_size = sappy_utils.INSTRUMENT_TABLE_ITEM_SIZE
        while data:
            if len(data) < item_size:
                break
            itemData, data = data[:item_size], data[item_size:]
            item = sappy_utils.InstrumentItem.parse(itemData)
            if not isinstance(item, sappy_utils.InstrumentKeySplitItem):
                continue
            keySplitTableAddress.append(item.key_split_table_address)

        # Drop the dups
        keySplitTableAddress = set(keySplitTableAddress)
        keySplitTableAddress = sorted([d - 0x8000000 for d in keySplitTableAddress])

        mems = {}
        already_extracted = 0
        to_be_extracted = 0
        cant_be_extracted = []
        for offset in keySplitTableAddress:
            mem = rom.memory_map_containing_offset(offset)
            if mem.data_type == DataType.MUSIC_KEY_SPLIT_TABLE_SAPPY and mem.byte_offset == offset:
                already_extracted += 1
                continue
            if mem.data_type != DataType.UNKNOWN or mem.byte_codec not in [None, ByteCodec.RAW]:
                cant_be_extracted.append(offset)
                continue
            to_be_extracted += 1
            mems.setdefault(mem.byte_offset, []).append(offset)

        if to_be_extracted == 0:
            if len(cant_be_extracted) == 0:
                Qt.QMessageBox.information(
                    context.mainWidget(),
                    "Result",
                    f"Every item found ({already_extracted}) was already extracted. Nothing was modified."
                )
            else:
                msg = message_from_offsets(cant_be_extracted)
                Qt.QMessageBox.information(
                    context.mainWidget(),
                    "Error",
                    f"Some items ({msg}) can't be extracted. Nothing was modified."
                )
            return

        invalid_header = []
        was_extracted = 0

        for _, memOffsets in mems.items():
            for memOffset in memOffsets:
                mem = rom.memory_map_containing_offset(memOffset)
                data = rom.extract_raw(mem)
                relAddress = memOffset - mem.byte_offset
                stream = io.BytesIO(data)
                stream.seek(relAddress, os.SEEK_SET)
                if len(stream.read(128)) != 128:
                    invalid_header.append(memOffset)
                    continue

                newMem = MemoryMap(
                    byte_offset=memOffset,
                    byte_length=128,
                    byte_codec=ByteCodec.RAW,
                    data_type=DataType.MUSIC_KEY_SPLIT_TABLE_SAPPY,
                )

                # FIXME: Have to be merged with the prevous one
                command = ExtractMemoryMapCommand()
                command.setCommand(mem, newMem)
                context.pushCommand(command)
                was_extracted += 1

        if was_extracted:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"Some items ({was_extracted}) was extracted."
            )

        if cant_be_extracted:
            msg = message_from_offsets(cant_be_extracted)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                f"Some items can't be extracted because of the memory map description. See {msg}"
            )

        if invalid_header:
            msg = message_from_offsets(invalid_header)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                f"Some items can't be extracted because it was not possible to parse them. See {msg}"
            )


class SearchSappySampleFromInstrumentTable(Behavior):
    """
    Search and extract SongHeader from SongAddress table.
    """
    def run(self):
        context = self.context()
        rom = context.rom()
        mem = context.currentMemoryMap()
        if mem is None:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "No selected memory map. A single Sappy song table have to be selected."
            )
            return

        if mem.data_type != DataType.MUSIC_INSTRUMENT_SAPPY:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                "The selected memory map is not a Sappy instrument table"
            )
            return

        data = rom.extract_data(mem)
        sampleAddress = []
        item_size = sappy_utils.INSTRUMENT_TABLE_ITEM_SIZE
        while data:
            if len(data) < item_size:
                break
            itemData, data = data[:item_size], data[item_size:]
            item = sappy_utils.InstrumentItem.parse(itemData)
            if not isinstance(item, sappy_utils.InstrumentSampleItem):
                continue
            sampleAddress.append(item.sample_address)

        # Drop the dups
        sampleAddress = set(sampleAddress)
        sampleAddress = sorted([d - 0x8000000 for d in sampleAddress])

        mems = {}
        already_extracted = 0
        to_be_extracted = 0
        cant_be_extracted = []
        for offset in sampleAddress:
            mem = rom.memory_map_containing_offset(offset)
            if mem.data_type == DataType.SAMPLE_SAPPY and mem.byte_offset == offset:
                already_extracted += 1
                continue
            if mem.data_type != DataType.UNKNOWN or mem.byte_codec not in [None, ByteCodec.RAW]:
                cant_be_extracted.append(offset)
                continue
            to_be_extracted += 1
            mems.setdefault(mem.byte_offset, []).append(offset)

        if to_be_extracted == 0:
            if len(cant_be_extracted) == 0:
                Qt.QMessageBox.information(
                    context.mainWidget(),
                    "Result",
                    f"Every item found ({already_extracted}) was already extracted. Nothing was modified."
                )
            else:
                msg = message_from_offsets(cant_be_extracted)
                Qt.QMessageBox.information(
                    context.mainWidget(),
                    "Error",
                    f"Some items ({msg}) can't be extracted. Nothing was modified."
                )
            return

        invalid_header = []
        was_extracted = 0

        headerSize = sappy_utils.SAMPLE_HEADER_SIZE
        for _, memOffsets in mems.items():
            for memOffset in memOffsets:
                mem = rom.memory_map_containing_offset(memOffset)
                data = rom.extract_raw(mem)
                relAddress = memOffset - mem.byte_offset
                stream = io.BytesIO(data)
                stream.seek(relAddress, os.SEEK_SET)
                headerData = stream.read(headerSize)
                header = sappy_utils.SampleHeader.parse(headerData)
                header = sappy_utils.SampleHeader.parse(headerData)
                if not header.is_valid():
                    invalid_header.append(memOffset)
                    continue

                newMem = MemoryMap(
                    byte_offset=memOffset,
                    byte_length=16 + header.size + 1,  # Sounds like +1 is mandatory
                    byte_codec=ByteCodec.RAW,
                    data_type=DataType.SAMPLE_SAPPY,
                )

                # FIXME: Have to be merged with the previous one
                command = ExtractMemoryMapCommand()
                command.setCommand(mem, newMem)
                context.pushCommand(command)
                was_extracted += 1

        if was_extracted:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"Some items ({was_extracted}) was extracted."
            )

        if cant_be_extracted:
            msg = message_from_offsets(cant_be_extracted)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                f"Some items can't be extracted because of the memory map description. See {msg}"
            )

        if invalid_header:
            msg = message_from_offsets(invalid_header)
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Error",
                f"Some items can't be extracted because it was not possible to parse them. See {msg}"
            )

import struct
from PyQt5 import Qt

from ..gba_file import GBAFile
from .behavior import Behavior
from ..format_utils import format_address
from ..model import MemoryMap, ByteCodec, DataType
from .. import sappy_utils


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
                context,
                "Result",
                f"The following offsets looks like SAPPY empty instrument bank:\n{string}"
            )
        else:
            Qt.QMessageBox.information(
                context,
                "Result",
                "Nothing was found"
            )


class SplitSappySample(Behavior):

    def setOffset(self, offset: int):
        self.__offset = offset

    def run(self):
        context = self.context()
        rom = context.rom()

        mem = context._memView.selectedMemoryMap()
        if mem is None:
            return

        if mem.byte_codec not in (None, ByteCodec.RAW):
            return

        address = self.__offset
        if address is None:
            return

        header = MemoryMap(
            byte_offset=address,
            byte_length=16,
            data_type=DataType.UNKNOWN,
        )
        data = rom.extract_data(header)

        zero1, zero2, zero3, kind, pitch, start, size = struct.unpack("<BBBBLLL", data)
        if zero1 != 0 or zero2 != 0 or zero3 != 0 or kind not in (0x00, 0x40):
            return

        prevMem = MemoryMap(
            byte_offset=mem.byte_offset,
            byte_length=address - mem.byte_offset,
            byte_codec=ByteCodec.RAW,
            data_type=DataType.UNKNOWN,
        )

        selectedMem = MemoryMap(
            byte_offset=address,
            byte_length=16 + size + 1,  # Sounds like +1 is mandatory
            byte_codec=ByteCodec.RAW,
            data_type=DataType.SAMPLE_SAPPY,
        )

        nextMem = MemoryMap(
            byte_offset=selectedMem.byte_end,
            byte_length=mem.byte_length - prevMem.byte_length - selectedMem.byte_length,
            byte_codec=ByteCodec.RAW,
            data_type=DataType.UNKNOWN,
        )

        if nextMem.byte_length < 0:
            print("Negative")
            return

        if mem.byte_end != nextMem.byte_end:
            print("Mismatch")
            return

        memoryMapList = context.memoryMapList()
        index = memoryMapList.objectIndex(mem).row()
        memoryMapList.removeObject(mem)
        if prevMem.byte_length != 0:
            memoryMapList.insertObject(index, prevMem)
            index += 1
        memoryMapList.insertObject(index, selectedMem)
        index += 1
        if nextMem.byte_length != 0:
            memoryMapList.insertObject(index, nextMem)


class SearchSappySongHeaderFromInstrument(Behavior):
    """
    Search for the address of an instrument table.

    An instrument table is linked from a Song header.

    See https://www.romhacking.net/documents/462/
    """
    def run(self):
        context = self.context()
        rom = context.rom()
        mem = context._memView.selectedMemoryMap()
        if mem is None:
            Qt.QMessageBox.information(
                context,
                "Error",
                "No selected memory map. A single Sappy instrument table have to be selected."
            )
            return

        if mem.data_type != DataType.MUSIC_INSTRUMENT_SAPPY:
            Qt.QMessageBox.information(
                context,
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
                context,
                "Result",
                f"The following offsets looks to link this SAPPY instrument table:\n{string}"
            )
        else:
            Qt.QMessageBox.information(
                context,
                "Result",
                "Nothing was found"
            )

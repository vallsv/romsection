import struct
from PyQt5 import Qt

from ..gba_file import GBAFile
from .behavior import Behavior
from ..format_utils import format_address
from ..model import MemoryMap, ByteCodec, DataType


class SearchSappyTag(Behavior):
    """
    Search for sappy empty bank.

    See https://www.romhacking.net/documents/462/
    """
    def run(self):
        unused_instrument = b"\x01\x3c\x00\x00\x02\x00\x00\x00\x00\x00\x0f\x00"
        context = self.context()
        rom = context.rom()
        result = rom.search_for_bytes(0, rom.size, unused_instrument)

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
    def run(self):
        context = self.context()
        rom = context.rom()

        mem = context._memView.selectedMemoryMap()
        if mem is None:
            return

        if mem.byte_codec not in (None, ByteCodec.RAW):
            return

        address = context._hexa.selectedAddress()
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
            data_type=DataType.SAMPLE,
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

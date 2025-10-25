from PyQt5 import Qt
from ..gba_file import GBAFile
from .behavior import Behavior
from ..qt_utils import exceptionAsMessageBox
from ..model import MemoryMap, ByteCodec, DataType
from ..commands.remove_memorymap import RemoveMemoryMapCommand
from ..commands.update_memorymap import UpdateMemoryMapCommand
from ..commands.insert_memorymap import InsertMemoryMapCommand


class CreateUncoveredMemory(Behavior):
    """
    Create unknown memory map on uncovered memory.
    """
    def run(self):
        Qt.QGuiApplication.setOverrideCursor(Qt.QCursor(Qt.Qt.WaitCursor))
        found = 0
        context = self.context()
        rom = context.rom()
        memoryMapList = context.memoryMapList()
        try:
            with exceptionAsMessageBox(context.mainWidget()):

                offsets = list(rom.offsets)
                # offsets = sorted(offsets, keys=lambda v: v.byte_offset)
                mem_end = MemoryMap(
                    byte_offset=rom.size,
                    byte_length=1,
                    data_type=DataType.UNKNOWN,
                )
                offsets.append(mem_end)

                current_offset = 0
                index = 0
                for offset in offsets:
                    if offset.byte_offset < current_offset:
                        index += 1
                        continue
                    if current_offset != offset.byte_offset:
                        length = offset.byte_offset - current_offset
                        mem = MemoryMap(
                            byte_offset=current_offset,
                            byte_length=length,
                            byte_codec=ByteCodec.RAW,
                            data_type=DataType.UNKNOWN,
                        )
                        # FIXME: Have to be merged to the previous command
                        command = InsertMemoryMapCommand()
                        command.setCommand(index, mem)
                        context.pushCommand(command)
                        index += 1
                        found += 1
                    index += 1
                    current_offset = offset.byte_offset + (offset.byte_length or 1)
        finally:
            Qt.QGuiApplication.restoreOverrideCursor()

        if found:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"{found} memory maps were created"
            )
        else:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                "Nothing was modified"
            )


class ReplaceUnknownByPadding(Behavior):
    """
    Search and replace unknwn portions by padding when it's small and filled by zero
    """
    def run(self):
        Qt.QGuiApplication.setOverrideCursor(Qt.QCursor(Qt.Qt.WaitCursor))
        found = 0
        context = self.context()
        rom = context.rom()
        memoryMapList = context.memoryMapList()
        try:
            with exceptionAsMessageBox(context.mainWidget()):
                for mem in memoryMapList:
                    if mem.data_type != DataType.UNKNOWN:
                        continue
                    if mem.byte_codec not in (None, ByteCodec.RAW):
                        continue
                    if mem.byte_length > 3:
                        continue
                    data = rom.extract_raw(mem)
                    if data.count(b"\x00") != mem.byte_length:
                        continue
                    # FIXME: We could chech adress alignement
                    #        but i feel like sometimes there is
                    #        surprisingly unaligned padding
                    newMem = mem.replace(data_type=DataType.PADDING)
                    # FIXME: Have to be merged to the previous command
                    command = UpdateMemoryMapCommand()
                    command.setCommand(mem, newMem)
                    context.pushCommand(command)
                    found += 1
        finally:
            Qt.QGuiApplication.restoreOverrideCursor()

        if found:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"{found} memory maps were fixed"
            )
        else:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                "Nothing was modified"
            )


class RemoveUnknown(Behavior):
    """
    Search and remove unknown memory map, if still tagged as RAW
    """
    def run(self):
        Qt.QGuiApplication.setOverrideCursor(Qt.QCursor(Qt.Qt.WaitCursor))
        found = 0
        context = self.context()
        rom = context.rom()
        memoryMapList = context.memoryMapList()
        try:
            with exceptionAsMessageBox(context.mainWidget()):
                for mem in reversed(memoryMapList):
                    if mem.byte_codec != ByteCodec.RAW:
                        continue
                    if mem.data_type != DataType.UNKNOWN:
                        continue

                    # FIXME: Have to be merged to the previous one
                    command = RemoveMemoryMapCommand()
                    command.setCommand(mem)
                    context.pushCommand(command)
                    found += 1
        finally:
            Qt.QGuiApplication.restoreOverrideCursor()

        if found:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                f"{found} memory maps were removed"
            )
        else:
            Qt.QMessageBox.information(
                context.mainWidget(),
                "Result",
                "Nothing was modified"
            )

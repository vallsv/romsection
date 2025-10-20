from ..model import MemoryMap, ByteCodec, DataType
from ..widgets.memory_map_list_model import MemoryMapListModel


def splitMemoryMap(memoryMapList: MemoryMapListModel, mem: MemoryMap, newMem: MemoryMap):
    prevMem = MemoryMap(
        byte_offset=mem.byte_offset,
        byte_length=newMem.byte_offset - mem.byte_offset,
        byte_codec=ByteCodec.RAW,
        data_type=DataType.UNKNOWN,
    )

    nextMem = MemoryMap(
        byte_offset=newMem.byte_end,
        byte_length=mem.byte_length - prevMem.byte_length - newMem.byte_length,
        byte_codec=ByteCodec.RAW,
        data_type=DataType.UNKNOWN,
    )

    if prevMem.byte_length < 0:
        raise RuntimeError("Inconsistencies in memory map creation")

    if nextMem.byte_length < 0:
        raise RuntimeError("Inconsistencies in memory map creation")

    if mem.byte_end != nextMem.byte_end:
        raise RuntimeError("Inconsistencies in memory map creation")

    index = memoryMapList.objectIndex(mem).row()
    memoryMapList.removeObject(mem)

    if prevMem.byte_length != 0:
        memoryMapList.insertObject(index, prevMem)
        index += 1
    memoryMapList.insertObject(index, newMem)
    index += 1
    if nextMem.byte_length != 0:
        memoryMapList.insertObject(index, nextMem)

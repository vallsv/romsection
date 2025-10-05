import struct
import typing

"""
Sappy referes to a sound engine that is used by a lot of Game Boy Advance games.

This module contains helpers to handle related data.

See https://www.romhacking.net/documents/462/
"""

UNUSED_INSTRUMENT = b"\x01\x3c\x00\x00\x02\x00\x00\x00\x00\x00\x0f\x00"

class Sample(typing.NamedTuple):
    zero1: int
    zero2: int
    zero3: int
    flags: int
    pitch: int
    start: int
    size: int

    def is_valid(self) -> bool:
        if self.zero1 != 0 or self.zero2 != 0 or self.zero3 != 0:
            return False
        if self.flags not in (0x00, 0x40):
            return False
        return True

    @property
    def loop(self) -> bool:
        return self.flags & 0x40 != 0

    @staticmethod
    def parse(data: bytes) -> "Sample":
        res = struct.unpack("<BBBBLLL", data)
        return Sample._make(res)

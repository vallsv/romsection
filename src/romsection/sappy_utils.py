import struct
import typing

"""
Sappy referes to a sound engine that is used by a lot of Game Boy Advance games.

This module contains helpers to handle related data.

See https://www.romhacking.net/documents/462/
"""

UNUSED_INSTRUMENT = b"\x01\x3c\x00\x00\x02\x00\x00\x00\x00\x00\x0f\x00"


class InstrumentSample(typing.NamedTuple):
    kind: int
    key: int
    unused: int
    panning: int
    sample_address: int
    attack: int
    decay: int
    sustain: int
    release: int

    @property
    def short_description(self):
        return "Sample (GBA Direct Sound channel)"

    @staticmethod
    def parse(data: bytes) -> "InstrumentSample":
        res = struct.unpack("<BBBBLBBBB", data)
        return InstrumentSample._make(res)


class InstrumentPsg(typing.NamedTuple):
    channel: int
    key: int
    timelength: int
    sweep: int
    data: int
    attack : int
    decay : int
    sustain : int
    release : int

    @property
    def short_description(self):
        return "PSG instrument / sub-instrument"

    @staticmethod
    def parse(data: bytes) -> "InstrumentSample":
        res = struct.unpack("<BBBBLBBBB", data)
        return InstrumentSample._make(res)


class InstrumentKeySplit(typing.NamedTuple):
    kind: int
    zero1: int
    zero2: int
    zero3: int
    first_instrument_address: int
    key_split_table_address: int

    @property
    def short_description(self):
        return "Key-Split instruments"

    @staticmethod
    def parse(data: bytes) -> "InstrumentKeySplit":
        res = struct.unpack("<BBBBLL", data)
        return InstrumentKeySplit._make(res)


class InstrumentEveryKeySplit(typing.NamedTuple):
    kind: int
    zero1: int
    zero2: int
    zero3: int
    percussion_table_address: int
    zero4: int

    @property
    def short_description(self):
        return "Every Key Split (percussion) instrument"

    @staticmethod
    def parse(data: bytes) -> "InstrumentEveryKeySplit":
        res = struct.unpack("<BBBBLL", data)
        return InstrumentEveryKeySplit._make(res)


class InstrumentUnused(typing.NamedTuple):
    data: bytes

    @property
    def short_description(self):
        return "Unused instrument"


class InstrumentInvalid(typing.NamedTuple):
    kind: int
    data: bytes

    @property
    def short_description(self):
        return "Invalid instrument"


class Instrument(typing.NamedTuple):

    @staticmethod
    def parse(data: bytes) -> InstrumentSample | InstrumentPsg | InstrumentKeySplit | InstrumentEveryKeySplit | InstrumentUnused | InstrumentInvalid:
        if data == UNUSED_INSTRUMENT:
            return InstrumentUnused(data)
        kind = data[0]
        if kind in (0x00, 0x08,  0x10, 0x20):
            return InstrumentSample.parse(data)
        if kind == (0x01, 0x02, 0x03, 0x04, 0x09, 0x0A, 0x0B, 0x0C):
            return InstrumentPsg.parse(data)
        if kind == 0x40:
            return InstrumentKeySplit.parse(data)
        if kind == 0x80:
            return InstrumentEveryKeySplit.parse(data)
        return InstrumentInvalid(kind, data[1:])


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

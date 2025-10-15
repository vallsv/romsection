import io
import numpy
import struct
import typing

"""
Sappy referes to a sound engine that is used by a lot of Game Boy Advance games.

This module contains helpers to handle related data.

See https://www.romhacking.net/documents/462/
"""

UNUSED_INSTRUMENT = b"\x01\x3c\x00\x00\x02\x00\x00\x00\x00\x00\x0f\x00"


def _as_struct(data: bytes, description: list[tuple[int, str]]) -> list[tuple[int, bytes, str]]:
    pos = 0
    result: list[tuple[int, bytes, str]] = []
    for desc in description:
        d = data[pos:pos + desc[0]]
        result.append((pos, d, desc[1]))
        pos += desc[0]
    return result


INSTRUMENT_TABLE_ITEM_SIZE = 12


class InstrumentSampleItem(typing.NamedTuple):
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
    def parse(data: bytes) -> "InstrumentSampleItem":
        res = struct.unpack("<BBBBLBBBB", data)
        return InstrumentSampleItem._make(res)

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        obj = struct.unpack("<BBBBLBBBB", data)
        description = [
            (1, "Sample instrument (GBA Direct Sound channel)"),
            (1, f"Key: {obj[1]}"),
            (1, f"Unused: {obj[2]}"),
            (1, f"Panning: {obj[3]}"),
            (4, f"Sample address: {obj[4] - 0x8000000:08X}h"),
            (1, f"Attack: {obj[5]}"),
            (1, f"Decay: {obj[6]}"),
            (1, f"Systain: {obj[7]}"),
            (1, f"Release: {obj[8]}"),
        ]
        return _as_struct(data, description)


class InstrumentPsgItem(typing.NamedTuple):
    channel: int
    key: int
    timelength: int
    sweep: int
    data: int
    attack: int
    decay: int
    sustain: int
    release: int

    @property
    def short_description(self):
        return "PSG instrument / sub-instrument"

    @staticmethod
    def parse(data: bytes) -> "InstrumentPsgItem":
        res = struct.unpack("<BBBBLBBBB", data)
        return InstrumentPsgItem._make(res)

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        obj = struct.unpack("<BBBBLBBBB", data)
        description = [
            (1, "PSG instrument / sub-instrument"),
            (0, f"Channel: {obj[0]}"),
            (1, f"Key: {obj[1]}"),
            (1, f"Timelength: {obj[2]}"),
            (1, f"Sweep: {obj[3]}"),
            (4, f"Data: {obj[4]:08X}h"),
            (1, f"Attack: {obj[5]}"),
            (1, f"Decay: {obj[6]}"),
            (1, f"Sustain: {obj[7]}"),
            (1, f"Release: {obj[8]}"),
        ]
        return _as_struct(data, description)


class InstrumentKeySplitItem(typing.NamedTuple):
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
    def parse(data: bytes) -> "InstrumentKeySplitItem":
        res = struct.unpack("<BBBBLL", data)
        return InstrumentKeySplitItem._make(res)

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        obj = struct.unpack("<BBBBLL", data)
        description = [
            (1, "Key-Split instruments"),
            (1, f"Unused: should be 00"),
            (1, f"Unused: should be 00"),
            (1, f"Unused: should be 00"),
            (4, f"First instrument address: {obj[4] - 0x8000000:08X}h"),
            (4, f"Key split table address: {obj[5] - 0x8000000:08X}h"),
        ]
        return _as_struct(data, description)


class InstrumentEveryKeySplitItem(typing.NamedTuple):
    kind: int
    zero1: int
    zero2: int
    zero3: int
    percussion_table_address: int
    zero4: int

    @property
    def short_description(self):
        return "Every Key Split instrument (percussion)"

    @staticmethod
    def parse(data: bytes) -> "InstrumentEveryKeySplitItem":
        res = struct.unpack("<BBBBLL", data)
        return InstrumentEveryKeySplitItem._make(res)

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        obj = struct.unpack("<BBBBLL", data)
        description = [
            (1, "Every Key Split instrument (percussion)"),
            (1, f"Unused: should be 00"),
            (1, f"Unused: should be 00"),
            (1, f"Unused: should be 00"),
            (4, f"Percussion table address: {obj[4] - 0x8000000:08X}h"),
            (1, f"Unused: should be 00"),
        ]
        return _as_struct(data, description)


class InstrumentUnusedItem(typing.NamedTuple):
    data: bytes

    @property
    def short_description(self):
        return "Unused instrument"

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        description = [
            (8, "Unused instrument"),
        ]
        return _as_struct(data, description)

class InstrumentInvalidItem(typing.NamedTuple):
    kind: int
    data: bytes

    @property
    def short_description(self):
        return "Invalid instrument"

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        description = [
            (len(data), "Invalid instrument"),
        ]
        return _as_struct(data, description)


class InstrumentItem(typing.NamedTuple):

    @staticmethod
    def parse(data: bytes) -> InstrumentSampleItem | InstrumentPsgItem | InstrumentKeySplitItem | InstrumentEveryKeySplitItem | InstrumentUnusedItem | InstrumentInvalidItem:
        if data == UNUSED_INSTRUMENT:
            return InstrumentUnusedItem(data)
        kind = data[0]
        if kind in (0x00, 0x08,  0x10, 0x20):
            return InstrumentSampleItem.parse(data)
        if kind in (0x01, 0x02, 0x03, 0x04, 0x09, 0x0A, 0x0B, 0x0C):
            return InstrumentPsgItem.parse(data)
        if kind == 0x40:
            return InstrumentKeySplitItem.parse(data)
        if kind == 0x80:
            return InstrumentEveryKeySplitItem.parse(data)
        return InstrumentInvalidItem(kind, data[1:])

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        if data == UNUSED_INSTRUMENT:
            return InstrumentUnusedItem.parse_struct(data)
        kind = data[0]
        if kind in (0x00, 0x08,  0x10, 0x20):
            return InstrumentSampleItem.parse_struct(data)
        if kind in (0x01, 0x02, 0x03, 0x04, 0x09, 0x0A, 0x0B, 0x0C):
            return InstrumentPsgItem.parse_struct(data)
        if kind == 0x40:
            return InstrumentKeySplitItem.parse_struct(data)
        if kind == 0x80:
            return InstrumentEveryKeySplitItem.parse_struct(data)
        return InstrumentInvalidItem.parse_struct(data)


SAMPLE_HEADER_SIZE = 16


class SampleHeader(typing.NamedTuple):
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
    def parse(data: bytes) -> "SampleHeader":
        res = struct.unpack("<BBBBLLL", data)
        return SampleHeader._make(res)

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        obj = struct.unpack("<BBBBLLL", data)
        description = [
            (1, f"Unused: should be 00"),
            (1, f"Unused: should be 00"),
            (1, f"Unused: should be 00"),
            (1, f"Flags: {obj[3]:b}"),
            (4, f"Pitch: {obj[4]}"),
            (4, f"Start: {obj[5]}"),
            (4, f"Size: {obj[6]}"),
        ]
        return _as_struct(data, description)


SONG_TABLE_ITEM_SIZE = 8


class SongTableItem(typing.NamedTuple):
    song_header_address: int
    track_group: int
    zero1: int
    track_group2: int
    zero2: int

    def is_valid(self) -> bool:
        if self.zero1 != 0 or self.zero2 != 0:
            return False
        if self.track_group != self.track_group2:
            return False
        return True

    @property
    def short_description(self):
        if not self.is_valid():
           return "Invalid song address"
        address = self.song_header_address - 0x08000000
        return f"Song header: {address:08X}h; track group: {self.track_group}"

    @staticmethod
    def parse(data: bytes) -> "SongTableItem":
        res = struct.unpack("<LBBBB", data)
        return SongTableItem._make(res)

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        obj = struct.unpack("<LBBBB", data)
        description = [
            (4, f"Song header address: {obj[0] - 0x8000000:08X}h"),
            (1, f"Track group: {obj[1]}"),
            (1, f"Unused: should be 00"),
            (1, f"Track group (duplicated): {obj[3]}"),
            (1, f"Unused: should be 00"),
        ]
        return _as_struct(data, description)


class SongHeader(typing.NamedTuple):
    nb_tracks: int
    zero1: int
    priority: int
    flags: int
    instrument_address: int | None = None
    track_data_addresses: list[int] | None = None

    def is_valid(self) -> bool:
        if self.zero1 != 0:
            return False
        return True

    @property
    def short_description(self):
        if not self.is_valid():
           return "Invalid song header"
        empty = self.nb_tracks == 0 and self.priority == 0 and self.flags == 0
        if empty:
           return "Empty song header"

        if self.track_data_addresses is None:
           return "Empty song header"

        if len(self.track_data_addresses) != self.nb_tracks:
           return "Data does not match the required amount of track data addresses"

        instrument_address = self.instrument_address
        track_data_addresses = self.track_data_addresses
        track_data_address = (self.track_data_addresses[0] if len(self.track_data_addresses) else 0)

        def f_ram(mem: int | None) -> str:
            if mem is None:
                return "None"
            return f"{mem - 0x08000000:08X}h"

        return f"Instruments: {f_ram(instrument_address)}; 1st track: {f_ram(track_data_address)}"

    @staticmethod
    def parse(data: bytes) -> "SongHeader":
        if data == b"\x00\x00\x00\x00":
            return SongHeader(0, 0, 0, 0)
        res = struct.unpack("<BBBBL", data[:8])
        nb_tracks = res[0]

        max_parsable = len(data) - len(data) % 4
        track_data_addresses = [int(d) for d in numpy.frombuffer(data[8:max_parsable], dtype="<u4")]
        return SongHeader(
            res[0],
            res[1],
            res[2],
            res[3],
            res[4],
            track_data_addresses,
        )

    @staticmethod
    def parse_size(stream: io.IOBase) -> int | None:
        header = stream.read(4)
        if len(header) != 4:
            return None
        if header == b"\x00\x00\x00\x00":
            return 4

        instrument = stream.read(4)
        if len(instrument) != 4:
            return None

        nb_tracks = header[0]
        track = stream.read(4 * nb_tracks)
        if len(track) != 4 * nb_tracks:
            return None

        return 8 + 4 * nb_tracks

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        stream = io.BytesIO(data)
        result: list[tuple[int, bytes, str]] = []

        pos = stream.tell()
        nb_tracks = stream.read(1)
        result.append((pos, nb_tracks, f"Nb tracks: {nb_tracks[0]}"))

        pos = stream.tell()
        zero1 = stream.read(1)
        result.append((pos, zero1, f"Unused: should be 00"))

        pos = stream.tell()
        priority = stream.read(1)
        result.append((pos, priority, f"Priority: {priority[0]}"))

        pos = stream.tell()
        flags = stream.read(1)
        result.append((pos, flags, f"Flags: {flags[0]:b}"))

        pos = stream.tell()
        instrument_address = stream.read(4)
        if len(instrument_address) != 4:
            return result
        address = struct.unpack("<L", instrument_address)
        result.append((pos, instrument_address, f"Instrument address: {address[0] - 0x8000000:08X}h"))

        for nb in range(nb_tracks[0]):
            pos = stream.tell()
            track_data_address = stream.read(4)
            if len(track_data_address) != 4:
                return result
            address = struct.unpack("<L", track_data_address)
            result.append((pos, track_data_address, f"Track data address #{nb}: {address[0] - 0x8000000:08X}h"))

        return result


TRACK_COMMANDS = {
    0x80: (0, "Wait zero (NOP)"),
    0xB1: (0, "End of track"),
    0xB2: (4, "Jump to address"),
    0xB3: (4, "Call subsection"),
    0xB4: (0, "End subsection"),
    0xB5: (5, "Call and repeat subsection"),
    0xB9: (3, "Conditionnal jump"),
    0xBA: (1, "Set track priority"),
    0xBB: (1, "Set tempo"),
    0xBC: (1, "Transpose"),
    0xBD: (1, "Set instrument"),
    0xBE: (1, "Set volume"),
    0xBF: (1, "Set panning"),
    0xC0: (1, "Pitch bend value"),
    0xC1: (1, "Pitch bend range"),
    0xC2: (1, "Set LFO speed"),
    0xC3: (1, "Set LFO delay"),
    0xC4: (1, "Set LFO depth"),
    0xC5: (1, "Set LFO type"),
    0xC6: (0, "Unknown"),
    0xC7: (0, "Unknown"),
    0xC8: (1, "Set detune"),
    0xC9: (0, "Unknown"),
    0xCA: (0, "Unknown"),
    0xCB: (0, "Unknown"),
    0xCC: (0, "Unknown"),
    0xCD: (2, "Set pseudo echo"),
    0xCE: (-1, "Note off"),
    0xCF: (-1, "Note on"),
}


class Track(typing.NamedTuple):
    length: int
    terminated: bool

    @staticmethod
    def parse_size(stream: io.IOBase) -> int | None:
        start = stream.tell()
        while True:
            data = stream.read(1)
            if data == b"":
                return None
            cmd = data[0]
            if 0x00 <= cmd <= 0x7F:
                # Repeat the last command
                pass
            elif 0x81 <= cmd <= 0xB0:
                # Wait some time
                pass
            elif cmd == 0xB1:
                # End of track
                break
            elif 0xD0 <= cmd <= 0xFF:
                # Note on with auto time-out
                pass
            else:
                desc = TRACK_COMMANDS.get(cmd)
                if desc is not None:
                    # Call subsection
                    nb_args = desc[0]
                    if nb_args > 0:
                        address = stream.read(nb_args)
                        if len(address) != nb_args:
                            return None
        return stream.tell() - start

    @staticmethod
    def parse_struct(data: bytes) -> list[tuple[int, bytes, str]]:
        stream = io.BytesIO(data)
        result: list[tuple[int, bytes, str]] = []
        while True:
            pos = stream.tell()
            bcmd = stream.read(1)
            if bcmd == b"":
                return result
            cmd = bcmd[0]
            if 0x00 <= cmd <= 0x7F:
                result.append((pos, bcmd, "Repeat the last command"))
            elif 0x81 <= cmd <= 0xB0:
                result.append((pos, bcmd, "Wait some time"))
            elif cmd == 0xB1:
                result.append((pos, bcmd, "End of track"))
                break
            elif 0xD0 <= cmd <= 0xFF:
                result.append((pos, bcmd, "Note on with auto time-out"))
            else:
                desc = TRACK_COMMANDS.get(cmd)
                if desc is not None:
                    # Call subsection
                    nb_args = desc[0]
                    if nb_args > 0:
                        args = stream.read(nb_args)
                        result.append((pos, bcmd + args, desc[1]))
                        if len(args) != nb_args:
                            return result
        return result

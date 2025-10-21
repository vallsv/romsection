"""
GBA Run-length decoder.

.. code-block::

    Data header (32bit)
        Bit 0-3   Reserved
        Bit 4-7   Compressed type (must be 3 for run-length)
        Bit 8-31  Size of decompressed data
    Repeat below. Each Flag Byte followed by one or more Data Bytes.
    Flag data (8bit)
        Bit 0-6   Expanded Data Length (uncompressed N-1, compressed N-3)
        Bit 7     Flag (0=uncompressed, 1=compressed)
    Data Byte(s) - N uncompressed bytes, or 1 byte repeated N times

See https://problemkaputt.de/gbatek-bios-decompression-functions.htm
"""

import io
import os
import numpy


def _read_u8(stream: io.IOBase):
    v = stream.read(1)
    if len(v) == 0:
        raise ValueError("Not a valid GBA RL stream")
    return v[0]


def _read_u24_little(stream: io.IOBase):
    v = stream.read(3)
    if len(v) != 3:
        raise ValueError("Not a valid GBA RL stream")
    return int.from_bytes(v, byteorder='little', signed=False)


def _dry_read(stream: io.IOBase, size: int):
    stream.seek(size, os.SEEK_CUR)


def decompress(stream: io.IOBase) -> bytes:
    encoder = _read_u8(stream)
    if encoder != 0x30:
        raise ValueError("Not a valid GBA RL stream")
    size = _read_u24_little(stream)
    array = numpy.empty(size, numpy.uint8)
    n = 0
    while n < size:
        d = _read_u8(stream)
        compressed = (d & 0x80) != 0
        length = d & 0x7F
        if compressed:
            length += 3
            if n + length > size:
                raise ValueError("Not a valid GBA RL stream")
            d = _read_u8(stream)
            array[n:n + length] = d
            n += length
        else:
            length += 1
            if n + length > size:
                raise ValueError("Not a valid GBA RL stream")
            raw = stream.read(length)
            if len(raw) != length:
                raise ValueError("Not a valid GBA RL stream")
            raw_array = numpy.frombuffer(raw, numpy.uint8)
            array[n:n + length] = raw_array
            n += length

    return array.tobytes()


def dryrun(stream: io.IOBase) -> bytes:
    encoder = _read_u8(stream)
    if encoder != 0x30:
        raise ValueError("Not a valid GBA RL stream")
    size = _read_u24_little(stream)
    n = 0
    while n < size:
        d = _read_u8(stream)
        compressed = (d & 0x80) != 0
        length = d & 0x7F
        if compressed:
            length += 3
            if n + length > size:
                raise ValueError("Not a valid GBA RL stream")
            _dry_read(stream, 1)
            n += length
        else:
            length += 1
            if n + length > size:
                raise ValueError("Not a valid GBA RL stream")
            _dry_read(stream, length)
            n += length

    return size

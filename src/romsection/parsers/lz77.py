"""
Decompress LZ77 8-bits, as used by Game Boy Advanced ROMs.

It's a LZSS format, based on
- A slinding window of 4096 bytes
- A length compression between 3..18.

The format is compound by the following:

- header: 32 bits
   - magic: 8 bits = 0x10
   - decompressed length: 24bits
- n x block:
   - types: 8 bits
   - 8 x data:
      - one of:
          - new data:
              - data: 8 bits
          - data from decompressed data:
              - repeat: 4 bits
              - location: 12 bits

Resources:
- problemkaputt.de/gbatek.htm
- https://www.cs.rit.edu/~tjh8300/CowBite/CowBiteSpec.htm
- https://github.com/lunasorcery/gba-lz77
- https://github.com/TimoVesalainen/Nintenlord.Hacking

"""

import io
import os
import numpy
from collections.abc import Callable


def _read_u8(f):
    v = f.read(1)
    if len(v) == 0:
        raise ValueError("Not a valid GBA LZ77 stream")
    return v[0]


def _read_u24_little(f):
    v = f.read(3)
    return v[0] + (v[1] << 8) + (v[2] << 16)


def decompress(input_stream: io.RawIOBase) -> bytes:
    """Decompress a data stream into a memory array."""
    magic = _read_u8(input_stream)
    if magic != 0x10:
        raise ValueError("Not a valid GBA LZ77 stream")

    decompressed_length = _read_u24_little(input_stream)
    if decompressed_length == 0:
        raise ValueError("Not a valid GBA LZ77 stream")

    result = numpy.empty(decompressed_length, numpy.uint8)
    pos = 0
    while pos < decompressed_length:
        types = _read_u8(input_stream)
        for i in range(8):
            if pos > decompressed_length:
                raise ValueError("Not a valid GBA LZ77 stream")
            if pos == decompressed_length:
                break
            from_history = types & (0x80 >> i)
            if from_history == 0:
                result[pos] = _read_u8(input_stream)
                pos += 1
            else:
                value = input_stream.read(2)
                length = (value[0] >> 4) + 3
                location = 1 + value[1] + ((value[0] & 0xF) << 8)

                if pos + length > decompressed_length:
                    raise ValueError("Not a valid GBA LZ77 stream")

                while length > 0:
                    if location > pos:
                        cp = min(length, location - pos)
                        result[pos:pos + cp] = 0
                    else:
                        cp = min(length, location)
                        result[pos:pos + cp] = result[pos - location: pos - location + cp]
                    pos += cp
                    length -= cp
    return result.tobytes()


def dryrun(
    input_stream: io.RawIOBase,
    min_length: int | None = None,
    max_length: int | None = None,
    must_stop: Callable[[], bool] | None = None,
) -> int:
    """Decompress a data stream without extraction the result.

    It a faster way to check the validity and get the size of the block.
    """
    magic = _read_u8(input_stream)
    if magic != 0x10:
        raise ValueError("Not a valid GBA LZ77 stream")

    decompressed_length = _read_u24_little(input_stream)
    if decompressed_length == 0:
        raise ValueError("Not a valid GBA LZ77 stream")
    if max_length is not None and decompressed_length > max_length:
        raise RuntimeError(f"Found size of {decompressed_length}, which is bigger than the expected limits")
    if min_length is not None and decompressed_length < min_length:
        raise RuntimeError(f"Found size of {decompressed_length}, which is smaller than the expected limits")

    pos = 0
    while pos < decompressed_length:
        types = _read_u8(input_stream)
        for i in range(8):
            if pos > decompressed_length:
                raise ValueError("Not a valid GBA LZ77 stream")
            if pos == decompressed_length:
                break
            from_history = types & (0x80 >> i)
            if from_history == 0:
                input_stream.seek(1, os.SEEK_CUR)
                pos += 1
            else:
                value = input_stream.read(2)
                length = (value[0] >> 4) + 3

                if pos + length > decompressed_length:
                    raise ValueError("Not a valid GBA LZ77 stream")

                pos += length
        if must_stop is not None and must_stop():
            raise StopIteration
    if pos != decompressed_length:
        raise ValueError("Not a valid GBA LZ77 stream")
    return decompressed_length

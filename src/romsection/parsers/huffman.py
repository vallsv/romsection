"""
Decompress Huffman 4 and 8-bits, as used by Game Boy Advanced ROMs.

- Header
    - 4bits: Compressed type (must be 2 for Huffman)
    - 4bits: Data size in bit units (normally 4 or 8)
    - 24bits: Size of decompressed data in bytes
- Tree
    - 8bits: n -> size of table = (n+1) * 2
    - nodes:
        - 8bits: One of
            - node:
                - 7th bit: Left is data
                - 6th bit: Right is data
                - 6bits: offset to the next lelf+right child
            - data
- Data (stored in 32bits unit)
    - 31th bit is the first bit)  (0=R, 1=L)

Resources:
- https://www.cs.rit.edu/~tjh8300/CowBite/CowBiteSpec.htm
- https://github.com/BinarySerializer/BinarySerializer.Nintendo

"""

import io
import os
import numpy
from collections.abc import Callable


def _read_u8(f):
    v = f.read(1)
    if len(v) == 0:
        raise ValueError("Not a valid GBA huffman stream")
    return v[0]


def _read_u24_little(f):
    v = f.read(3)
    if len(v) != 3:
        raise ValueError("Not a valid GBA huffman stream")
    return v[0] + (v[1] << 8) + (v[2] << 16)


def decompress(input_stream: io.RawIOBase) -> bytes:
    """
    Decompress this input_stream into bytes.

    Raises:
        ValueError: If the stream does not contain a GBA huffman data
    """
    header = _read_u8(input_stream)

    encoding = (header & 0xF0) >> 4
    if encoding != 2:
        raise ValueError("Not a valid GBA huffman stream")

    data_depth = header & 0x0F

    if data_depth == 4:
        return decompress_4bits(input_stream)
    elif data_depth == 8:
        return decompress_8bits(input_stream)

    raise ValueError(f"Unsupported huffman {data_depth}bits data depth")


class _BitIO():
    """
    Bit stream based on u32 word little endian.

    The hightest bits are read first, as result,
    the 4th byte is read before the 1st byte.
    """
    def __init__(self, stream: io.IOBase):
        self._stream = stream
        self._mask = 0
        self._value = 0

    def read_bit(self) -> int:
        if self._mask == 0:
            d = self._stream.read(4)
            if len(d) != 4:
                raise IOError("End of stream")
            self._value = int.from_bytes(d, byteorder='little', signed=False)
            self._mask = 0x80000000
        res = int((self._value & self._mask) != 0)
        self._mask = self._mask // 2
        return res


def _read_tokens(tree_data: bytes) -> dict[bytes, int]:
    """Read the tokens from the binary tree"""
    stack = [(b"", 0, False)]
    tokens: dict[bytes, int] = {}

    nb_max = 256 * 4
    for key, index, is_data in stack:
        nb_max -= 1
        if nb_max < 0:
            raise ValueError("Not a valid GBA huffman stream: Loop detected")
        if index >= len(tree_data):
            break
        d = tree_data[index]
        if is_data:
            tokens[key] = d
        else:
            l_is_data = (d & 0x80) != 0
            r_is_data = (d & 0x40) != 0
            offset = d & 0x3F
            next_index = index + (index & 1) + 1 + offset * 2
            stack.append((key + b"0", next_index, l_is_data))
            stack.append((key + b"1", next_index + 1, r_is_data))
    return tokens


def _read_value(bit_stream, tokens: dict[bytes, int], max_key_size: int) -> int:
    key = b""
    for _ in range(max_key_size):
        bit = bit_stream.read_bit()
        key += b"%d" % bit
        d = tokens.get(key)
        if d is not None:
            return d
    else:
        raise ValueError("Not a valid GBA huffman stream")


def decompress_4bits(input_stream: io.RawIOBase) -> bytes:
    decompressed_size = _read_u24_little(input_stream)
    n = _read_u8(input_stream)
    tree_size = n * 2 + 1
    if tree_size > 256 * 2:
        raise ValueError("Not a valid GBA huffman stream")
    tree_data = input_stream.read(tree_size)
    if len(tree_data) != tree_size:
        raise ValueError("Not a valid GBA huffman stream")

    tokens = _read_tokens(tree_data)
    max_key_size = max((len(k) for k in tokens.keys()))

    result = numpy.empty(decompressed_size, dtype=numpy.uint8)
    bit_stream = _BitIO(input_stream)
    size = 0
    while size < decompressed_size:
        lo = _read_value(bit_stream, tokens, max_key_size)
        hi = _read_value(bit_stream, tokens, max_key_size)
        result[size] = (hi << 4) + lo
        size += 1

    return result.tobytes()


def decompress_8bits(input_stream: io.RawIOBase) -> bytes:
    decompressed_size = _read_u24_little(input_stream)
    n = _read_u8(input_stream)
    tree_size = n * 2 + 1
    if tree_size > 256 * 2:
        raise ValueError("Not a valid GBA huffman stream")
    tree_data = input_stream.read(tree_size)
    if len(tree_data) != tree_size:
        raise ValueError("Not a valid GBA huffman stream")

    # Read the tree
    tokens = _read_tokens(tree_data)
    max_key_size = max((len(k) for k in tokens.keys()))

    result = numpy.empty(decompressed_size, dtype=numpy.uint8)
    bit_stream = _BitIO(input_stream)
    size = 0
    while size < decompressed_size:
        v = _read_value(bit_stream, tokens, max_key_size)
        result[size] = v
        size += 1

    return result.tobytes()


def dryrun(
    input_stream: io.RawIOBase,
    min_length: int | None = None,
    max_length: int | None = None,
    must_stop: Callable[[], bool] | None = None,
) -> int:
    """
    Decompress this input_stream into bytes.

    Raises:
        ValueError: If the stream does not contain a GBA huffman data
    """
    header = _read_u8(input_stream)

    encoding = (header & 0xF0) >> 4
    if encoding != 2:
        raise ValueError("Not a valid GBA huffman stream")

    data_depth = header & 0x0F

    decompressed_length = _read_u24_little(input_stream)
    if max_length is not None and decompressed_length > max_length:
        raise RuntimeError(f"Found size of {decompressed_length}, which is bigger than the expected limits")
    if min_length is not None and decompressed_length < min_length:
        raise RuntimeError(f"Found size of {decompressed_length}, which is smaller than the expected limits")

    n = _read_u8(input_stream)
    tree_size = n * 2 + 1
    if tree_size > 256 * 2:
        raise ValueError("Not a valid GBA huffman stream")
    tree_data = input_stream.read(tree_size)
    if len(tree_data) != tree_size:
        raise ValueError("Not a valid GBA huffman stream")

    tokens = _read_tokens(tree_data)
    max_key_size = max((len(k) for k in tokens.keys()))

    bit_stream = _BitIO(input_stream)
    size = 0

    if data_depth == 4:
        while size < decompressed_length:
            _read_value(bit_stream, tokens, max_key_size)
            _read_value(bit_stream, tokens, max_key_size)
            size += 1
            if must_stop is not None and must_stop():
                raise StopIteration

        return decompressed_length

    elif data_depth == 8:
        while size < decompressed_length:
            _read_value(bit_stream, tokens, max_key_size)
            size += 1
            if must_stop is not None and must_stop():
                raise StopIteration

        return decompressed_length

    raise ValueError(f"Unsupported huffman {data_depth}bits data depth")

import io
import numpy
from romsection.parsers.lz77 import decompress, dryrun


def test_lz77():
    data = b"""\
\x10\x30\x00\x00\x08\x00\x00\x00\x00\x30\x03\x01\x01\x01\x4b\x01\x10\
\x06\x02\x02\x20\x08\x01\x10\x06\x20\x10\xc0\x30\x06\x40\x25"""
    result = decompress(io.BytesIO(data))
    assert result.size == 8 * 6
    result.shape = 6, 8
    expected = [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 1, 1, 1, 1, 0, 0],
        [0, 1, 2, 2, 1, 1, 1, 0],
        [0, 1, 2, 1, 1, 1, 1, 0],
        [0, 0, 1, 1, 1, 1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ]
    numpy.testing.assert_allclose(result, expected)
    assert dryrun(io.BytesIO(data)) == 8 * 6


def test_lz77_with_empty_window():
    """Compress data by using initial empty window (as 0 array)."""
    data = b"""\
\x10\x30\x00\x00\xb2\x70\x00\x01\x00\x00\x10\x06\x02\x02\x20\x08\x01\
\xf0\x10\x06\x20\x10\x30\x06\x40\x00\x00\x00"""
    result = decompress(io.BytesIO(data))
    assert result.size == 8 * 6
    result.shape = 6, 8
    expected = [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 1, 1, 1, 1, 0, 0],
        [0, 1, 2, 2, 1, 1, 1, 0],
        [0, 1, 2, 1, 1, 1, 1, 0],
        [0, 0, 1, 1, 1, 1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ]
    numpy.testing.assert_allclose(result, expected)
    assert dryrun(io.BytesIO(data)) == 8 * 6

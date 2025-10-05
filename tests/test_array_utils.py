import pytest
import numpy
from romsection.array_utils import convert_8bx1_to_4bx2, convert_to_tiled_8x8, convert_16bx1_to_5bx3
from romsection import array_utils


def test_convert_8bx1_to_4bx2():
    expected = numpy.array([0xB, 0xA, 0xD, 0xC])
    source = numpy.array([0xAB, 0xCD], dtype=numpy.uint8)
    result = convert_8bx1_to_4bx2(source)
    numpy.testing.assert_allclose(result, expected)


def test_convert_to_tiled_8x8():
    array = numpy.arange(64 * 4, dtype=numpy.uint8).reshape(-1, 16)
    result = convert_to_tiled_8x8(array)
    tile_64 = numpy.arange(64, dtype=numpy.uint8).reshape(8, 8)
    numpy.testing.assert_allclose(result[0:8, 0:8], tile_64)
    numpy.testing.assert_allclose(result[0:8, 8:16], tile_64 + 64)
    numpy.testing.assert_allclose(result[8:16, 0:8], tile_64 + 128)
    numpy.testing.assert_allclose(result[8:16, 8:16], tile_64 + 192)


def test_convert_16bx1_to_5bx3():
    expected = numpy.array([0x18, 0x1E, 0x1F], dtype=numpy.uint8)
    source = numpy.array([0b0111111111011000], numpy.uint16)
    result = convert_16bx1_to_5bx3(source)
    numpy.testing.assert_allclose(result, expected)


@pytest.mark.parametrize(
    "array,expected",
    (
        (
            numpy.array([0, 127, 255], dtype=numpy.uint8),
            numpy.array([0, 127, 255], dtype=numpy.uint8),
        ),
        (
            numpy.array([-128, 0, 127], dtype=numpy.int8),
            numpy.array([0, 128, 255], dtype=numpy.uint8),
        ),
        (
            numpy.array([0, 128 * 256, 255 * 256], dtype=numpy.uint16),
            numpy.array([0, 128, 255], dtype=numpy.uint8),
        ),
        (
            numpy.array([-128 * 256, 0, 127 * 256], dtype=numpy.int16),
            numpy.array([0, 128, 255], dtype=numpy.uint8),
        ),
    ),
)
def test_translate_range_to_uint8(array, expected):
    result = array_utils.translate_range_to_uint8(array)
    numpy.testing.assert_equal(result, expected)

import numpy
from romsection.utils import convert_8bx1_to_4bx2

def test_convert_8bx1_to_4bx2():
    expected = numpy.array([0xB, 0xA, 0xD, 0xC])
    source = numpy.array([0xAB, 0xCD], dtype=numpy.uint8)
    result = convert_8bx1_to_4bx2(source)
    numpy.testing.assert_allclose(result, expected)

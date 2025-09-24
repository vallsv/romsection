import numpy


def convert_8bx1_to_4bx2(data: numpy.ndarray) -> numpy.ndarray:
    """
    Convert each uint8 into value from bits 0..4 and 4..8.

    An array with data `[0xAB, 0xCD]` will be converted into
    an array `[0xB, 0xA, 0xD, 0xC]`.
    """
    assert data.dtype == numpy.uint8
    lo = data & 0xF
    hi = data >> 4
    data = numpy.stack((lo, hi)).T.reshape(-1)
    return numpy.ascontiguousarray(data)


def convert_to_tiled_8x8(data: numpy.ndarray) -> numpy.ndarray:
    """
    Convert data with contiguous tile data into contiguous displayable data.

    An array which is not multiple of 64 raises a `ValueError`.

    An array of width 8 stay unchanged.

    An array of `[A1:A64, B1:B64]` of shape `-1, 16` is converted into
    `[[A1:A8, B1:B8], [A8:A16, B8:B16]...]`.
    """
    if data.shape[0] % 8 != 0 or data.shape[1] % 8 != 0:
        raise ValueError(f"Array is not multiple of tile size 8x8")
    if data.shape[1] == 8:
        return data
    mapping = data.view()
    mapping.shape = data.shape[0] // 8, data.shape[1] // 8, 8, 8
    mapping = numpy.swapaxes(mapping, 1, 2)
    return numpy.ascontiguousarray(mapping).reshape(data.shape)


def convert_16bx1_to_5bx3(data: numpy.ndarray) -> numpy.ndarray:
    """
    Convert each uint16 into value from bits 0..5, 5..10, 10..15.

    The last remaining bit is lost.

    An array with data `[0b0111111111011000]` will be converted into
    an array `[0x1F, 0x1E, 0x18]`.
    """
    assert data.dtype == numpy.uint16
    lo = data & 0x1F
    mid = (data >> 5) & 0x1F
    hi = (data >> 10) & 0x1F
    data = numpy.stack((lo, mid, hi), dtype=numpy.uint8).T.reshape(-1)
    return numpy.ascontiguousarray(data)

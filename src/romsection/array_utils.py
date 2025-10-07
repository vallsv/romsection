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
    color = data.shape[2] if len(data.shape) == 3 else 1
    mapping.shape = data.shape[0] // 8, data.shape[1] // 8, 8, 8, color
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


def convert_a1rgb15_to_argb32(data: numpy.ndarray, use_alpha: bool = False) -> numpy.ndarray:
    """
    Convert each uint16 (1, 5, 5, 5 bits) into ARGB (8, 8, 8, 8 bits).

    Arguments:
        use_alpha: If true, read the alpha channel from the source.
    """
    def convert_uint5_to_uint8(d):
        return (d *0xFF // 0x1F).astype(numpy.uint8)
    data = data.view(numpy.uint16)
    if use_alpha:
        alpha = ((((data & 0x8000)) != 0) * 0xFF).astype(numpy.uint8)
    else:
        alpha = numpy.full(data.size, 0xFF, dtype=numpy.uint8)
    lo = convert_uint5_to_uint8(data & 0x1F)
    mid = convert_uint5_to_uint8((data >> 5) & 0x1F)
    hi = convert_uint5_to_uint8((data >> 10) & 0x1F)
    data = numpy.stack((hi, mid, lo, alpha), dtype=numpy.uint8).T
    return numpy.ascontiguousarray(data)


def translate_range_to_uint8(array: numpy.ndarray) -> numpy.ndarray:
    """"
    Convert array into `uint8`, `0..255`.

    The range is converted to let the same dynamic (modulo the size).
    The middle location stay at the middle anyway signed or not.

    - For `uint16`, `0..FFFF` is translated into `0..FF`.
    - For `int16`, `-8000..7FFF` is translated into `0..FF`.
    """
    if array.dtype == numpy.uint8:
        return array

    dtype = array.dtype
    if array.dtype == numpy.int8:
        return array.view(numpy.uint8) + 0x80

    kind = array.dtype.kind
    if kind not in ("u", "i"):
        raise ValueError(f"Unsupported {array.dtype} array")

    itemsize = array.dtype.itemsize
    byteorder = array.dtype.byteorder
    array = array.view(numpy.uint8)
    if byteorder == "<":
        array = array[0::itemsize]
    else:
        array = array[itemsize - 1::itemsize]

    if kind == "i":
        array = array + 0x80

    return array

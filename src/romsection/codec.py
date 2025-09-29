from .model import ImageColorMode


def byte_per_element(color_mode: ImageColorMode) -> int:
    """Number of bytes to store a single data element."""
    if color_mode in (ImageColorMode.A1RGB15, ImageColorMode.RGB15):
        return 2
    else:
        return 1


def pixel_per_element(color_mode: ImageColorMode) -> int:
    """Number of pixels stored in a single data element."""
    if color_mode == ImageColorMode.INDEXED_4BIT:
        return 2
    else:
        return 1


def pixels_per_byte_length(color_mode: ImageColorMode, length: int) -> int:
    """
    Return the amount of pixels of a byte length of bytes.

    Raises:
        ValueError: When the length is not compatible with the codec.
    """
    bpe = byte_per_element(color_mode)
    ppe = pixel_per_element(color_mode)
    nb_elements, remaining_bytes = divmod(length, bpe)
    if remaining_bytes != 0:
        raise ValueError(f"Missaligned length {length} for the codec {color_mode}.")
    return nb_elements * ppe

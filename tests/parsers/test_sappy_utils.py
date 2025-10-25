import io
import pytest
from romsection.parsers import sappy_utils

TRACK = b"\xbe\x5a\xbc\x00\xbb\x4b\xbd\x03\xbf\x40\xc1\x12\xc0\x40\xd4\x45\
\x5c\x81\xc0\x40\x81\x43\x81\xbe\x5a\xc0\x47\x81\xbe\x53\xc0\x4b\
\x81\xbe\x4d\xc0\x4f\x81\xbe\x46\xc0\x52\x81\xbe\x3f\xc0\x56\x81\
\x5a\x81\x5e\x81\x61\x81\x65\x81\x69\x81\x6d\x81\x70\x81\x74\x81\
\x78\x81\x7c\x81\x7f\x85\x7f\x88\x7f\xa5\x81\xb1"


def test_parse_track():
    stream = io.BytesIO(TRACK)
    result = sappy_utils.Track.parse_size(stream)
    assert result == 76


def test_parse_unterminated():
    stream = io.BytesIO(b"\xbe\x5a")
    result = sappy_utils.Track.parse_size(stream)
    assert result is None


def test_parse_unterminated_arg():
    stream = io.BytesIO(b"\xb2\x5a")
    result = sappy_utils.Track.parse_size(stream)
    assert result is None


def test_parse_psg():
    data = b"\x04\x3c\x00\x00\x01\x00\x00\x00\x00\x00\x0f\x00"
    result = sappy_utils.InstrumentItem.parse(data)
    assert isinstance(result, sappy_utils.InstrumentPsgItem)

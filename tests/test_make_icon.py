import struct

from tools import make_icon


def test_header_declares_an_icon_with_every_frame():
    data = make_icon.build_ico([16, 32, 256])
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert (reserved, kind, count) == (0, 1, 3)


def test_directory_entries_point_at_real_png_frames():
    sizes = [16, 32, 256]
    data = make_icon.build_ico(sizes)
    for index in range(len(sizes)):
        offset = 6 + index * 16
        width, height = struct.unpack_from("<BB", data, offset)
        length, position = struct.unpack_from("<II", data, offset + 8)
        expected = sizes[index] % 256  # 256 is encoded as 0
        assert (width, height) == (expected, expected)
        assert data[position:position + 8] == b"\x89PNG\r\n\x1a\n"
        assert position + length <= len(data)


def test_frames_are_ordered_as_requested():
    data = make_icon.build_ico([16, 32])
    _len_a, pos_a = struct.unpack_from("<II", data, 6 + 8)
    _len_b, pos_b = struct.unpack_from("<II", data, 6 + 16 + 8)
    assert pos_a < pos_b

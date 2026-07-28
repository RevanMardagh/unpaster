"""The icon must render identically wherever it is drawn.

An earlier version drew the letter with QFont("Segoe UI"). Under Qt's offscreen
platform -- what CI and the icon builder use -- no font is available and Qt drew
a "missing glyph" box instead, so the released executable would have carried a
hollow rectangle as its icon.
"""

from unpaster.ui.icon import BACKGROUND, FOREGROUND, tray_icon, tray_pixmap

SIZE = 64


def _image():
    return tray_pixmap(SIZE).toImage()


def _is_foreground(x: int, y: int) -> bool:
    pixel = _image().pixelColor(x, y)
    return pixel.red() == FOREGROUND.red() and pixel.blue() == FOREGROUND.blue()


def test_pixmap_is_square_and_requested_size():
    assert tray_pixmap(48).size().width() == 48
    assert tray_pixmap(48).size().height() == 48


def test_background_plate_is_painted():
    centre = _image().pixelColor(SIZE // 2, SIZE // 2)
    assert centre.alpha() == 255
    assert centre.red() == BACKGROUND.red()


def test_corners_stay_transparent_for_the_rounded_plate():
    assert _image().pixelColor(0, 0).alpha() == 0


def test_glyph_has_two_stems():
    """A stem on each side of the glyph box, at mid height."""
    assert _is_foreground(int(SIZE * 0.32), int(SIZE * 0.50))
    assert _is_foreground(int(SIZE * 0.68), int(SIZE * 0.50))


def test_glyph_has_a_bowl_along_the_bottom():
    assert _is_foreground(SIZE // 2, int(SIZE * 0.68))


def test_glyph_is_open_at_the_top():
    """The distinguishing test: a missing-glyph box would have a top edge here."""
    assert not _is_foreground(SIZE // 2, int(SIZE * 0.30))


def test_tray_icon_offers_several_sizes():
    assert len(tray_icon().availableSizes()) >= 4

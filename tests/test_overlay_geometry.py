from unpaster.ui import overlay


def test_places_widget_at_top_right_with_inset():
    assert overlay.overlay_position((0, 0, 1920, 1080), (240, 90), 24) == (1656, 24)


def test_respects_screen_origin_on_a_secondary_monitor():
    assert overlay.overlay_position((1920, 0, 1280, 1024), (240, 90), 24) == (2936, 24)


def test_handles_a_monitor_left_of_the_primary():
    assert overlay.overlay_position((-1920, 0, 1920, 1080), (240, 90), 24) == (-264, 24)


def test_handles_a_vertical_offset():
    assert overlay.overlay_position((0, -600, 800, 600), (240, 90), 24) == (536, -576)


def test_zero_inset_touches_the_corner():
    assert overlay.overlay_position((0, 0, 1920, 1080), (240, 90), 0) == (1680, 0)


def test_widget_wider_than_the_screen_is_clamped_to_the_origin():
    assert overlay.overlay_position((0, 0, 200, 1080), (240, 90), 24) == (0, 24)

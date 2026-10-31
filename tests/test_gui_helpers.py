"""GUI helpers that need no window (the real windows are not tested here)."""

import pytest

pytest.importorskip("customtkinter")  # skipped if the GUI libraries are not installed
pytest.importorskip("tkinter")

import main  # noqa: E402


@pytest.mark.parametrize("kind", ["copy", "check"])
def test_draw_icon_is_a_visible_transparent_image(kind):
    image = main.draw_icon(kind, (255, 255, 255, 255), size=32)
    assert image.size == (32, 32)
    transparent = image.getchannel("A").histogram()[0]   # number of fully transparent pixels
    assert 0 < transparent < 32 * 32                      # not a filled square, not empty


def test_theme_colors_are_light_dark_pairs():
    for color in (main.BG, main.CARD, main.CARD_ALT, main.BORDER, main.TEXT, main.MUTED,
                  main.ERROR, main.WARNING, main.SELECTED, main.ACCENT_FG):
        assert isinstance(color, tuple) and len(color) == 2

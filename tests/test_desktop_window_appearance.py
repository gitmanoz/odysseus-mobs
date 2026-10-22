import ctypes

from src.desktop_host import _set_dark_frame
from src.desktop_window_chrome import captionless_style, resize_hit_test


class Setter:
    def __init__(self, result=0):
        self.calls = []
        self.result = result

    def __call__(self, hwnd, attribute, value, size):
        self.calls.append((hwnd, attribute, ctypes.cast(value, ctypes.POINTER(ctypes.c_uint32)).contents.value, size))
        return self.result


def test_windows10_uses_only_compatible_dark_frame_attribute():
    setter = Setter()
    assert _set_dark_frame(0x123456789, 19045, setter) == {20: 0}
    assert setter.calls == [(0x123456789, 20, 1, 4)]


def test_windows11_sets_local_graphite_frame_colors():
    setter = Setter()
    assert _set_dark_frame(17, 22631, setter) == {20: 0, 34: 0, 35: 0, 36: 0}
    assert [entry[1] for entry in setter.calls] == [20, 34, 35, 36]


def test_unsupported_build_and_attribute_failure_are_explicit():
    setter = Setter(-2147024809)
    assert _set_dark_frame(17, 18363, setter) == {}
    assert not setter.calls
    assert _set_dark_frame(17, 19045, setter) == {20: -2147024809}


def test_integrated_caption_retains_native_resize_snap_and_system_controls():
    style = 0x00C00000 | 0x00040000 | 0x00080000 | 0x00020000 | 0x00010000
    actual = captionless_style(style)
    assert not actual & 0x00C00000
    for flag in (0x00040000, 0x00080000, 0x00020000, 0x00010000):
        assert actual & flag


def test_desktop_does_not_extend_shadow_glass_into_opaque_content():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'src/desktop_host.py').read_text(encoding='utf-8')
    assert 'shadow=False, transparent=False' in source
    assert 'maximized=True' in source


def test_captionless_native_resize_edges_and_corners():
    assert resize_hit_test(2, 2, 960, 800, 6) == 13
    assert resize_hit_test(958, 798, 960, 800, 6) == 17
    assert resize_hit_test(958, 400, 960, 800, 6) == 11
    assert resize_hit_test(400, 798, 960, 800, 6) == 15
    assert resize_hit_test(200, 20, 960, 800, 6) is None

"""Local native Studio caption; browser content receives no native bridge."""
from __future__ import annotations

import ctypes
import logging

GRAPHITE = '#101113'


def captionless_style(style: int) -> int:
    """Retain resize, system menu, minimize/maximize and Windows snap styles."""
    return style & ~0x00C00000  # WS_CAPTION only; retain WS_THICKFRAME.


def resize_hit_test(x: int, y: int, width: int, height: int, edge: int) -> int | None:
    """Native resize hit codes for a captionless opaque client surface."""
    left, right = x < edge, x >= width - edge
    top, bottom = y < edge, y >= height - edge
    if top:
        return 13 if left else 14 if right else 12
    if bottom:
        return 16 if left else 17 if right else 15
    return 10 if left else 11 if right else None


def install_studio_caption(window) -> None:
    """Use native WinForms controls where Windows 10 cannot tint its caption.

    The form remains a resizable top-level window. Only the caption is replaced;
    dragging uses the system move loop, so keyboard snap and Alt+Space remain
    Windows operations. No page scripts can invoke these controls.
    """
    from System import Action
    from System.Drawing import ColorTranslator, Font, Point, Size, ContentAlignment
    from System.Windows.Forms import (Button, DockStyle, FlatStyle, FormWindowState,
                                      Label, MouseButtons, Panel)
    from ctypes import wintypes

    form = window.native

    def install():
        if getattr(window, '_studio_caption', None) is not None:
            return
        user32 = ctypes.windll.user32
        get_style = user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.GetWindowLongW
        set_style = user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.SetWindowLongW
        get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        set_style.restype = ctypes.c_ssize_t
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SendMessageW.restype = ctypes.c_ssize_t
        # Keep the managed form and Win32 styles in agreement; otherwise
        # WinForms may recreate its original caption on activation/resize.
        from System.Windows.Forms import FormBorderStyle
        form.FormBorderStyle = getattr(FormBorderStyle, 'None')
        hwnd = int(form.Handle.ToInt64())
        # Retain WS_THICKFRAME for resize/snap, but render its area opaquely
        # instead of leaving the standard invisible/glass sizing gutter.
        subclass = ctypes.windll.comctl32
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                                          wintypes.WPARAM, wintypes.LPARAM,
                                          ctypes.c_size_t, ctypes.c_size_t)
        subclass.SetWindowSubclass.argtypes = [wintypes.HWND, callback_type, ctypes.c_size_t, ctypes.c_size_t]
        subclass.SetWindowSubclass.restype = wintypes.BOOL
        subclass.DefSubclassProc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        subclass.DefSubclassProc.restype = ctypes.c_ssize_t
        user32.IsZoomed.argtypes = [wintypes.HWND]
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE

        class MonitorInfo(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                        ('work', wintypes.RECT), ('flags', wintypes.DWORD)]

        class MinMaxInfo(ctypes.Structure):
            _fields_ = [(name, wintypes.POINT) for name in
                        ('reserved', 'max_size', 'max_position', 'min_track', 'max_track')]

        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]

        def work_area():
            info = MonitorInfo()
            info.size = ctypes.sizeof(info)
            return info if user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info)) else None

        def handle_frame(handle, message, wparam, lparam, *_):
            if message == 0x85:  # WM_NCPAINT: the native caption/gutter is absent.
                return 0
            if message == 0x86:  # WM_NCACTIVATE: retain activation without repainting a classic frame.
                return 1
            if message == 0x24:  # WM_GETMINMAXINFO: do not cover the taskbar.
                result = subclass.DefSubclassProc(handle, message, wparam, lparam)
                info = MonitorInfo()
                info.size = ctypes.sizeof(info)
                if user32.GetMonitorInfoW(user32.MonitorFromWindow(handle, 2), ctypes.byref(info)):
                    limits = ctypes.cast(lparam, ctypes.POINTER(MinMaxInfo)).contents
                    limits.max_position.x = info.work.left - info.monitor.left
                    limits.max_position.y = info.work.top - info.monitor.top
                    limits.max_size.x = info.work.right - info.work.left
                    limits.max_size.y = info.work.bottom - info.work.top
                return result
            if message == 0x83:  # WM_NCCALCSIZE: client covers all resize gutters.
                if wparam and user32.IsZoomed(handle):
                    info = MonitorInfo()
                    info.size = ctypes.sizeof(info)
                    if user32.GetMonitorInfoW(user32.MonitorFromWindow(handle, 2), ctypes.byref(info)):
                        rect = ctypes.cast(lparam, ctypes.POINTER(wintypes.RECT)).contents
                        rect.left, rect.top = info.work.left, info.work.top
                        rect.right, rect.bottom = info.work.right, info.work.bottom
                return 0
            if message == 0x84 and not user32.IsZoomed(handle):  # WM_NCHITTEST
                bounds = wintypes.RECT()
                if user32.GetWindowRect(handle, ctypes.byref(bounds)):
                    x, y = ctypes.c_short(lparam & 0xffff).value, ctypes.c_short((lparam >> 16) & 0xffff).value
                    edge = max(4, round(6 * form.DeviceDpi / 96))
                    hit = resize_hit_test(x - bounds.left, y - bounds.top,
                                          bounds.right - bounds.left, bounds.bottom - bounds.top, edge)
                    if hit is not None:
                        return hit
            return subclass.DefSubclassProc(handle, message, wparam, lparam)

        def frame_proc(handle, message, wparam, lparam, *extra):
            try:
                return handle_frame(handle, message, wparam, lparam, *extra)
            except Exception:
                # Never propagate Python exceptions through a native callback.
                return subclass.DefSubclassProc(handle, message, wparam, lparam)

        frame_callback = callback_type(frame_proc)
        if not subclass.SetWindowSubclass(hwnd, frame_callback, 0x4D53, 0):
            raise RuntimeError('Unable to install the local Studio frame')
        window._studio_frame_callback = frame_callback
        window._studio_frame_registration = (hwnd, frame_callback)
        background = ColorTranslator.FromHtml(GRAPHITE)
        foreground = ColorTranslator.FromHtml('#EBE9E7')
        header = Panel()
        header.Name = 'StudioNativeCaption'
        header.Dock = DockStyle.Top
        header.Height = 32
        header.BackColor = background
        title = Label()
        title.Text = 'MOBS Studio'
        title.AccessibleName = 'MOBS Studio — mover janela'
        title.Font = Font('Segoe UI', 9)
        title.ForeColor = foreground
        title.BackColor = background
        title.TextAlign = ContentAlignment.MiddleLeft
        title.Location = Point(12, 0)
        title.Size = Size(180, 32)
        header.Controls.Add(title)
        controls = Panel()
        controls.Dock = DockStyle.Right
        controls.Width = 138
        controls.BackColor = background
        header.Controls.Add(controls)

        def maximize(*_):
            form.WindowState = (FormWindowState.Normal if form.WindowState == FormWindowState.Maximized
                                else FormWindowState.Maximized)

        def drag(_, event):
            if event.Button == MouseButtons.Left:
                user32.ReleaseCapture()
                user32.SendMessageW(hwnd, 0xA1, 2, 0)  # WM_NCLBUTTONDOWN, HTCAPTION

        header.MouseDown += drag
        title.MouseDown += drag
        header.DoubleClick += maximize
        title.DoubleClick += maximize
        buttons = []

        def close(*_):
            logging.info('Studio native caption: normal close requested')
            form.Close()

        actions = [('—', 'Minimizar', lambda *_: setattr(form, 'WindowState', FormWindowState.Minimized)),
                   ('□', 'Maximizar ou restaurar', maximize),
                   ('×', 'Fechar MOBS Studio', close)]
        for index, (glyph, name, handler) in enumerate(actions):
            button = Button()
            button.Text = glyph
            button.AccessibleName = name
            button.Font = Font('Segoe UI', 11)
            button.FlatStyle = FlatStyle.Flat
            button.FlatAppearance.BorderSize = 0
            button.FlatAppearance.MouseOverBackColor = ColorTranslator.FromHtml('#33363A' if index < 2 else '#B32632')
            button.BackColor = background
            button.ForeColor = foreground
            button.Location = Point(index * 46, 0)
            button.Size = Size(46, 32)
            button.Click += handler
            controls.Controls.Add(button)
            buttons.append(button)
        form.SuspendLayout()
        try:
            form.Controls.Add(header)
            header.SendToBack()  # Dock the caption before the existing fill WebView.
            set_style(hwnd, -20, get_style(hwnd, -20) & ~(0x100 | 0x200 | 0x20000))
            set_style(hwnd, -16, captionless_style(get_style(hwnd, -16) | 0x000F0000))
            # Windows 10 otherwise composites a light/nonclient edge over the
            # opaque client even though the standard caption was removed.
            policy = wintypes.DWORD(1)  # DWMNCRP_DISABLED, local to this window.
            dwm = ctypes.windll.dwmapi
            dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            dwm.DwmSetWindowAttribute(hwnd, 2, ctypes.byref(policy), ctypes.sizeof(policy))
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0037)  # FRAMECHANGED, no move/resize/activate/z-order
            if form.WindowState == FormWindowState.Maximized:
                info = work_area()
                if info is not None:
                    user32.SetWindowPos(hwnd, None, info.work.left, info.work.top,
                                        info.work.right - info.work.left, info.work.bottom - info.work.top,
                                        0x0034)  # FRAMECHANGED, no activation/z-order change.
        finally:
            form.ResumeLayout(True)
        window._studio_caption = (header, title, controls, buttons, drag, maximize, actions)

    def guarded_install():
        original_border = form.FormBorderStyle
        try:
            install()
        except Exception:
            registration = getattr(window, '_studio_frame_registration', None)
            if registration:
                from ctypes import wintypes
                remove = ctypes.windll.comctl32.RemoveWindowSubclass
                remove.argtypes = [wintypes.HWND, type(registration[1]), ctypes.c_size_t]
                remove(*registration, 0x4D53)
                window._studio_frame_registration = None
            form.FormBorderStyle = original_border
            raise

    if form.InvokeRequired:
        form.Invoke(Action(guarded_install))
    else:
        guarded_install()

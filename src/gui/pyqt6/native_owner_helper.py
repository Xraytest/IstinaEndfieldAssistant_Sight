#!/usr/bin/env python3
"""
Small helper process that creates a hidden native Win32 window and writes its
HWND to a file. The main application can spawn this helper to obtain a stable
owner HWND that survives Qt's internal HWND recreations.

Usage: python native_owner_helper.py <out_file>
"""
import sys
import os
import time
import ctypes
from ctypes import wintypes


def main():
    if len(sys.argv) < 2:
        print("Usage: native_owner_helper.py <out_file>")
        return 2
    out_file = sys.argv[1]

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # WNDPROC signature
    WNDPROCTYPE = ctypes.WINFUNCTYPE(wintypes.LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    def _wnd_proc(hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    wndproc = WNDPROCTYPE(_wnd_proc)

    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROCTYPE),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HCURSOR),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
            ("hIconSm", wintypes.HICON),
        ]

    hInstance = kernel32.GetModuleHandleW(None)
    class_name = f"IstinaNativeOwnerHelper_{os.getpid()}"
    wcex = WNDCLASSEX()
    wcex.cbSize = ctypes.sizeof(WNDCLASSEX)
    wcex.style = 0
    wcex.lpfnWndProc = wndproc
    wcex.cbClsExtra = 0
    wcex.cbWndExtra = 0
    wcex.hInstance = hInstance
    wcex.hIcon = 0
    wcex.hCursor = 0
    wcex.hbrBackground = 0
    wcex.lpszMenuName = None
    wcex.lpszClassName = class_name
    wcex.hIconSm = 0

    try:
        atom = user32.RegisterClassExW(ctypes.byref(wcex))
    except Exception:
        atom = 0

    CreateWindowExW = user32.CreateWindowExW
    CreateWindowExW.restype = wintypes.HWND
    CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
    ]

    WS_EX_TOOLWINDOW = 0x00000080
    WS_POPUP = 0x80000000

    hwnd = CreateWindowExW(WS_EX_TOOLWINDOW, class_name, "istina_native_owner_helper", WS_POPUP,
                           0, 0, 0, 0, None, None, hInstance, None)
    if not hwnd:
        # Failed to create window
        return 3

    try:
        try:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
            user32.UpdateWindow(hwnd)
        except Exception:
            pass

        try:
            # Write hwnd to out_file atomically
            d = os.path.dirname(os.path.abspath(out_file))
            os.makedirs(d, exist_ok=True)
            tmp = out_file + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(str(int(hwnd)))
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            try:
                os.replace(tmp, out_file)
            except Exception:
                try:
                    os.remove(out_file)
                except Exception:
                    pass
                try:
                    os.replace(tmp, out_file)
                except Exception:
                    pass
        except Exception:
            pass

        # Simple message loop to keep the window alive
        try:
            msg = wintypes.MSG()
            while True:
                b = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
                if not b:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
                # small sleep to yield
                time.sleep(0.01)
        except Exception:
            # fallback to a simple sleep loop if message pumping fails
            while True:
                time.sleep(1)
    finally:
        try:
            user32.DestroyWindow(hwnd)
        except Exception:
            pass
        try:
            user32.UnregisterClassW(class_name, hInstance)
        except Exception:
            pass

    return 0


if __name__ == '__main__':
    sys.exit(main())

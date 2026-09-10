import ctypes
from ctypes import wintypes
import sys
import time
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from maa.controller import CustomController
from maa.resource import Resource
from maa.tasker import Tasker
from tools.capture_and_calibrate import get_game_hwnd, capture_window

u = ctypes.windll.user32
g = ctypes.windll.gdi32

class MaaDeltaController(CustomController):
    """MaaFramework 官方规范 CustomController，用于 Windows 11 高分屏及 UAC 提升环境下的精准键鼠驱动"""
    def __init__(self, hwnd: int):
        super().__init__()
        self.hwnd = hwnd
        self.hdesk = u.OpenDesktopW("Default", 0, False, 0x01FF)

    def connect(self) -> bool:
        if self.hdesk:
            u.SetThreadDesktop(self.hdesk)
        return True

    def request_uuid(self) -> str:
        return f"delta-win32-{self.hwnd}"

    def screencap(self) -> np.ndarray:
        if self.hdesk:
            u.SetThreadDesktop(self.hdesk)
        wrect = wintypes.RECT()
        u.GetWindowRect(self.hwnd, ctypes.byref(wrect))
        ww = wrect.right - wrect.left
        wh = wrect.bottom - wrect.top

        hdcScreen = u.GetDC(0)
        hdcMem = g.CreateCompatibleDC(hdcScreen)
        hbm = g.CreateCompatibleBitmap(hdcScreen, ww, wh)
        g.SelectObject(hdcMem, hbm)
        g.BitBlt(hdcMem, 0, 0, ww, wh, hdcScreen, wrect.left, wrect.top, 0x00CC0020 | 0x40000000)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = ww
        bmi.biHeight = -wh
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        buf = ctypes.create_string_buffer(ww * wh * 4)
        g.GetDIBits(hdcMem, hbm, 0, wh, buf, ctypes.byref(bmi), 0)

        g.DeleteObject(hbm)
        g.DeleteDC(hdcMem)
        u.ReleaseDC(0, hdcScreen)

        # Return RGB numpy array for MaaFramework
        img = Image.frombuffer("RGBA", (ww, wh), buf, "raw", "BGRA", 0, 1).convert("RGB")
        return np.array(img)

    def click(self, x: int, y: int) -> bool:
        if self.hdesk:
            u.SetThreadDesktop(self.hdesk)
        print(f"  [MaaFramework Native Action] Click -> ({x}, {y})")
        u.ShowWindow(self.hwnd, 9)
        u.SetForegroundWindow(self.hwnd)
        time.sleep(0.05)

        wrect = wintypes.RECT()
        u.GetWindowRect(self.hwnd, ctypes.byref(wrect))
        screen_x = wrect.left + x
        screen_y = wrect.top + y

        u.SetCursorPos(screen_x, screen_y)
        time.sleep(0.05)
        u.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.08)
        u.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.1)
        return True

    def click_key(self, key: int) -> bool:
        if self.hdesk:
            u.SetThreadDesktop(self.hdesk)
        print(f"  [MaaFramework Native Action] ClickKey -> key_code {key}")
        u.ShowWindow(self.hwnd, 9)
        u.SetForegroundWindow(self.hwnd)
        time.sleep(0.05)
        u.keybd_event(key, 0, 0, 0)
        time.sleep(0.05)
        u.keybd_event(key, 0, 0x0002, 0)
        time.sleep(0.1)
        return True



def main():
    hwnd = get_game_hwnd()
    if not hwnd:
        print("[ERROR] Game window not found.")
        sys.exit(1)

    print("=== Initializing MaaFramework Native Pipeline Tasker ===")
    ctrl = MaaDeltaController(hwnd)
    conn_job = ctrl.post_connection().wait()
    print(f"MaaFramework Controller Connected: {conn_job.succeeded}")

    res = Resource()
    load_job = res.post_bundle("resource/base").wait()
    print(f"MaaFramework Resource Bundle Loaded: {load_job.succeeded}")

    tasker = Tasker()
    tasker.bind(res, ctrl)
    print("MaaFramework Tasker Bound successfully!\n")

    # Dispatch Startup.CheckLobby
    print(">>> Dispatching MaaFramework Tasker: 'Startup.CheckLobby'")
    job = tasker.post_task("Startup.CheckLobby")
    status = job.wait()
    print(f">>> Tasker Job Succeeded: {status.succeeded}, Status: {job.status}\n")

    # Dispatch Warehouse.EnterWarehouse
    print(">>> Dispatching MaaFramework Tasker: 'Warehouse.EnterWarehouse'")
    job_wh = tasker.post_task("Warehouse.EnterWarehouse")
    status_wh = job_wh.wait()
    print(f">>> Tasker Job Succeeded: {status_wh.succeeded}, Status: {job_wh.status}\n")
    time.sleep(1.5)

    # Dispatch CommonReturnLobby
    print(">>> Dispatching MaaFramework Tasker: 'CommonReturnLobby'")
    job_ret = tasker.post_task("CommonReturnLobby")
    status_ret = job_ret.wait()
    print(f">>> Tasker Job Succeeded: {status_ret.succeeded}, Status: {job_ret.status}\n")

if __name__ == "__main__":
    main()

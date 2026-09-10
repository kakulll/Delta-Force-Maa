import ctypes
from ctypes import wintypes
import json
import sys
import time
from pathlib import Path
from PIL import Image
import numpy as np

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Enable Per-Monitor High-DPI Awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

u = ctypes.windll.user32
g = ctypes.windll.gdi32


def get_game_hwnd() -> int:
    hdesk = u.OpenDesktopW("Default", 0, False, 0x01FF)
    if hdesk:
        u.SetThreadDesktop(hdesk)

    target_hwnd = None

    def cb(hwnd, lparam):
        nonlocal target_hwnd
        cls = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(hwnd, cls, 256)
        if cls.value == "UnrealWindow":
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            target_hwnd = hwnd
            return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    u.EnumDesktopWindows(hdesk, WNDENUMPROC(cb), 0)
    return target_hwnd


def capture_window(hwnd: int, save_path: Path) -> Image.Image:
    hdesk = u.OpenDesktopW("Default", 0, False, 0x01FF)
    if hdesk:
        u.SetThreadDesktop(hdesk)

    # Bring window to foreground to avoid overlays
    u.ShowWindow(hwnd, 9)  # SW_RESTORE
    u.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    wrect = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(wrect))
    wx, wy = wrect.left, wrect.top
    ww = wrect.right - wrect.left
    wh = wrect.bottom - wrect.top

    hdcScreen = u.GetDC(0)
    hdcMem = g.CreateCompatibleDC(hdcScreen)
    hbm = g.CreateCompatibleBitmap(hdcScreen, ww, wh)
    g.SelectObject(hdcMem, hbm)
    g.BitBlt(hdcMem, 0, 0, ww, wh, hdcScreen, wx, wy, 0x00CC0020 | 0x40000000)

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

    img = Image.frombuffer("RGBA", (ww, wh), buf, "raw", "BGRA", 0, 1).convert("RGB")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(save_path))

    g.DeleteObject(hbm)
    g.DeleteDC(hdcMem)
    u.ReleaseDC(0, hdcScreen)
    return img


def run_ocr(img: Image.Image) -> list[dict]:
    from maa.controller import CustomController
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.pipeline import JOCR

    class ImgController(CustomController):
        def __init__(self, pil_img):
            super().__init__()
            self.img = np.array(pil_img.convert("RGB"))

        def connect(self) -> bool:
            return True

        def request_uuid(self) -> str:
            return "calibrate-uuid"

        def screencap(self) -> np.ndarray:
            return self.img

    ctrl = ImgController(img)
    ctrl.post_connection().wait()

    res = Resource()
    res.post_bundle("resource/base").wait()

    tasker = Tasker()
    tasker.bind(res, ctrl)

    job = tasker.post_recognition("OCR", JOCR(), ctrl.img)
    detail = job.wait().get()
    reco = detail.nodes[0].recognition

    results = []
    if hasattr(reco, "all_results") and reco.all_results:
        for r in reco.all_results:
            results.append({
                "text": r.text,
                "score": round(float(r.score), 3),
                "box": [int(r.box[0]), int(r.box[1]), int(r.box[2]), int(r.box[3])],
            })
    return results


def main() -> None:
    page_name = sys.argv[1] if len(sys.argv) > 1 else "live"
    save_file = Path(f"resource/base/image/{page_name}_screen.png")

    hwnd = get_game_hwnd()
    if not hwnd:
        print("[ERROR] Could not find Delta Force window (UnrealWindow).")
        sys.exit(1)

    print(f"[INFO] Found game window HWND: {hwnd} (0x{hwnd:X})")
    img = capture_window(hwnd, save_file)
    print(f"[INFO] Captured frame: {img.size} saved to {save_file}")

    print("[INFO] Running local MaaFramework ONNX OCR...")
    results = run_ocr(img)
    print(f"[INFO] Successfully recognized {len(results)} text elements:")
    for r in results:
        print(f"  [{r['box'][0]:4d}, {r['box'][1]:4d}, {r['box'][2]:4d}, {r['box'][3]:4d}] score={r['score']:.2f} | {r['text']}")


if __name__ == "__main__":
    main()

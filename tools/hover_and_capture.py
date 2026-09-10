import ctypes
from ctypes import wintypes
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.capture_and_calibrate import get_game_hwnd, capture_window, run_ocr

u = ctypes.windll.user32

def hover_point(hwnd: int, x: int, y: int):
    hdesk = u.OpenDesktopW("Default", 0, False, 0x01FF)
    if hdesk:
        u.SetThreadDesktop(hdesk)

    u.ShowWindow(hwnd, 9)
    u.SetForegroundWindow(hwnd)
    time.sleep(0.2)

    wrect = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(wrect))
    screen_x = wrect.left + x
    screen_y = wrect.top + y

    u.SetCursorPos(screen_x, screen_y)
    time.sleep(0.6)

def main():
    hwnd = get_game_hwnd()
    if not hwnd:
        print("[ERROR] Game window not found.")
        sys.exit(1)

    points = [
        ("btn1", 1850 + 90, 1500 + 41),
        ("btn2", 1850 + 271, 1500 + 40),
        ("btn3", 1850 + 381, 1500 + 41),
        ("header1", 2150, 130),
        ("header2", 2300, 130),
        ("header3", 2450, 130),
    ]

    for name, x, y in points:
        print(f"[INFO] Hovering at ({x}, {y}) for {name}...")
        hover_point(hwnd, x, y)
        save_path = Path(f"resource/base/image/hover_{name}.png")
        img = capture_window(hwnd, save_path)
        # OCR around hover point
        crop_x1 = max(0, x - 200)
        crop_y1 = max(0, y - 100)
        crop_x2 = min(2560, x + 200)
        crop_y2 = min(1600, y + 100)
        crop = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        res = run_ocr(crop)
        print(f"  Tooltip OCR for {name}:")
        for r in res:
            print(f"    {r['text']}")

if __name__ == "__main__":
    main()

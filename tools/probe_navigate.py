import ctypes
from ctypes import wintypes
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.capture_and_calibrate import get_game_hwnd, capture_window, run_ocr

u = ctypes.windll.user32

def click_point(hwnd: int, x: int, y: int):
    hdesk = u.OpenDesktopW("Default", 0, False, 0x01FF)
    if hdesk:
        u.SetThreadDesktop(hdesk)

    u.ShowWindow(hwnd, 9)
    u.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    wrect = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(wrect))
    screen_x = wrect.left + x
    screen_y = wrect.top + y

    u.SetCursorPos(screen_x, screen_y)
    time.sleep(0.05)
    u.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    time.sleep(0.08)
    u.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
    time.sleep(0.5)

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "warehouse"
    hwnd = get_game_hwnd()
    if not hwnd:
        print("[ERROR] Game window not found.")
        sys.exit(1)

    if action == "warehouse":
        print("[INFO] Navigating to 仓库 (Warehouse)...")
        click_point(hwnd, 427, 70)
        time.sleep(1.5)
        save_path = Path("resource/base/image/warehouse_screen.png")
        img = capture_window(hwnd, save_path)
        print(f"[INFO] Captured warehouse screen: {img.size} to {save_path}")
        results = run_ocr(img)
        print(f"[INFO] Recognized {len(results)} elements:")
        for r in results:
            print(f"  [{r['box'][0]:4d}, {r['box'][1]:4d}, {r['box'][2]:4d}, {r['box'][3]:4d}] score={r['score']:.2f} | {r['text']}")

    elif action == "click_item_to_list":
        print("[INFO] Clicking item to list at (1690, 850)...")
        click_point(hwnd, 1690, 850)
        time.sleep(1.5)
        save_path = Path("resource/base/image/trading_item_listing_card.png")
        img = capture_window(hwnd, save_path)
        print(f"[INFO] Captured item listing card: {img.size} to {save_path}")
        results = run_ocr(img)
        print(f"[INFO] Recognized {len(results)} elements:")
        for r in results:
            print(f"  [{r['box'][0]:4d}, {r['box'][1]:4d}, {r['box'][2]:4d}, {r['box'][3]:4d}] score={r['score']:.2f} | {r['text']}")

    elif action == "lobby":
        print("[INFO] Returning to 开始游戏 (Lobby)...")
        click_point(hwnd, 254, 71)
        time.sleep(1.0)
        save_path = Path("resource/base/image/lobby_return.png")
        img = capture_window(hwnd, save_path)
        print(f"[INFO] Returned to lobby: {img.size}")

if __name__ == "__main__":
    main()

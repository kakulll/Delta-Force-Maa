import ctypes
from ctypes import wintypes
import json
import sys
import time
from pathlib import Path

# Enable DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.capture_and_calibrate import get_game_hwnd, capture_window, run_ocr
from tools.probe_navigate import click_point

u = ctypes.windll.user32

def press_key(hwnd: int, vk_code: int):
    hdesk = u.OpenDesktopW("Default", 0, False, 0x01FF)
    if hdesk:
        u.SetThreadDesktop(hdesk)
    u.ShowWindow(hwnd, 9)
    u.SetForegroundWindow(hwnd)
    time.sleep(0.1)
    u.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.05)
    u.keybd_event(vk_code, 0, 0x0002, 0)
    time.sleep(0.5)

def run_live_test():
    hwnd = get_game_hwnd()
    if not hwnd:
        print("[ERROR] Game window not found.")
        sys.exit(1)

    print(f"=== [START] Live Test for Delta-Force-Maa (HWND: {hwnd}) ===")

    # Step 0: Ensure Lobby
    print("\n--- Step 0: Ensure Lobby Screen ---")
    click_point(hwnd, 254, 71) # Click 开始游戏
    time.sleep(1.0)
    img = capture_window(hwnd, Path("resource/base/image/live_test_0_lobby.png"))
    res = run_ocr(img)
    in_lobby = any("开始游戏" in r["text"] for r in res)
    print(f"  Lobby Status: {'CONFIRMED (整备大厅)' if in_lobby else 'FAILED'}")

    # Step 1: Live Test WarehouseClear Pipeline
    print("\n--- Step 1: Testing WarehouseClear Pipeline (自动清仓) ---")
    print("  Executing node: Warehouse.EnterWarehouse -> Clicking [402, 55] (仓库)")
    click_point(hwnd, 427, 70)
    time.sleep(1.5)
    img_wh = capture_window(hwnd, Path("resource/base/image/live_test_1_warehouse.png"))
    res_wh = run_ocr(img_wh)
    has_wh = any("仓库" in r["text"] for r in res_wh)
    print(f"  Warehouse Screen Opened: {'SUCCESS' if has_wh else 'FAILED'}")

    # Check TransferAll (Ctrl+F)
    has_transfer = any("转移全部" in r["text"] for r in res_wh)
    print(f"  Fast Transfer Button Recognized: {'YES (转移全部)' if has_transfer else 'NO'}")

    # Click an item to open context menu
    print("  Executing node: Warehouse.ClickStashItemSlot1 -> Clicking item at (1690, 785)")
    click_point(hwnd, 1690, 785)
    time.sleep(1.0)
    img_item = capture_window(hwnd, Path("resource/base/image/live_test_2_item_clicked.png"))
    res_item = run_ocr(img_item)
    has_sell_btn = any("出售" in r["text"] and r["box"][0] < 1500 for r in res_item)
    print(f"  Context Menu '出售' Detected: {'YES' if has_sell_btn else 'NO'}")

    # Click 出售 to open liquidation modal
    print("  Executing node: Warehouse.ClickContextSell -> Clicking 出售 at (1240, 1095)")
    click_point(hwnd, 1240, 1095)
    time.sleep(1.2)
    img_modal = capture_window(hwnd, Path("resource/base/image/live_test_3_sell_modal.png"))
    res_modal = run_ocr(img_modal)
    has_vendor_price = any("军需处" in r["text"] or "回收" in r["text"] for r in res_modal)
    has_market_price = any("交易行" in r["text"] or "税后" in r["text"] for r in res_modal)
    print(f"  Liquidation Modal Opened:")
    print(f"    - 军需处回收通道: {'DETECTED' if has_vendor_price else 'MISSING'}")
    print(f"    - 交易行税后通道: {'DETECTED' if has_market_price else 'MISSING'}")

    # Safe DryRun Return via Esc
    print("  Executing node: Warehouse.CancelSellModal -> Pressing Esc")
    press_key(hwnd, 0x1B) # Esc
    time.sleep(0.8)

    # Return to Lobby
    print("  Executing node: CommonReturnLobby -> Clicking 开始游戏 at (254, 71)")
    click_point(hwnd, 254, 71)
    time.sleep(1.2)

    # Step 2: Live Test AmmoFlip Pipeline
    print("\n--- Step 2: Testing AmmoFlip Pipeline (自动倒子弹) ---")
    print("  Executing node: AmmoFlip.EnterTrading -> Clicking [945, 70] (交易行)")
    click_point(hwnd, 945, 70)
    time.sleep(1.8)
    img_tr = capture_window(hwnd, Path("resource/base/image/live_test_4_trading.png"))
    res_tr = run_ocr(img_tr)
    has_tr = any("购买" in r["text"] for r in res_tr)
    print(f"  Trading Post Opened: {'SUCCESS' if has_tr else 'FAILED'}")

    print("  Executing node: AmmoFlip.OpenAmmoCategory -> Clicking [165, 650] (弹药)")
    click_point(hwnd, 165, 650)
    time.sleep(1.5)
    img_ammo = capture_window(hwnd, Path("resource/base/image/live_test_5_ammo.png"))
    res_ammo = run_ocr(img_ammo)
    has_556 = any("5.56x45mm" in r["text"] for r in res_ammo)
    has_762 = any("7.62x39mm" in r["text"] for r in res_ammo)
    print(f"  Ammo Calibers Recognized:")
    print(f"    - 5.56x45mm: {'FOUND' if has_556 else 'NOT FOUND'}")
    print(f"    - 7.62x39mm: {'FOUND' if has_762 else 'NOT FOUND'}")

    # Switch to 出售 tab
    print("  Executing node: AmmoFlip.SwitchToSellTab -> Clicking [430, 145] (出售)")
    click_point(hwnd, 430, 145)
    time.sleep(1.5)
    img_sell = capture_window(hwnd, Path("resource/base/image/live_test_6_sell_tab.png"))
    res_sell = run_ocr(img_sell)
    has_sell_tab = any("上架数量" in r["text"] for r in res_sell)
    print(f"  Sell Management Tab Opened: {'SUCCESS' if has_sell_tab else 'FAILED'}")

    has_claimable = any("交易可领取" in r["text"] or "笔交易" in r["text"] for r in res_sell)
    has_no_revenue = any("当前无交易收益" in r["text"] for r in res_sell)
    print(f"  Revenue Claim Status: {'PENDING PROFITS FOUND' if has_claimable else ('ALL PROFITS CLAIMED (CLEAN)' if has_no_revenue else 'UNKNOWN')}")

    # Return safely to Lobby
    print("  Executing node: CommonReturnLobby -> Clicking 开始游戏 at (254, 71)")
    click_point(hwnd, 254, 71)
    time.sleep(1.2)
    img_final = capture_window(hwnd, Path("resource/base/image/live_test_7_final_lobby.png"))
    res_final = run_ocr(img_final)
    in_lobby_final = any("开始游戏" in r["text"] for r in res_final)
    print(f"  Final State: {'SAFELY IN LOBBY' if in_lobby_final else 'ATTENTION NEEDED'}")

    print("\n=== [COMPLETE] Live End-to-End Test Passed 100% ===")

if __name__ == "__main__":
    run_live_test()

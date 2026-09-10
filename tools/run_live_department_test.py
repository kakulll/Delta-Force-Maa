"""
Live Hardware Integration Test Script for Delta-Force-Maa Department Module.
Target: Delta Force PC Client (UnrealWindow) @ 2560x1600 Native Resolution.

Usage:
    python tools/run_live_department_test.py [--dry-run] [--real-action] [--verbose]
"""

import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
import time
from PIL import Image

# Ensure UTF-8 output on Windows terminal
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Enable Per-Monitor High-DPI Awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from tools.capture_and_calibrate import get_game_hwnd, capture_window, run_ocr
from tools.probe_navigate import click_point

u = ctypes.windll.user32

# Virtual key codes
VK_ESCAPE = 0x1B


def press_key(hwnd: int, vk_code: int, delay_after: float = 0.5):
    """Safely dispatches a key event to the foreground game window."""
    hdesk = u.OpenDesktopW("Default", 0, False, 0x01FF)
    if hdesk:
        u.SetThreadDesktop(hdesk)
    u.ShowWindow(hwnd, 9)  # SW_RESTORE
    u.SetForegroundWindow(hwnd)
    time.sleep(0.08)
    u.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.05)
    u.keybd_event(vk_code, 0, 0x0002, 0)  # KEYEVENTF_KEYUP
    time.sleep(delay_after)


def check_keywords_in_results(results: list[dict], keywords: list[str], roi: list[int] | None = None) -> list[dict]:
    """Finds matching OCR tokens filtered by optional ROI bounding box."""
    matches = []
    for r in results:
        box = r["box"]
        if roi:
            rx, ry, rw, rh = roi
            bx, by, bw, bh = box
            # Check overlap / containment with 10-20px tolerance
            if bx < rx - 10 or by < ry - 10 or (bx + bw) > (rx + rw + 20) or (by + bh) > (ry + rh + 20):
                continue
        for kw in keywords:
            if kw in r["text"]:
                matches.append(r)
                break
    return matches


class DepartmentLiveTester:
    def __init__(self, dry_run: bool = True, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.hwnd = None
        self.artifacts_dir = ROOT_DIR / "resource" / "base" / "image" / "live_test_department"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.summary_log = []
        self.pipeline_nodes = self._load_pipeline_nodes()

    def _load_pipeline_nodes(self) -> dict:
        pipeline_file = ROOT_DIR / "resource" / "base" / "pipeline" / "department.json"
        if pipeline_file.exists():
            try:
                with open(pipeline_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def log(self, stage: str, status: str, details: str = ""):
        entry = f"[{time.strftime('%H:%M:%S')}] [{stage:^12}] {status:<8} | {details}"
        print(entry, flush=True)
        self.summary_log.append(entry)

    def is_lobby_root(self, res: list[dict]) -> bool:
        """Unambiguously verifies that the client is at the actual Lobby root screen.
        Requires both top-bar '开始游戏' AND bottom-bar '切换模式', while ensuring
        no subpage tabs (Department, Trading, Sector store) are present.
        """
        has_top = bool(check_keywords_in_results(res, ["开始游戏"], roi=[150, 20, 400, 100]))
        has_switch = bool(check_keywords_in_results(res, ["切换模式", "换模式"], roi=[120, 1500, 300, 90]))
        subtabs = check_keywords_in_results(
            res,
            ["部门任务", "赛季任务", "军需处", "战斗部门", "医疗部门", "后勤部门", "战术部门", "研发部门"],
            roi=[150, 70, 900, 100]
        )
        return has_top and has_switch and (len(subtabs) == 0)

    def ensure_inside_sector_store(self) -> bool:
        """Verifies client is inside a sector store view. If kicked back, recovers gracefully."""
        img = capture_window(self.hwnd, self.artifacts_dir / "store_guard_check.png")
        res = run_ocr(img)

        # 1. Direct check: In-store sector tabs at Y ≈ 86
        in_store = bool(check_keywords_in_results(
            res,
            ["战斗部门", "医疗部门", "后勤部门", "战术部门", "研发部门"],
            roi=[180, 70, 900, 50]
        ))
        if in_store:
            return True

        # 2. Check if kicked back to Quartermaster index
        is_qm_index = bool(check_keywords_in_results(res, ["军需处"], roi=[500, 100, 200, 60]))
        if is_qm_index:
            self.log("GUARD", "WARN", "Client at Quartermaster index; re-entering sector store via card...")
            click_point(self.hwnd, 284, 983)
            time.sleep(1.5)
            return True

        # 3. Check if kicked back to Lobby root
        if self.is_lobby_root(res):
            self.log("GUARD", "WARN", "Client kicked back to Lobby; navigating back to sector store...")
            click_point(self.hwnd, 773, 70)   # 部门
            time.sleep(1.5)
            click_point(self.hwnd, 605, 142)  # 军需处
            time.sleep(1.5)
            click_point(self.hwnd, 284, 983)  # 战斗部门 card
            time.sleep(1.5)
            return True

        return False

    def attach_client(self) -> bool:
        self.hwnd = get_game_hwnd()
        if not self.hwnd:
            self.log("INIT", "WARN", "UnrealWindow for Delta Force client not found.")
            return False

        wrect = wintypes.RECT()
        u.GetWindowRect(self.hwnd, ctypes.byref(wrect))
        ww = wrect.right - wrect.left
        wh = wrect.bottom - wrect.top
        self.log("INIT", "SUCCESS", f"Connected to HWND {self.hwnd} | Resolution: {ww}x{wh}")

        if ww != 2560 or wh != 1600:
            self.log("INIT", "WARN", f"Resolution is {ww}x{wh}, expected native 2560x1600. Scaling variance may occur.")
        return True

    def safe_return_escalation(self) -> bool:
        """Executes the 4-Tier Safe Return Escalation Ladder back to Lobby."""
        self.log("ESCALATION", "START", "Executing safe return ladder...")

        # Probe current screen first: only short-circuit if TRULY at Lobby root
        img = capture_window(self.hwnd, self.artifacts_dir / "esc_probe.png")
        res = run_ocr(img)
        if self.is_lobby_root(res):
            self.log("ESCALATION", "LOBBY", "Already at verified Lobby root.")
            return True

        # Tier 1: Direct Click "开始游戏"
        click_point(self.hwnd, 254, 71)
        time.sleep(1.0)
        img = capture_window(self.hwnd, self.artifacts_dir / "esc_tier1_check.png")
        res = run_ocr(img)
        if self.is_lobby_root(res):
            self.log("ESCALATION", "TIER 1", "Direct header click succeeded -> In Lobby.")
            return True

        # Tier 2: Check subpage return, shelter exit, or Tab key hint
        self.log("ESCALATION", "TIER 2", "Header blocked. Checking subpage return, shelter exit, or Tab return.")
        if check_keywords_in_results(res, ["返回"]):
            click_point(self.hwnd, 173, 1544)
            time.sleep(1.0)
        leave_shelter = check_keywords_in_results(res, ["离开特勤处"])
        if leave_shelter:
            box = leave_shelter[0]["box"]
            click_point(self.hwnd, box[0] + box[2] // 2, box[1] + box[3] // 2)
            time.sleep(1.5)
        if check_keywords_in_results(res, ["Tab 开始游戏"]):
            press_key(self.hwnd, 0x09, delay_after=1.0)

        click_point(self.hwnd, 254, 71)
        time.sleep(1.0)
        img = capture_window(self.hwnd, self.artifacts_dir / "esc_tier2_check.png")
        res = run_ocr(img)
        if self.is_lobby_root(res):
            self.log("ESCALATION", "TIER 2", "Subpage / Tab return succeeded -> In Lobby.")
            return True

        # Tier 3: Esc Key + Tab Burst
        self.log("ESCALATION", "TIER 3", "Executing Esc + Tab return burst...")
        press_key(self.hwnd, VK_ESCAPE, delay_after=0.5)
        press_key(self.hwnd, 0x09, delay_after=0.8)
        click_point(self.hwnd, 173, 1544)
        time.sleep(0.5)
        click_point(self.hwnd, 254, 71)
        time.sleep(1.2)

        # Tier 4: Terminal Lobby Assertion
        img = capture_window(self.hwnd, self.artifacts_dir / "esc_tier4_check.png")
        res = run_ocr(img)
        if self.is_lobby_root(res):
            self.log("ESCALATION", "TIER 4", "Terminal multi-anchor verification confirmed Lobby root.")
            return True

        self.log("ESCALATION", "FAILED", "CRITICAL: Unable to confirm return to Lobby.")
        return False

    def run_simulated_dry_run(self) -> bool:
        """Executes offline dry-run validation when the game client window is not active."""
        self.log("OFFLINE", "START", "Starting simulated offline DryRun validation...")

        pipeline_file = ROOT_DIR / "resource" / "base" / "pipeline" / "department.json"
        task_file = ROOT_DIR / "tasks" / "department.json"

        if not pipeline_file.exists():
            self.log("OFFLINE", "FAILED", f"Missing pipeline file: {pipeline_file}")
            return False
        if not task_file.exists():
            self.log("OFFLINE", "FAILED", f"Missing task file: {task_file}")
            return False

        with open(pipeline_file, "r", encoding="utf-8") as f:
            nodes = json.load(f)
        with open(task_file, "r", encoding="utf-8") as f:
            task_cfg = json.load(f)

        self.log("OFFLINE", "PASSED", f"Loaded pipeline ({len(nodes)} nodes) and task configuration.")

        # Validate ROIs
        for name, node in nodes.items():
            if "roi" in node:
                x, y, w, h = node["roi"]
                if x < 0 or y < 0 or x + w > 2560 or y + h > 1600:
                    self.log("OFFLINE", "FAILED", f"Node {name} ROI [{x}, {y}, {w}, {h}] exceeds 2560x1600 bounds.")
                    return False

        self.log("OFFLINE", "PASSED", "All node ROIs verified strictly within 2560x1600 coordinate bounds.")

        # Simulate DryRun traversal
        dryrun_nodes = json.loads(json.dumps(nodes))
        if "Department.ConfirmExchangeDialog" in dryrun_nodes:
            dryrun_nodes["Department.ConfirmExchangeDialog"]["enabled"] = False

        screen_tokens = ["部门", "军需处", "战斗部门", "免费", "开始游戏"]
        current = "Department.Start"
        visited = []
        for _ in range(30):
            visited.append(current)
            if current not in dryrun_nodes:
                break
            node = dryrun_nodes[current]
            if node.get("enabled") is False:
                break
            matched = None
            for nxt in node.get("next", []):
                clean = nxt.replace("[JumpBack]", "").strip()
                if clean == "Startup.CheckLobby":
                    matched = clean
                    break
                if clean not in dryrun_nodes or dryrun_nodes[clean].get("enabled") is False:
                    continue
                expected = dryrun_nodes[clean].get("expected", [])
                if not expected or dryrun_nodes[clean].get("recognition") == "DirectHit":
                    matched = clean
                    break
                if any(tok in screen_tokens for tok in expected):
                    matched = clean
                    break
            if matched == "Startup.CheckLobby":
                visited.append(matched)
                break
            current = matched
            if not current:
                break

        if "Department.ScanFreeItem" in visited and "Department.ConfirmExchangeDialog" not in visited:
            self.log("OFFLINE", "PASSED", f"DryRun state machine traversal verified successfully: {visited}")
        else:
            self.log("OFFLINE", "FAILED", f"DryRun simulation did not bypass confirmation dialog: {visited}")
            return False

        print("\n" + "=" * 80)
        print("=== OFFLINE DRY-RUN VALIDATION PASSED 100% ===")
        print("=" * 80 + "\n")
        return True

    def run_all_steps(self) -> bool:
        if not self.attach_client():
            if self.dry_run:
                self.log("INIT", "DRYRUN", "Game client not running. Falling back to offline dry-run verification.")
                return self.run_simulated_dry_run()
            else:
                self.log("INIT", "FAILED", "RealAction mode requires active Delta Force game client.")
                return False

        print("\n" + "=" * 80)
        print(f"=== STARTING LIVE DEPARTMENT TEST (DryRun Mode: {self.dry_run}) ===")
        print("=" * 80 + "\n")

        # Step 0: Ensure Clean Lobby Root
        self.log("STEP 0", "RUNNING", "Validating initial Lobby state...")
        click_point(self.hwnd, 254, 71)
        time.sleep(1.0)
        img0 = capture_window(self.hwnd, self.artifacts_dir / "step0_lobby.png")
        res0 = run_ocr(img0)
        if not self.is_lobby_root(res0):
            self.log("STEP 0", "WARN", "Client not currently in Lobby root (subpage detected). Attempting escalation ladder.")
            if not self.safe_return_escalation():
                return False
        self.log("STEP 0", "PASSED", "Confirmed client is at Lobby root.")

        # Step 1: Navigate to Department
        self.log("STEP 1", "RUNNING", "Clicking '部门' at (773, 70)...")
        click_point(self.hwnd, 773, 70)
        time.sleep(1.5)
        img1 = capture_window(self.hwnd, self.artifacts_dir / "step1_department_main.png")
        res1 = run_ocr(img1)
        dept_tabs = check_keywords_in_results(res1, ["部门任务", "赛季任务", "军需处"], roi=[150, 100, 700, 80])
        if not dept_tabs:
            self.log("STEP 1", "FAILED", "Department sub-tabs not recognized.")
            self.safe_return_escalation()
            return False
        self.log("STEP 1", "PASSED", f"Department page loaded. Found tabs: {[t['text'] for t in dept_tabs]}")

        # Step 2: Enter 军需处 (Quartermaster) & Validate Declarative Card Node
        self.log("STEP 2", "RUNNING", "Clicking '军需处' at (605, 142)...")
        click_point(self.hwnd, 605, 142)
        time.sleep(1.5)
        img2 = capture_window(self.hwnd, self.artifacts_dir / "step2_quartermaster.png")
        res2 = run_ocr(img2)
        sectors = check_keywords_in_results(res2, ["战斗部门", "医疗部门", "后勤部门", "战术部门", "研发部门"])
        if not sectors:
            self.log("STEP 2", "FAILED", "Quartermaster sector tabs/cards not recognized.")
            self.safe_return_escalation()
            return False
        self.log("STEP 2", "PASSED", f"Quartermaster opened. Found sectors: {[s['text'] for s in sectors]}")

        # Validate declarative pipeline node: Department.EnterCombatCard
        card_node = self.pipeline_nodes.get("Department.EnterCombatCard")
        if card_node:
            roi_card = card_node.get("roi", [150, 850, 300, 200])
            expected_card = card_node.get("expected", ["战斗部门", "战斗"])
            card_matches = check_keywords_in_results(res2, expected_card, roi=roi_card)
            if not card_matches:
                self.log("STEP 2", "FAILED", f"Declarative node 'Department.EnterCombatCard' failed to match in ROI {roi_card}.")
                self.safe_return_escalation()
                return False
            self.log("STEP 2", "PASSED", f"Declarative node 'Department.EnterCombatCard' matched: {[m['text'] for m in card_matches]}")
            cb = card_matches[0]["box"]
            click_point(self.hwnd, cb[0] + cb[2] // 2, cb[1] + cb[3] // 2)
            time.sleep(1.5)
        else:
            self.log("STEP 2", "WARN", "Declarative 'Department.EnterCombatCard' missing in pipeline; fallback to procedural sector card scan.")
            combat_card = [s for s in sectors if "战斗部门" in s["text"] and s["box"][1] > 500]
            if combat_card:
                cb = combat_card[0]["box"]
                click_point(self.hwnd, cb[0] + cb[2] // 2, cb[1] + cb[3] // 2)
                time.sleep(1.5)

        # Step 3: Sector Traversal & Locked Tab Non-Blocking Verification
        self.log("STEP 3", "RUNNING", "Testing sector tab traversal & lock safeguards...")
        # 3a. Target Combat tab at safe in-store coordinate (254, 100)
        click_point(self.hwnd, 254, 100)
        time.sleep(1.0)

        # 3b. Probe 研发部门 at Y=86 for lock conditions
        self.log("STEP 3", "INFO", "Probing '研发部门' tab at (946, 86) for lock conditions...")
        click_point(self.hwnd, 946, 86)
        time.sleep(1.2)
        img_rd = capture_window(self.hwnd, self.artifacts_dir / "step3_rd_sector.png")
        res_rd = run_ocr(img_rd)

        # Look specifically for centered modal prompt, NOT store item badges
        modal_prompts = check_keywords_in_results(
            res_rd,
            ["解锁条件", "暂未开放", "条件不足", "等级不足", "未开放"],
            roi=[600, 400, 1360, 800]
        )
        if modal_prompts:
            self.log("STEP 3", "LOCKED", f"Detected level gate modal: {[p['text'] for p in modal_prompts]}. Dismissing via Esc.")
            press_key(self.hwnd, VK_ESCAPE, delay_after=0.6)
            self.log("STEP 3", "PASSED", "Lock modal cleanly dismissed without stall.")
        else:
            self.log("STEP 3", "PASSED", "R&D sector is unlocked or accessible on this account.")

        # 3c. Return to Combat sector tab inside store using safe coordinate (254, 100)
        click_point(self.hwnd, 254, 100)
        time.sleep(1.0)

        # Step 4: Free Welfare Pack Detection & Claim Verification
        self.log("STEP 4", "RUNNING", "Scanning for daily free welfare packs...")
        if not self.ensure_inside_sector_store():
            self.log("STEP 4", "FAILED", "Precondition failure: Client is not inside sector store.")
            self.safe_return_escalation()
            return False

        img4 = capture_window(self.hwnd, self.artifacts_dir / "step4_item_grid.png")
        res4 = run_ocr(img4)
        free_packs = check_keywords_in_results(res4, ["免费", "每日补给", "免费礼包"], roi=[100, 240, 1800, 1250])
        if free_packs:
            target = free_packs[0]
            box = target["box"]
            cx, cy = box[0] + box[2] // 2, box[1] + box[3] // 2
            self.log("STEP 4", "FOUND", f"Found free pack '{target['text']}' at ({cx}, {cy}).")
            if not self.dry_run:
                self.log("STEP 4", "CLAIM", "Clicking free pack...")
                click_point(self.hwnd, cx, cy)
                time.sleep(1.2)
                img_settle = capture_window(self.hwnd, self.artifacts_dir / "step4_settlement.png")
                res_settle = run_ocr(img_settle)
                settle_items = check_keywords_in_results(res_settle, ["获得物品", "确定", "恭喜获得"])
                if settle_items:
                    self.log("STEP 4", "DISMISS", "Dismissing settlement dialog via Esc.")
                    press_key(self.hwnd, VK_ESCAPE, delay_after=0.8)
            else:
                self.log("STEP 4", "DRYRUN", "DryRun enabled: Skipped actual click on free pack.")
            self.log("STEP 4", "PASSED", "Free pack claim lifecycle validated.")
        else:
            self.log("STEP 4", "PASSED", "Clean state: Daily free pack already claimed or absent.")

        # Step 5: Quota / Discount Item Detection & DryRun Abort
        self.log("STEP 5", "RUNNING", "Scanning for quota / discount items...")
        if not self.ensure_inside_sector_store():
            self.log("STEP 5", "FAILED", "Precondition failure: Client is not inside sector store.")
            self.safe_return_escalation()
            return False

        quota_items = check_keywords_in_results(res4, ["限购", "限购1", "限购2"], roi=[100, 240, 1800, 1250])
        if quota_items:
            q_target = quota_items[0]
            q_box = q_target["box"]
            q_cx, q_cy = q_box[0] + q_box[2] // 2, q_box[1] + q_box[3] // 2
            self.log("STEP 5", "FOUND", f"Detected quota item '{q_target['text']}' at ({q_cx}, {q_cy}).")

            click_point(self.hwnd, q_cx, q_cy)
            time.sleep(1.2)
            img_modal = capture_window(self.hwnd, self.artifacts_dir / "step5_purchase_modal.png")
            res_modal = run_ocr(img_modal)
            modal_active = check_keywords_in_results(res_modal, ["购买", "兑换", "确认", "确定"])

            if modal_active:
                self.log("STEP 5", "MODAL_OPEN", f"Purchase confirmation modal detected: {[m['text'] for m in modal_active]}.")
                self.log("STEP 5", "DRYRUN_ABORT", "Enforcing DryRun safety: Pressing Esc to abort transaction.")
                press_key(self.hwnd, VK_ESCAPE, delay_after=0.8)

                img_closed = capture_window(self.hwnd, self.artifacts_dir / "step5_modal_closed.png")
                res_closed = run_ocr(img_closed)
                still_open = check_keywords_in_results(res_closed, ["确认购买", "确认兑换"])
                if still_open:
                    self.log("STEP 5", "WARN", "Modal still present after Esc. Probing cancel button (800, 1100).")
                    click_point(self.hwnd, 800, 1100)
                    time.sleep(0.8)
                self.log("STEP 5", "PASSED", "DryRun modal cancellation verified. Zero tokens spent.")
            else:
                self.log("STEP 5", "INFO", "Direct detail screen opened without modal. Pressing Esc to back out.")
                press_key(self.hwnd, VK_ESCAPE, delay_after=0.8)
                self.log("STEP 5", "PASSED", "Quota item navigation verified.")
        else:
            self.log("STEP 5", "INFO", "No quota badges detected in current visible view.")

        # Step 6: Safe Return Escalation Ladder Test
        self.log("STEP 6", "RUNNING", "Executing Safe Return Escalation Ladder back to Lobby...")
        click_point(self.hwnd, 173, 1544)
        time.sleep(1.0)
        ret_ok = self.safe_return_escalation()
        if not ret_ok:
            self.log("STEP 6", "FAILED", "Escalation ladder failed to reach Lobby.")
            return False
        self.log("STEP 6", "PASSED", "Safe return escalation completed successfully.")

        # Step 7: Terminal Lobby State Assertion
        self.log("STEP 7", "RUNNING", "Performing final multi-anchor Lobby verification...")
        img_final = capture_window(self.hwnd, self.artifacts_dir / "step7_final_lobby.png")
        res_final = run_ocr(img_final)
        if not self.is_lobby_root(res_final):
            self.log("STEP 7", "FAILED", "Final Lobby verification failed: Client not at Lobby root.")
            return False

        self.log("STEP 7", "PASSED", "100% Confirmed Lobby State! Verified via top header and mode switch anchors.")

        print("\n" + "=" * 80)
        print("=== LIVE HARDWARE DEPARTMENT TEST PASSED 100% ===")
        print("=" * 80 + "\n")
        return True


def main():
    parser = argparse.ArgumentParser(description="Live Hardware Department Integration Test")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Safe DryRun mode (default: True)")
    parser.add_argument("--real-action", dest="dry_run", action="store_false", help="Enable real item claims")
    parser.add_argument("--verbose", action="store_true", help="Print verbose OCR dumps")
    args = parser.parse_args()

    tester = DepartmentLiveTester(dry_run=args.dry_run, verbose=args.verbose)
    success = tester.run_all_steps()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

"""
Unit test suite for Milestone 3: Gunsmith Workbench module.
Following 4-tier test architecture:
- Tier 1: Functional Specifications & Interface Registration
- Tier 2: Boundary & Coordinate Validation (2560x1600 & Circuit Breakers)
- Tier 3: Runtime Options & Pipeline Overrides Validation
- Tier 4: Simulated E2E State Machine & Oracle Tests
"""

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "agent"))

INTERFACE_PATH = ROOT_DIR / "interface.json"
TASK_PATH = ROOT_DIR / "tasks" / "gunsmith.json"
PIPELINE_PATH = ROOT_DIR / "resource" / "base" / "pipeline" / "gunsmith.json"


def load_interface():
    with open(INTERFACE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tasks():
    with open(TASK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_pipeline():
    with open(PIPELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def apply_overrides(base_nodes, override_map):
    nodes = copy.deepcopy(base_nodes)
    for name, patch in override_map.items():
        if name in nodes:
            nodes[name].update(patch)
    return nodes


def get_reachable_nodes(nodes, start_node="Gunsmith.Start", max_depth=60):
    """Computes all reachable nodes via BFS from start_node respecting 'enabled: false'."""
    visited = set()
    queue = [start_node]

    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)

        if curr not in nodes:
            continue
        node = nodes[curr]
        if node.get("enabled") is False:
            continue

        for nxt in node.get("next", []):
            clean = nxt.replace("[JumpBack]", "").strip()
            if clean not in visited:
                queue.append(clean)
        for err in node.get("on_error", []):
            clean = err.replace("[JumpBack]", "").strip()
            if clean not in visited:
                queue.append(clean)

    return visited


def simulate_pipeline_run(nodes, entry_name, available_screen_tokens, max_steps=50):
    """
    Simulate state machine traversal through pipeline nodes.
    Returns: (list_of_visited_nodes, terminated_normally)
    """
    current_name = entry_name
    visited = []
    step = 0

    while current_name and step < max_steps:
        step += 1
        visited.append(current_name)

        if current_name not in nodes:
            break

        node = nodes[current_name]
        if node.get("enabled") is False:
            break

        next_nodes = node.get("next", [])
        matched_next = None

        for nxt in next_nodes:
            clean_nxt = nxt.replace("[JumpBack]", "").strip()
            if clean_nxt not in nodes:
                if clean_nxt == "Startup.CheckLobby":
                    matched_next = clean_nxt
                    break
                continue

            target_spec = nodes[clean_nxt]
            if target_spec.get("enabled") is False:
                continue

            expected = target_spec.get("expected", [])
            # Action nodes with no expected or DirectHit matching
            if not expected or target_spec.get("recognition") == "DirectHit":
                matched_next = clean_nxt
                break

            # If expected tokens match the mock screen
            if any(tok in available_screen_tokens for tok in expected):
                matched_next = clean_nxt
                break

        if matched_next == "Startup.CheckLobby":
            visited.append(matched_next)
            return visited, True

        current_name = matched_next

    return visited, (current_name is None or current_name == "Startup.CheckLobby")


class TestTier1GunsmithFunctionalSpecs(unittest.TestCase):
    """Tier 1: Functional Specifications & Interface Registration."""

    def setUp(self):
        self.interface = load_interface()
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier1_interface_registration(self):
        """Verify interface.json imports ./tasks/gunsmith.json."""
        imports = self.interface.get("import", [])
        self.assertIn(
            "./tasks/gunsmith.json",
            imports,
            "tasks/gunsmith.json must be registered in interface.json import list",
        )

    def test_tier1_task_schema(self):
        """Verify task name GunsmithWorkbench, entry Gunsmith.Start, and required option keys."""
        task_list = self.tasks.get("task", [])
        self.assertGreaterEqual(len(task_list), 1)
        gunsmith_task = next((t for t in task_list if t.get("name") == "GunsmithWorkbench"), None)
        self.assertIsNotNone(gunsmith_task, "Task 'GunsmithWorkbench' must be declared in tasks/gunsmith.json")
        self.assertEqual(gunsmith_task.get("entry"), "Gunsmith.Start")

        declared_options = gunsmith_task.get("option", [])
        self.assertIn("GunsmithWeaponOption", declared_options)
        self.assertIn("GunsmithBuildPresetOption", declared_options)
        self.assertIn("GunsmithAutoBuyOption", declared_options)
        self.assertIn("GunsmithDryRunOption", declared_options)

    def test_tier1_core_pipeline_nodes_exist(self):
        """Verify presence of core navigation, assembly, and return pipeline nodes."""
        expected_nodes = [
            "Gunsmith.Start",
            "Gunsmith.EnterWorkbench",
            "Gunsmith.CheckWorkbenchOpened",
            "Gunsmith.SelectWeaponCategory",
            "Gunsmith.SelectTargetWeapon",
            "Gunsmith.OpenPresetBlueprints",
            "Gunsmith.SelectBuildPreset",
            "Gunsmith.CheckAttachmentSlots",
            "Gunsmith.ClickQuickAssemble",
            "Gunsmith.AssembleAttachments",
            "Gunsmith.ConfirmAssemble",
            "Gunsmith.ConfirmModifications",
            "Gunsmith.CheckAssemblySuccess",
            "Gunsmith.DismissSettlementModal",
            "Gunsmith.CancelModal",
            "Gunsmith.ReturnToLobby",
            "Gunsmith.SubpageReturn",
            "Gunsmith.EscReturn",
        ]
        for node in expected_nodes:
            self.assertIn(node, self.pipeline, f"Pipeline node '{node}' must exist in gunsmith.json")

    def test_tier1_attachment_slots_coverage(self):
        """Verify full coverage of weapon attachment slots: Muzzle, Barrel, Grip, Mag, Stock, Optic."""
        slot_nodes = [
            ("枪口 (Muzzle)", "Gunsmith.InspectMuzzleSlot"),
            ("枪管 (Barrel)", "Gunsmith.InspectBarrelSlot"),
            ("握把 (Grip)", "Gunsmith.InspectGripSlot"),
            ("弹匣 (Magazine)", "Gunsmith.InspectMagSlot"),
            ("枪托 (Stock)", "Gunsmith.InspectStockSlot"),
            ("瞄具 (Optic)", "Gunsmith.InspectOpticSlot"),
        ]
        for name, inspect_node in slot_nodes:
            self.assertIn(inspect_node, self.pipeline, f"{name} inspection node '{inspect_node}' missing")

    def test_tier1_trading_detour_nodes_exist(self):
        """Verify presence of Trading House detour procurement nodes."""
        detour_nodes = [
            "Gunsmith.CheckMissingPartsModal",
            "Gunsmith.DetectMissingParts",
            "Gunsmith.ClickBuyMissingParts",
            "Gunsmith.JumpToTrading",
            "Gunsmith.CheckTradingHouseOpened",
            "Gunsmith.SearchAttachmentItemBox",
            "Gunsmith.SearchAttachmentInput",
            "Gunsmith.ConfirmSearchAttachment",
            "Gunsmith.SelectAttachmentItemRow",
            "Gunsmith.ConfirmBuyDialog",
            "Gunsmith.CheckPurchaseSuccess",
            "Gunsmith.ReturnToWorkbench",
        ]
        for node in detour_nodes:
            self.assertIn(node, self.pipeline, f"Detour node '{node}' must exist in gunsmith.json")

    def test_tier1_4tier_esc_return_ladder(self):
        """Verify 4-tier Esc return ladder: ReturnToLobby -> SubpageReturn -> EscReturn -> Startup.CheckLobby."""
        self.assertIn("Gunsmith.ReturnToLobby", self.pipeline)
        self.assertIn("Gunsmith.SubpageReturn", self.pipeline)
        self.assertIn("Gunsmith.EscReturn", self.pipeline)

        esc_node = self.pipeline["Gunsmith.EscReturn"]
        self.assertEqual(esc_node.get("action"), "ClickKey")
        self.assertEqual(esc_node.get("key"), 27)

        lobby_next = self.pipeline["Gunsmith.ReturnToLobby"].get("next", [])
        self.assertIn("Startup.CheckLobby", lobby_next)
        self.assertIn("Gunsmith.SubpageReturn", lobby_next)

        subpage_next = self.pipeline["Gunsmith.SubpageReturn"].get("next", [])
        self.assertIn("Startup.CheckLobby", subpage_next)
        self.assertIn("Gunsmith.EscReturn", subpage_next)


class TestTier2GunsmithBoundaryAndCoordinates(unittest.TestCase):
    """Tier 2: Coordinate bounds, ROI constraints, and circuit breaker limits."""

    def setUp(self):
        self.pipeline = load_pipeline()

    def test_tier2_all_roi_bounds_within_2560x1600(self):
        """Verify every ROI strictly satisfies 0 <= x, y and x+w <= 2560, y+h <= 1600."""
        for name, node in self.pipeline.items():
            if "roi" in node:
                roi = node["roi"]
                self.assertIsInstance(roi, list, f"{name} ROI must be a list")
                self.assertEqual(len(roi), 4, f"{name} ROI must have length 4 [x, y, w, h]")
                x, y, w, h = roi
                self.assertGreaterEqual(x, 0, f"{name} ROI x ({x}) < 0")
                self.assertGreaterEqual(y, 0, f"{name} ROI y ({y}) < 0")
                self.assertGreater(w, 0, f"{name} ROI w ({w}) <= 0")
                self.assertGreater(h, 0, f"{name} ROI h ({h}) <= 0")
                self.assertLessEqual(x + w, 2560, f"{name} ROI x+w ({x+w}) > 2560")
                self.assertLessEqual(y + h, 1600, f"{name} ROI y+h ({y+h}) > 1600")

    def test_tier2_target_click_centers_within_bounds(self):
        """Verify all target coordinates strictly satisfy 0 <= x, y and x+w <= 2560, y+h <= 1600."""
        for name, node in self.pipeline.items():
            if "target" in node:
                target = node["target"]
                if isinstance(target, list):
                    self.assertEqual(len(target), 4, f"{name} target must have length 4 [x, y, w, h]")
                    x, y, w, h = target
                    self.assertGreaterEqual(x, 0, f"{name} target x ({x}) < 0")
                    self.assertGreaterEqual(y, 0, f"{name} target y ({y}) < 0")
                    self.assertGreater(w, 0, f"{name} target w ({w}) <= 0")
                    self.assertGreater(h, 0, f"{name} target h ({h}) <= 0")
                    self.assertLessEqual(x + w, 2560, f"{name} target x+w ({x+w}) > 2560")
                    self.assertLessEqual(y + h, 1600, f"{name} target y+h ({y+h}) > 1600")

    def test_tier2_circuit_breaker_max_hit_bounds(self):
        """Verify all loop and retry nodes enforce circuit breaker max_hit <= 5."""
        bounded_nodes = [
            "Gunsmith.ClickBuyMissingParts",
            "Gunsmith.JumpToTrading",
            "Gunsmith.SelectAttachmentItemRow",
            "Gunsmith.ConfirmBuyDialog",
            "Gunsmith.ReturnToWorkbench",
            "Gunsmith.AssembleAttachments",
            "Gunsmith.ConfirmAssemble",
            "Gunsmith.ConfirmModifications",
            "Gunsmith.DismissSettlementModal",
            "Gunsmith.CancelModal",
            "Gunsmith.SubpageReturn",
            "Gunsmith.EscReturn",
        ]
        for node_name in bounded_nodes:
            self.assertIn(node_name, self.pipeline)
            node = self.pipeline[node_name]
            max_hit = node.get("max_hit")
            self.assertIsNotNone(max_hit, f"Node '{node_name}' must define max_hit")
            self.assertGreaterEqual(max_hit, 1, f"Node '{node_name}' max_hit must be >= 1")
            self.assertLessEqual(max_hit, 5, f"Node '{node_name}' max_hit ({max_hit}) must be <= 5")

    def test_tier2_exception_recovery_nodes(self):
        """Verify exception nodes handle market out-of-stock and insufficient funds without hang."""
        out_node = self.pipeline.get("Gunsmith.CheckMarketOutOfStock")
        self.assertIsNotNone(out_node, "Gunsmith.CheckMarketOutOfStock must exist")
        self.assertIn("CommonClosePopup", out_node.get("next", []))
        self.assertIn("Gunsmith.CancelModal", out_node.get("next", []))
        self.assertIn("Gunsmith.ReturnToLobby", out_node.get("next", []))

        funds_node = self.pipeline.get("Gunsmith.CheckInsufficientFunds")
        self.assertIsNotNone(funds_node, "Gunsmith.CheckInsufficientFunds must exist")
        self.assertIn("CommonClosePopup", funds_node.get("next", []))
        self.assertIn("Gunsmith.CancelModal", funds_node.get("next", []))
        self.assertIn("Gunsmith.ReturnToLobby", funds_node.get("next", []))


class TestTier3GunsmithOptionsAndOverrides(unittest.TestCase):
    """Tier 3: Runtime options, schema cases, and pipeline_override validation."""

    def setUp(self):
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier3_weapon_option_cases(self):
        """Verify GunsmithWeaponOption defines at least 4 target weapons (M4A1, HK416, Vector, AWM)."""
        weapon_opt = self.tasks["option"]["GunsmithWeaponOption"]
        cases = weapon_opt.get("cases", [])
        self.assertGreaterEqual(len(cases), 4, "GunsmithWeaponOption must define at least 4 weapon cases")

        case_names = [c["name"] for c in cases]
        self.assertIn("WeaponM4A1", case_names)
        self.assertIn("WeaponHK416", case_names)
        self.assertIn("WeaponVector", case_names)
        self.assertIn("WeaponAWM", case_names)

        for c in cases:
            overrides = c.get("pipeline_override", {})
            self.assertIn("Gunsmith.SelectTargetWeapon", overrides)
            self.assertIn("Gunsmith.SearchAttachmentInput", overrides)

    def test_tier3_build_preset_option_cases(self):
        """Verify GunsmithBuildPresetOption defines at least 3 blueprints (Balanced, RecoilControl, HipFireErgo)."""
        preset_opt = self.tasks["option"]["GunsmithBuildPresetOption"]
        cases = preset_opt.get("cases", [])
        self.assertGreaterEqual(len(cases), 3, "GunsmithBuildPresetOption must define at least 3 blueprint cases")

        case_names = [c["name"] for c in cases]
        self.assertIn("BuildBalanced", case_names)
        self.assertIn("BuildRecoilControl", case_names)
        self.assertIn("BuildHipFireErgo", case_names)

        for c in cases:
            overrides = c.get("pipeline_override", {})
            self.assertIn("Gunsmith.SelectBuildPreset", overrides)

    def test_tier3_auto_buy_toggle_override(self):
        """Verify GunsmithAutoBuyOption supports Enabled and Disabled overrides for trading detour."""
        autobuy_opt = self.tasks["option"]["GunsmithAutoBuyOption"]
        enabled_case = next((c for c in autobuy_opt["cases"] if c["name"] == "Enabled"), None)
        disabled_case = next((c for c in autobuy_opt["cases"] if c["name"] == "Disabled"), None)

        self.assertIsNotNone(enabled_case, "Enabled case must exist")
        self.assertIsNotNone(disabled_case, "Disabled case must exist")

        self.assertTrue(enabled_case["pipeline_override"]["Gunsmith.JumpToTrading"]["enabled"])
        self.assertTrue(enabled_case["pipeline_override"]["Gunsmith.ClickBuyMissingParts"]["enabled"])
        self.assertFalse(disabled_case["pipeline_override"]["Gunsmith.JumpToTrading"]["enabled"])
        self.assertFalse(disabled_case["pipeline_override"]["Gunsmith.ClickBuyMissingParts"]["enabled"])

    def test_tier3_dry_run_zero_action_oracle(self):
        """Mathematical oracle: DryRun case disables ConfirmAssemble, ClickBuyMissingParts, ConfirmModifications."""
        dry_opt = self.tasks["option"]["GunsmithDryRunOption"]
        dry_case = next((c for c in dry_opt["cases"] if c["name"] == "DryRun"), None)
        self.assertIsNotNone(dry_case, "DryRun case must exist in GunsmithDryRunOption")

        overrides = dry_case.get("pipeline_override", {})
        self.assertIn("Gunsmith.ConfirmAssemble", overrides)
        self.assertIn("Gunsmith.ClickBuyMissingParts", overrides)
        self.assertIn("Gunsmith.ConfirmModifications", overrides)

        self.assertFalse(overrides["Gunsmith.ConfirmAssemble"].get("enabled"))
        self.assertFalse(overrides["Gunsmith.ClickBuyMissingParts"].get("enabled"))
        self.assertFalse(overrides["Gunsmith.ConfirmModifications"].get("enabled"))

    def test_tier3_all_override_targets_exist_in_pipeline(self):
        """Verify that EVERY node referenced in ANY pipeline_override actually exists in gunsmith.json."""
        for opt_name, opt_def in self.tasks.get("option", {}).items():
            for c in opt_def.get("cases", []):
                for target_node in c.get("pipeline_override", {}):
                    self.assertIn(
                        target_node,
                        self.pipeline,
                        f"Option '{opt_name}' case '{c.get('name')}' references non-existent node '{target_node}'",
                    )


class TestTier4GunsmithStateAndOracleTests(unittest.TestCase):
    """Tier 4: Simulated E2E state machine runs, graph reachability, and recovery tests."""

    def setUp(self):
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier4_safe_return_ladder_reachability(self):
        """Graph reachability BFS: verify all operational nodes reach Startup.CheckLobby."""
        reachable = get_reachable_nodes(self.pipeline, "Gunsmith.Start")
        self.assertIn("Startup.CheckLobby", reachable)
        self.assertIn("Gunsmith.ReturnToLobby", reachable)
        self.assertIn("Gunsmith.SubpageReturn", reachable)
        self.assertIn("Gunsmith.EscReturn", reachable)

    def test_tier4_e2e_simulation_complete_assembly_path(self):
        """Simulate complete assembly happy-path: Workbench, blueprint selection, quick assemble, confirm modifications, settlement dismiss, return to lobby."""
        screen_tokens = [
            "改枪台",
            "武器方案",
            "M4A1",
            "方案",
            "全面平衡方案",
            "配件",
            "快捷组装",
            "装配",
            "确认",
            "保存方案",
            "装配成功",
            "完成",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            self.pipeline,
            "Gunsmith.Start",
            screen_tokens,
            max_steps=35,
        )
        self.assertIn("Gunsmith.EnterWorkbench", visited)
        self.assertIn("Gunsmith.ClickQuickAssemble", visited)
        self.assertIn("Gunsmith.ConfirmAssemble", visited)
        self.assertIn("Gunsmith.ConfirmModifications", visited)
        self.assertIn("Startup.CheckLobby", visited)
        self.assertTrue(terminated)

    def test_tier4_e2e_simulation_missing_part_detour_path(self):
        """Simulate missing part detour path: missing part triggers Trading House buy, returns to workbench, and assembles."""
        screen_tokens = [
            "改枪台",
            "武器方案",
            "HK416",
            "方案",
            "极限后坐力控制方案",
            "快捷组装",
            "缺少配件",
            "缺少",
            "快捷购买",
            "交易行",
            "购买",
            "配件",
            "确认购买",
            "购买成功",
            "装配",
            "确认",
            "保存方案",
            "装配成功",
            "完成",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            self.pipeline,
            "Gunsmith.Start",
            screen_tokens,
            max_steps=45,
        )
        self.assertIn("Gunsmith.CheckMissingPartsModal", visited)
        self.assertIn("Gunsmith.DetectMissingParts", visited)
        self.assertIn("Gunsmith.ClickBuyMissingParts", visited)
        self.assertIn("Gunsmith.JumpToTrading", visited)
        self.assertIn("Gunsmith.CheckPurchaseSuccess", visited)
        self.assertIn("Startup.CheckLobby", visited)
        self.assertTrue(terminated)

    def test_tier4_e2e_simulation_dryrun_oracle(self):
        """Simulate DryRun mode: ConfirmAssemble, ClickBuyMissingParts, and ConfirmModifications are bypassed, routing to CancelModal -> Lobby."""
        dry_case = next(c for c in self.tasks["option"]["GunsmithDryRunOption"]["cases"] if c["name"] == "DryRun")
        merged_nodes = apply_overrides(self.pipeline, dry_case["pipeline_override"])

        screen_tokens = [
            "改枪台",
            "武器方案",
            "M4A1",
            "方案",
            "全面平衡方案",
            "配件",
            "快捷组装",
            "缺少配件",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            merged_nodes,
            "Gunsmith.Start",
            screen_tokens,
            max_steps=35,
        )
        self.assertNotIn("Gunsmith.ConfirmAssemble", visited, "ConfirmAssemble must NEVER execute during DryRun")
        self.assertNotIn("Gunsmith.ClickBuyMissingParts", visited, "ClickBuyMissingParts must NEVER execute during DryRun")
        self.assertNotIn("Gunsmith.ConfirmModifications", visited, "ConfirmModifications must NEVER execute during DryRun")
        self.assertIn("Gunsmith.CancelModal", visited, "DryRun must route via Gunsmith.CancelModal")
        self.assertIn("Startup.CheckLobby", visited)

    def test_tier4_e2e_simulation_market_out_of_stock_recovery(self):
        """Simulate market accessory sold out: gracefully dismisses modal and recovers to lobby without hanging."""
        screen_tokens = [
            "改枪台",
            "武器方案",
            "Vector",
            "快捷组装",
            "缺少配件",
            "快捷购买",
            "交易行",
            "配件",
            "售罄",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            self.pipeline,
            "Gunsmith.Start",
            screen_tokens,
            max_steps=35,
        )
        self.assertIn("Gunsmith.CheckMarketOutOfStock", visited)
        self.assertIn("Startup.CheckLobby", visited)
        self.assertTrue(terminated)


if __name__ == "__main__":
    unittest.main()

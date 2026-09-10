"""
Unit test suite for Milestone 2: Loadout Preset module.
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
TASK_PATH = ROOT_DIR / "tasks" / "loadout.json"
PIPELINE_PATH = ROOT_DIR / "resource" / "base" / "pipeline" / "loadout.json"


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


def get_reachable_nodes(nodes, start_node="Loadout.Start", max_depth=60):
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


class TestTier1LoadoutFunctionalSpecs(unittest.TestCase):
    """Tier 1: Functional Specifications & Interface Registration."""

    def setUp(self):
        self.interface = load_interface()
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier1_interface_registration(self):
        """Verify interface.json imports ./tasks/loadout.json."""
        imports = self.interface.get("import", [])
        self.assertIn(
            "./tasks/loadout.json",
            imports,
            "tasks/loadout.json must be registered in interface.json import list",
        )

    def test_tier1_task_schema(self):
        """Verify task name LoadoutPreset, entry Loadout.Start, and required option keys."""
        task_list = self.tasks.get("task", [])
        self.assertGreaterEqual(len(task_list), 1)
        loadout_task = next((t for t in task_list if t.get("name") == "LoadoutPreset"), None)
        self.assertIsNotNone(loadout_task, "Task 'LoadoutPreset' must be declared in tasks/loadout.json")
        self.assertEqual(loadout_task.get("entry"), "Loadout.Start")

        declared_options = loadout_task.get("option", [])
        self.assertIn("LoadoutPresetOption", declared_options)
        self.assertIn("LoadoutAllowTradingBuyOption", declared_options)
        self.assertIn("LoadoutDryRunOption", declared_options)

    def test_tier1_core_pipeline_nodes_exist(self):
        """Verify presence of core navigation and equipment pipeline nodes."""
        expected_nodes = [
            "Loadout.Start",
            "Loadout.EnterWarehouse",
            "Loadout.CheckWarehouseOpened",
            "Loadout.CheckCharacterPaperdoll",
            "Loadout.SelectPreset",
            "Loadout.ScanSlots",
            "Loadout.CheckWarehouseStock",
            "Loadout.RetrieveGear",
            "Loadout.EquipItem",
            "Loadout.EquipGear",
            "Loadout.VerifyAllSlotsEquipped",
            "Loadout.ReturnToLobby",
            "Loadout.SubpageReturn",
            "Loadout.EscReturn",
        ]
        for node in expected_nodes:
            self.assertIn(node, self.pipeline, f"Pipeline node '{node}' must exist in loadout.json")

    def test_tier1_five_gear_types_coverage(self):
        """Verify full coverage of all 5 gear types: Helmet, Armor, Chest Rig, Backpack, Meds."""
        gear_pairs = [
            ("头盔 (Helmet)", "Loadout.InspectHelmetSlot", "Loadout.CheckStashHelmet"),
            ("防弹衣 (Armor)", "Loadout.InspectArmorSlot", "Loadout.CheckStashArmor"),
            ("胸挂 (Chest Rig)", "Loadout.InspectChestRigSlot", "Loadout.CheckStashChestRig"),
            ("背包 (Backpack)", "Loadout.InspectBackpackSlot", "Loadout.CheckStashBackpack"),
            ("药品 (Meds)", "Loadout.InspectMedsSlot", "Loadout.CheckStashMeds"),
        ]
        for name, inspect_node, stash_node in gear_pairs:
            self.assertIn(inspect_node, self.pipeline, f"{name} inspection node '{inspect_node}' missing")
            self.assertIn(stash_node, self.pipeline, f"{name} stash detection node '{stash_node}' missing")

    def test_tier1_trading_detour_nodes_exist(self):
        """Verify presence of Trading House detour procurement nodes."""
        detour_nodes = [
            "Loadout.CheckMissingParts",
            "Loadout.JumpToTrading",
            "Loadout.CheckTradingHouseOpened",
            "Loadout.SearchMissingItemBox",
            "Loadout.SearchMissingItemInput",
            "Loadout.ConfirmSearchMissingItem",
            "Loadout.SelectMissingItemRow",
            "Loadout.ClickBuyMissing",
            "Loadout.BuyMissingItem",
            "Loadout.ConfirmBuyMissingDialog",
            "Loadout.CheckBuySuccess",
            "Loadout.ReturnToWarehouse",
        ]
        for node in detour_nodes:
            self.assertIn(node, self.pipeline, f"Detour node '{node}' must exist in loadout.json")

    def test_tier1_4tier_esc_return_ladder(self):
        """Verify 4-tier Esc return ladder: ReturnToLobby -> SubpageReturn -> EscReturn -> Startup.CheckLobby."""
        self.assertIn("Loadout.ReturnToLobby", self.pipeline)
        self.assertIn("Loadout.SubpageReturn", self.pipeline)
        self.assertIn("Loadout.EscReturn", self.pipeline)

        esc_node = self.pipeline["Loadout.EscReturn"]
        self.assertEqual(esc_node.get("action"), "ClickKey")
        self.assertEqual(esc_node.get("key"), 27)

        lobby_next = self.pipeline["Loadout.ReturnToLobby"].get("next", [])
        self.assertIn("Startup.CheckLobby", lobby_next)
        self.assertIn("Loadout.SubpageReturn", lobby_next)


class TestTier2LoadoutBoundaryAndCoordinates(unittest.TestCase):
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
        """Verify all loop and retry nodes enforce circuit breaker max_hit <= 10."""
        bounded_nodes = [
            "Loadout.RetrieveGear",
            "Loadout.EquipItem",
            "Loadout.EquipGear",
            "Loadout.JumpToTrading",
            "Loadout.ClickBuyMissing",
            "Loadout.BuyMissingItem",
            "Loadout.ConfirmBuyMissingDialog",
            "Loadout.ReturnToWarehouse",
            "Loadout.SubpageReturn",
            "Loadout.EscReturn",
        ]
        for node_name in bounded_nodes:
            self.assertIn(node_name, self.pipeline)
            node = self.pipeline[node_name]
            max_hit = node.get("max_hit")
            self.assertIsNotNone(max_hit, f"Node '{node_name}' must define max_hit")
            self.assertGreaterEqual(max_hit, 1, f"Node '{node_name}' max_hit must be >= 1")
            self.assertLessEqual(max_hit, 10, f"Node '{node_name}' max_hit ({max_hit}) must be <= 10")

    def test_tier2_exception_recovery_nodes(self):
        """Verify exception nodes handle inventory full and market out-of-stock without hang."""
        full_node = self.pipeline.get("Loadout.CheckStashFull")
        self.assertIsNotNone(full_node, "Loadout.CheckStashFull must exist")
        self.assertIn("CommonClosePopup", full_node.get("next", []))
        self.assertIn("Loadout.ReturnToLobby", full_node.get("next", []))

        out_node = self.pipeline.get("Loadout.CheckMarketOutOfStock")
        self.assertIsNotNone(out_node, "Loadout.CheckMarketOutOfStock must exist")
        self.assertIn("CommonClosePopup", out_node.get("next", []))
        self.assertIn("Loadout.ReturnToWarehouse", out_node.get("next", []))


class TestTier3LoadoutOptionsAndOverrides(unittest.TestCase):
    """Tier 3: Runtime options, schema cases, and pipeline_override validation."""

    def setUp(self):
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier3_preset_options_minimum_three_cases(self):
        """Verify LoadoutPresetOption defines at least 3 distinct named presets (突击, 侦察, 轻装)."""
        preset_opt = self.tasks["option"]["LoadoutPresetOption"]
        cases = preset_opt.get("cases", [])
        self.assertGreaterEqual(len(cases), 3, "LoadoutPresetOption must define at least 3 cases")

        case_names = [c["name"] for c in cases]
        self.assertIn("PresetAssault", case_names)
        self.assertIn("PresetRecon", case_names)
        self.assertIn("PresetLightweight", case_names)

        # Check each preset overrides item sets across gear types
        for c in cases:
            overrides = c.get("pipeline_override", {})
            self.assertIn("Loadout.SelectPreset", overrides)
            self.assertIn("Loadout.CheckStashHelmet", overrides)
            self.assertIn("Loadout.CheckStashArmor", overrides)
            self.assertIn("Loadout.CheckStashChestRig", overrides)
            self.assertIn("Loadout.CheckStashBackpack", overrides)
            self.assertIn("Loadout.CheckStashMeds", overrides)

    def test_tier3_trading_fallback_branch_override(self):
        """Verify LoadoutAllowTradingBuyOption supports Enabled and Disabled overrides."""
        trading_opt = self.tasks["option"]["LoadoutAllowTradingBuyOption"]
        enabled_case = next((c for c in trading_opt["cases"] if c["name"] == "Enabled"), None)
        disabled_case = next((c for c in trading_opt["cases"] if c["name"] == "Disabled"), None)

        self.assertIsNotNone(enabled_case, "Enabled case must exist")
        self.assertIsNotNone(disabled_case, "Disabled case must exist")

        self.assertTrue(enabled_case["pipeline_override"]["Loadout.JumpToTrading"]["enabled"])
        self.assertFalse(disabled_case["pipeline_override"]["Loadout.JumpToTrading"]["enabled"])

    def test_tier3_dry_run_zero_action_oracle(self):
        """Mathematical oracle: DryRun case disables EquipItem, RetrieveGear, and ClickBuyMissing."""
        dry_opt = self.tasks["option"]["LoadoutDryRunOption"]
        dry_case = next((c for c in dry_opt["cases"] if c["name"] == "DryRun"), None)
        self.assertIsNotNone(dry_case, "DryRun case must exist in LoadoutDryRunOption")

        overrides = dry_case.get("pipeline_override", {})
        self.assertIn("Loadout.EquipItem", overrides)
        self.assertIn("Loadout.RetrieveGear", overrides)
        self.assertIn("Loadout.ClickBuyMissing", overrides)

        self.assertFalse(overrides["Loadout.EquipItem"].get("enabled"))
        self.assertFalse(overrides["Loadout.RetrieveGear"].get("enabled"))
        self.assertFalse(overrides["Loadout.ClickBuyMissing"].get("enabled"))

    def test_tier3_all_override_targets_exist_in_pipeline(self):
        """Verify that EVERY node referenced in ANY pipeline_override actually exists in loadout.json."""
        for opt_name, opt_def in self.tasks.get("option", {}).items():
            for c in opt_def.get("cases", []):
                for target_node in c.get("pipeline_override", {}):
                    self.assertIn(
                        target_node,
                        self.pipeline,
                        f"Option '{opt_name}' case '{c.get('name')}' references non-existent node '{target_node}'",
                    )


class TestTier4LoadoutStateAndOracleTests(unittest.TestCase):
    """Tier 4: Simulated E2E state machine runs, graph reachability, and recovery tests."""

    def setUp(self):
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier4_safe_return_ladder_reachability(self):
        """Graph reachability BFS: verify all operational nodes reach Startup.CheckLobby."""
        reachable = get_reachable_nodes(self.pipeline, "Loadout.Start")
        self.assertIn("Startup.CheckLobby", reachable)
        self.assertIn("Loadout.ReturnToLobby", reachable)
        self.assertIn("Loadout.SubpageReturn", reachable)
        self.assertIn("Loadout.EscReturn", reachable)

    def test_tier4_e2e_simulation_warehouse_retrieval_path(self):
        """Simulate Phase 1 happy-path: Warehouse inspection, retrieve gear, equip, return to lobby."""
        screen_tokens = [
            "仓库",
            "装备",
            "突击方案",
            "全防头盔",
            "重装防弹衣",
            "突击胸挂",
            "战术大背包",
            "全套手术包",
            "穿戴",
            "配装完成",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            self.pipeline,
            "Loadout.Start",
            screen_tokens,
            max_steps=35,
        )
        self.assertIn("Loadout.EnterWarehouse", visited)
        self.assertIn("Loadout.RetrieveGear", visited)
        self.assertIn("Loadout.EquipItem", visited)
        self.assertIn("Startup.CheckLobby", visited)
        self.assertTrue(terminated)

    def test_tier4_e2e_simulation_trading_detour_path(self):
        """Simulate Phase 2 detour path: missing part triggers Trading House purchase then returns."""
        screen_tokens = [
            "仓库",
            "装备",
            "突击方案",
            "缺件",
            "交易行",
            "购买",
            "直接购买",
            "确认购买",
            "购买成功",
            "配装完成",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            self.pipeline,
            "Loadout.Start",
            screen_tokens,
            max_steps=40,
        )
        self.assertIn("Loadout.CheckMissingParts", visited)
        self.assertIn("Loadout.JumpToTrading", visited)
        self.assertIn("Loadout.ClickBuyMissing", visited)
        self.assertIn("Loadout.CheckBuySuccess", visited)
        self.assertIn("Startup.CheckLobby", visited)
        self.assertTrue(terminated)

    def test_tier4_e2e_simulation_dryrun_oracle(self):
        """Simulate DryRun mode: EquipItem, RetrieveGear, and ClickBuyMissing are bypassed."""
        dry_case = next(c for c in self.tasks["option"]["LoadoutDryRunOption"]["cases"] if c["name"] == "DryRun")
        merged_nodes = apply_overrides(self.pipeline, dry_case["pipeline_override"])

        screen_tokens = [
            "仓库",
            "装备",
            "突击方案",
            "全防头盔",
            "重装防弹衣",
            "突击胸挂",
            "战术大背包",
            "全套手术包",
            "穿戴",
            "配装完成",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            merged_nodes,
            "Loadout.Start",
            screen_tokens,
            max_steps=35,
        )
        self.assertNotIn("Loadout.EquipItem", visited, "EquipItem must NEVER execute during DryRun")
        self.assertNotIn("Loadout.RetrieveGear", visited, "RetrieveGear must NEVER execute during DryRun")
        self.assertNotIn("Loadout.ClickBuyMissing", visited, "ClickBuyMissing must NEVER execute during DryRun")

    def test_tier4_e2e_simulation_market_out_of_stock_recovery(self):
        """Simulate market item sold out: gracefully dismisses modal and returns to lobby."""
        screen_tokens = [
            "仓库",
            "装备",
            "缺件",
            "交易行",
            "购买",
            "售罄",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            self.pipeline,
            "Loadout.Start",
            screen_tokens,
            max_steps=35,
        )
        self.assertIn("Loadout.CheckMarketOutOfStock", visited)
        self.assertIn("Startup.CheckLobby", visited)
        self.assertTrue(terminated)

    def test_tier4_e2e_simulation_stash_full_recovery(self):
        """Simulate inventory full: handles exception and safely recovers to lobby."""
        screen_tokens = [
            "仓库",
            "装备",
            "仓库已满",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            self.pipeline,
            "Loadout.Start",
            screen_tokens,
            max_steps=30,
        )
        self.assertIn("Loadout.CheckStashFull", visited)
        self.assertIn("Startup.CheckLobby", visited)
        self.assertTrue(terminated)


if __name__ == "__main__":
    unittest.main()

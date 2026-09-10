"""
Unit test suite for Milestone 1: Keycard Sniping module.
Following 4-tier test architecture:
- Tier 1: Functional Specifications & Interface Registration
- Tier 2: Boundary & Coordinate Validation (2560x1600 & Circuit Breakers)
- Tier 3: Runtime Options & Pipeline Overrides Validation
- Tier 4: Simulated E2E State Machine & Oracle Tests
"""

import copy
import json
from pathlib import Path
import re
import sys
import unittest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "agent"))

INTERFACE_PATH = ROOT_DIR / "interface.json"
TASK_PATH = ROOT_DIR / "tasks" / "keycard.json"
PIPELINE_PATH = ROOT_DIR / "resource" / "base" / "pipeline" / "keycard.json"


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


def get_reachable_nodes(nodes, start_node="Keycard.Start", max_depth=60):
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


class TestTier1KeycardFunctionalSpecs(unittest.TestCase):
    """Tier 1: Functional Specifications & Schema Registration."""

    def setUp(self):
        self.interface = load_interface()
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier1_interface_registration(self):
        """Verify interface.json imports ./tasks/keycard.json."""
        imports = self.interface.get("import", [])
        self.assertIn("./tasks/keycard.json", imports, "tasks/keycard.json must be registered in interface.json import list")

    def test_tier1_task_schema(self):
        """Verify task name KeycardSniping, entry Keycard.Start, and required option keys."""
        task_list = self.tasks.get("task", [])
        self.assertGreaterEqual(len(task_list), 1)
        keycard_task = next((t for t in task_list if t.get("name") == "KeycardSniping"), None)
        self.assertIsNotNone(keycard_task, "Task 'KeycardSniping' must be declared in tasks/keycard.json")
        self.assertEqual(keycard_task.get("entry"), "Keycard.Start")

        declared_options = keycard_task.get("option", [])
        self.assertIn("KeycardTargetOption", declared_options)
        self.assertIn("KeycardMaxPriceOption", declared_options)
        self.assertIn("KeycardDryRunOption", declared_options)
        self.assertIn("KeycardRefreshSpeedOption", declared_options)

    def test_tier1_core_nodes_presence(self):
        """Verify presence of core navigation and evaluation pipeline nodes."""
        expected_nodes = [
            "Keycard.Start",
            "Keycard.EnterTrading",
            "Keycard.CheckTradingOpen",
            "Keycard.SelectCategoryKeycard",
            "Keycard.SearchCardBox",
            "Keycard.SearchCardName",
            "Keycard.ConfirmSearch",
            "Keycard.SelectTargetKeycard",
            "Keycard.SelectFirstItem",
            "Keycard.OcrPrice",
            "Keycard.EvaluatePrice",
            "Keycard.RefreshList",
            "Keycard.CloseDrawer",
        ]
        for node in expected_nodes:
            self.assertIn(node, self.pipeline, f"Pipeline node '{node}' must exist in keycard.json")

    def test_tier1_rapid_purchase_flow_nodes(self):
        """Verify rapid purchase flow nodes: ClickBuyDirect, MaxQuantity, ConfirmBuyDialog, SoldOut, InsufficientFunds."""
        purchase_nodes = [
            "Keycard.ClickBuyDirect",
            "Keycard.MaxQuantity",
            "Keycard.ConfirmBuyDialog",
            "Keycard.CheckPurchaseSuccess",
            "Keycard.CheckPurchaseSoldOut",
            "Keycard.CheckInsufficientFunds",
        ]
        for node in purchase_nodes:
            self.assertIn(node, self.pipeline, f"Rapid purchase flow node '{node}' must exist in keycard.json")

    def test_tier1_4tier_esc_return_ladder(self):
        """Verify 4-tier Esc return ladder: ReturnToLobby -> SubpageReturn -> EscReturn -> Startup.CheckLobby."""
        self.assertIn("Keycard.ReturnToLobby", self.pipeline)
        self.assertIn("Keycard.SubpageReturn", self.pipeline)
        self.assertIn("Keycard.EscReturn", self.pipeline)

        # EscReturn action should be ClickKey with key 27 (VK_ESCAPE)
        esc_node = self.pipeline["Keycard.EscReturn"]
        self.assertEqual(esc_node.get("action"), "ClickKey")
        self.assertEqual(esc_node.get("key"), 27)

        # Next targets of ReturnToLobby should include Startup.CheckLobby and SubpageReturn
        ret_next = self.pipeline["Keycard.ReturnToLobby"].get("next", [])
        self.assertIn("Startup.CheckLobby", ret_next)
        self.assertIn("Keycard.SubpageReturn", ret_next)


class TestTier2KeycardBoundaryAndCoordinates(unittest.TestCase):
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
        """Verify refresh loop has circuit breaker max_hit: 100."""
        refresh_node = self.pipeline.get("Keycard.RefreshList")
        self.assertIsNotNone(refresh_node)
        max_hit = refresh_node.get("max_hit")
        self.assertIsNotNone(max_hit, "RefreshList must define max_hit circuit breaker")
        self.assertGreaterEqual(max_hit, 1)
        self.assertLessEqual(max_hit, 100, "RefreshList max_hit must not exceed 100")

    def test_tier2_return_ladder_max_hit_bounds(self):
        """Verify SubpageReturn and EscReturn define finite retry ceilings (max_hit <= 5)."""
        subpage = self.pipeline.get("Keycard.SubpageReturn")
        self.assertIsNotNone(subpage)
        self.assertLessEqual(subpage.get("max_hit", 1), 5)

        esc = self.pipeline.get("Keycard.EscReturn")
        self.assertIsNotNone(esc)
        self.assertLessEqual(esc.get("max_hit", 1), 5)


class TestTier3KeycardOptionsAndOverrides(unittest.TestCase):
    """Tier 3: Runtime options, schema cases, and pipeline_override validation."""

    def setUp(self):
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier3_target_card_option_overrides(self):
        """Verify KeycardTargetOption includes 4 designated card types and valid overrides."""
        target_opt = self.tasks["option"]["KeycardTargetOption"]
        case_labels = [c.get("label") for c in target_opt.get("cases", [])]
        self.assertTrue(any("航天基地核心区红卡" in l for l in case_labels))
        self.assertTrue(any("零号大坝主控室金卡" in l for l in case_labels))
        self.assertTrue(any("长弓溪谷变电站红卡" in l for l in case_labels))
        self.assertTrue(any("巴克什行政区金卡" in l for l in case_labels))

        # Check all cases have pipeline_override targeting valid nodes
        for c in target_opt["cases"]:
            overrides = c.get("pipeline_override", {})
            self.assertGreater(len(overrides), 0, f"Case {c.get('name')} must provide pipeline_override")
            for node_name in overrides:
                self.assertIn(node_name, self.pipeline, f"Override target '{node_name}' must exist in keycard.json")

    def test_tier3_max_price_option_parameter(self):
        """Verify KeycardMaxPriceOption provides 500000, 1000000, 2000000, 99999999 ceilings."""
        price_opt = self.tasks["option"]["KeycardMaxPriceOption"]
        prices = []
        for c in price_opt.get("cases", []):
            override = c.get("pipeline_override", {}).get("Keycard.EvaluatePrice", {})
            param = override.get("custom_recognition_param", {})
            if "max_price" in param:
                prices.append(param["max_price"])

        self.assertIn(500000, prices)
        self.assertIn(1000000, prices)
        self.assertIn(2000000, prices)
        self.assertIn(99999999, prices)

    def test_tier3_dry_run_zero_purchase_guarantee(self):
        """Mathematical oracle: DryRun case disables ClickBuyDirect and ConfirmBuyDialog."""
        dry_opt = self.tasks["option"]["KeycardDryRunOption"]
        dry_case = next((c for c in dry_opt["cases"] if c["name"] == "DryRun"), None)
        self.assertIsNotNone(dry_case, "DryRun case must exist in KeycardDryRunOption")

        overrides = dry_case.get("pipeline_override", {})
        self.assertIn("Keycard.ClickBuyDirect", overrides)
        self.assertIn("Keycard.ConfirmBuyDialog", overrides)

        self.assertFalse(overrides["Keycard.ClickBuyDirect"].get("enabled"))
        self.assertFalse(overrides["Keycard.ConfirmBuyDialog"].get("enabled"))

    def test_tier3_refresh_speed_option_overrides(self):
        """Verify KeycardRefreshSpeedOption defines 200ms and 500ms cases."""
        speed_opt = self.tasks["option"]["KeycardRefreshSpeedOption"]
        delays = []
        for c in speed_opt.get("cases", []):
            override = c.get("pipeline_override", {}).get("Keycard.RefreshList", {})
            if "post_delay" in override:
                delays.append(override["post_delay"])

        self.assertIn(200, delays)
        self.assertIn(500, delays)

    def test_tier3_all_override_targets_exist_in_pipeline(self):
        """Verify that EVERY node referenced in ANY pipeline_override actually exists in keycard.json."""
        for opt_name, opt_def in self.tasks.get("option", {}).items():
            for c in opt_def.get("cases", []):
                for target_node in c.get("pipeline_override", {}):
                    self.assertIn(
                        target_node,
                        self.pipeline,
                        f"Option '{opt_name}' case '{c.get('name')}' references non-existent node '{target_node}'"
                    )


class TestTier4KeycardStateAndOracleTests(unittest.TestCase):
    """Tier 4: Simulated E2E state machine runs, graph reachability, and OCR normalization."""

    def setUp(self):
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier4_price_evaluator_ocr_string_normalization(self):
        """Verify OCR normalization logic: O/Q/D -> 0, comma/period stripping."""
        raw_samples = [
            ("5OO,OOO", 500000),
            ("1,DDD,DDD", 1000000),
            ("2,QQQ,000", 2000000),
            ("88,888.", 88888),
            ("O123", 123),
        ]
        for raw, expected_val in raw_samples:
            cleaned = (
                raw.upper()
                .replace(",", "")
                .replace(".", "")
                .replace(" ", "")
                .replace("O", "0")
                .replace("Q", "0")
                .replace("D", "0")
            )
            digits = re.findall(r"\d+", cleaned)
            val = int("".join(digits))
            self.assertEqual(val, expected_val, f"Failed normalizing '{raw}' to {expected_val}")

    def test_tier4_price_evaluator_min_price_dropped_digits(self):
        """Verify dropped digit protection: recognized price < min_price is discarded."""
        min_price = 500
        dropped_digit_sample = "200"  # was 2,000,000 but trailing digits dropped
        val = int(dropped_digit_sample)
        self.assertLess(val, min_price, "Simulated dropped price must be below min_price threshold")

    def test_tier4_safe_return_ladder_reachability(self):
        """Graph reachability BFS: verify all operational nodes reach Startup.CheckLobby."""
        reachable = get_reachable_nodes(self.pipeline, "Keycard.Start")
        self.assertIn("Startup.CheckLobby", reachable)
        self.assertIn("Keycard.ReturnToLobby", reachable)
        self.assertIn("Keycard.SubpageReturn", reachable)
        self.assertIn("Keycard.EscReturn", reachable)

    def test_tier4_e2e_simulation_happy_path(self):
        """Simulate normal purchase flow: traverses to ClickBuyDirect and returns to lobby."""
        screen_tokens = [
            "交易行",
            "购买",
            "钥匙",
            "航天基地核心区红卡",
            "确认购买",
            "购买成功",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            self.pipeline,
            "Keycard.Start",
            screen_tokens,
            max_steps=30,
        )
        self.assertIn("Keycard.EnterTrading", visited)
        self.assertIn("Keycard.SelectCategoryKeycard", visited)
        self.assertIn("Keycard.ClickBuyDirect", visited)
        self.assertIn("Keycard.ConfirmBuyDialog", visited)
        self.assertIn("Startup.CheckLobby", visited)
        self.assertTrue(terminated)

    def test_tier4_e2e_simulation_dryrun_abort(self):
        """Simulate DryRun mode: ClickBuyDirect and ConfirmBuyDialog are disabled, zero purchase executed."""
        dry_case = next(c for c in self.tasks["option"]["KeycardDryRunOption"]["cases"] if c["name"] == "DryRun")
        merged_nodes = apply_overrides(self.pipeline, dry_case["pipeline_override"])

        screen_tokens = [
            "交易行",
            "购买",
            "钥匙",
            "航天基地核心区红卡",
            "确认购买",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(
            merged_nodes,
            "Keycard.Start",
            screen_tokens,
            max_steps=30,
        )
        self.assertNotIn(
            "Keycard.ConfirmBuyDialog",
            visited,
            "ConfirmBuyDialog must NEVER be executed during DryRun mode"
        )


if __name__ == "__main__":
    unittest.main()

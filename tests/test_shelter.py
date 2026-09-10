"""
Unit test suite for Milestone 4: Shelter Maintenance module.
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
TASK_PATH = ROOT_DIR / "tasks" / "shelter.json"
PIPELINE_PATH = ROOT_DIR / "resource" / "base" / "pipeline" / "shelter.json"


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


def get_reachable_nodes(nodes, start_node="Shelter.Start", max_depth=60):
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


class TestTier1ShelterFunctionalSpecs(unittest.TestCase):
    """Tier 1: Functional Specifications & Interface Registration."""

    def setUp(self):
        self.interface = load_interface()
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier1_interface_registration(self):
        """Verify interface.json imports ./tasks/shelter.json."""
        imports = self.interface.get("import", [])
        self.assertIn(
            "./tasks/shelter.json",
            imports,
            "tasks/shelter.json must be registered in interface.json import list",
        )

    def test_tier1_task_schema(self):
        """Verify task name Shelter, entry Shelter.Start, and required options."""
        task_list = self.tasks.get("task", [])
        self.assertGreaterEqual(len(task_list), 1)
        shelter_task = next((t for t in task_list if t.get("name") == "Shelter"), None)
        self.assertIsNotNone(shelter_task, "Task 'Shelter' must be declared in tasks/shelter.json")
        self.assertEqual(shelter_task.get("entry"), "Shelter.Start")

        declared_options = shelter_task.get("option", [])
        self.assertIn("ShelterRoutineOption", declared_options)
        self.assertIn("ShelterRefuelOption", declared_options)
        self.assertIn("ShelterDryRunOption", declared_options)

    def test_tier1_core_pipeline_nodes_exist(self):
        """Verify presence of core navigation, harvest, shooting, training, refuel, and return nodes."""
        expected_nodes = [
            "Shelter.Start",
            "Shelter.EnterDepartment",
            "Shelter.CheckShelterMain",
            "Shelter.ClaimCraftedItems",
            "Shelter.EnterShootingRange",
            "Shelter.CheckDailyShootingAttempts",
            "Shelter.ShootingRangeExhaustedSkip",
            "Shelter.ExecuteTargetPractice",
            "Shelter.StartShootingRoutine",
            "Shelter.FinishShootingRoutine",
            "Shelter.ClaimShootingReward",
            "Shelter.ShootingRangeReturn",
            "Shelter.EnterTrainingCenter",
            "Shelter.InspectOperatorStatus",
            "Shelter.CheckTrainingStatus",
            "Shelter.ClaimOperatorXP",
            "Shelter.ClaimOperatorExp",
            "Shelter.DismissTrainingPopup",
            "Shelter.RestartTraining",
            "Shelter.TrainingCenterReturn",
            "Shelter.CheckGenerator",
            "Shelter.Refuel",
            "Shelter.ReturnToLobby",
            "Shelter.ReturnLobby",
            "Shelter.SubpageReturn",
            "Shelter.EscReturn",
        ]
        for node in expected_nodes:
            self.assertIn(node, self.pipeline, f"Pipeline node '{node}' must exist in shelter.json")

    def test_tier1_backward_compatibility(self):
        """Verify backward compatibility: ClaimCraftedItems, CheckGenerator, Refuel, ReturnLobby remain intact."""
        self.assertIn("Shelter.ClaimCraftedItems", self.pipeline)
        self.assertIn("Shelter.CheckGenerator", self.pipeline)
        self.assertIn("Shelter.Refuel", self.pipeline)
        self.assertIn("Shelter.ReturnLobby", self.pipeline)

        harvest_roi = self.pipeline["Shelter.ClaimCraftedItems"]["roi"]
        self.assertEqual(harvest_roi, [500, 500, 750, 200])

        generator_roi = self.pipeline["Shelter.CheckGenerator"]["roi"]
        self.assertEqual(generator_roi, [0, 200, 600, 500])

        refuel_roi = self.pipeline["Shelter.Refuel"]["roi"]
        self.assertEqual(refuel_roi, [700, 400, 550, 300])

    def test_tier1_4tier_esc_return_ladder(self):
        """Verify 4-tier Esc return ladder: ReturnToLobby -> SubpageReturn -> EscReturn -> Startup.CheckLobby."""
        self.assertIn("Shelter.ReturnToLobby", self.pipeline)
        self.assertIn("Shelter.SubpageReturn", self.pipeline)
        self.assertIn("Shelter.EscReturn", self.pipeline)

        esc_node = self.pipeline["Shelter.EscReturn"]
        self.assertEqual(esc_node.get("action"), "ClickKey")
        self.assertEqual(esc_node.get("key"), 27)

        lobby_next = self.pipeline["Shelter.ReturnToLobby"].get("next", [])
        self.assertIn("Startup.CheckLobby", lobby_next)
        self.assertIn("Shelter.SubpageReturn", lobby_next)

        subpage_next = self.pipeline["Shelter.SubpageReturn"].get("next", [])
        self.assertIn("Startup.CheckLobby", subpage_next)
        self.assertIn("Shelter.EscReturn", subpage_next)

    def test_tier1_pipeline_all_next_references_valid(self):
        """Verify all next and on_error node targets in shelter.json exist in shelter or global anchors."""
        known_global_nodes = {"CommonClosePopup", "Startup.CheckLobby"}
        shelter_nodes = set(self.pipeline.keys())

        for node_name, spec in self.pipeline.items():
            for target in spec.get("next", []):
                clean = target.replace("[JumpBack]", "").strip()
                self.assertTrue(
                    clean in shelter_nodes or clean in known_global_nodes,
                    f"Node '{node_name}' next points to undefined node '{clean}'",
                )
            for err_target in spec.get("on_error", []):
                clean = err_target.replace("[JumpBack]", "").strip()
                self.assertTrue(
                    clean in shelter_nodes or clean in known_global_nodes,
                    f"Node '{node_name}' on_error points to undefined node '{clean}'",
                )


class TestTier2ShelterBoundaryAndCoordinates(unittest.TestCase):
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

    def test_tier2_top_anchors_and_facility_coordinates(self):
        """Verify top shelter anchor and facility coordinates match native 2560x1600 spec."""
        self.assertEqual(self.pipeline["Shelter.EnterDepartment"]["roi"], [1050, 30, 140, 80])
        self.assertEqual(self.pipeline["Shelter.EnterShootingRange"]["roi"], [300, 600, 400, 200])
        self.assertEqual(self.pipeline["Shelter.EnterTrainingCenter"]["roi"], [800, 600, 400, 200])

    def test_tier2_circuit_breaker_max_hit_bounds(self):
        """Verify all loop and retry nodes enforce circuit breaker max_hit <= 5."""
        bounded_nodes = [
            "Shelter.ClaimCraftedItems",
            "Shelter.EnterShootingRange",
            "Shelter.CheckDailyShootingAttempts",
            "Shelter.ShootingRangeExhaustedSkip",
            "Shelter.ExecuteTargetPractice",
            "Shelter.StartShootingRoutine",
            "Shelter.FinishShootingRoutine",
            "Shelter.ClaimShootingReward",
            "Shelter.ShootingRangeReturn",
            "Shelter.EnterTrainingCenter",
            "Shelter.InspectOperatorStatus",
            "Shelter.CheckTrainingStatus",
            "Shelter.ClaimOperatorXP",
            "Shelter.ClaimOperatorExp",
            "Shelter.DismissTrainingPopup",
            "Shelter.RestartTraining",
            "Shelter.TrainingCenterReturn",
            "Shelter.CheckGenerator",
            "Shelter.Refuel",
            "Shelter.SubpageReturn",
            "Shelter.EscReturn",
        ]
        for node_name in bounded_nodes:
            self.assertIn(node_name, self.pipeline)
            node = self.pipeline[node_name]
            max_hit = node.get("max_hit")
            self.assertIsNotNone(max_hit, f"Node '{node_name}' must define max_hit")
            self.assertGreaterEqual(max_hit, 1, f"Node '{node_name}' max_hit must be >= 1")
            self.assertLessEqual(max_hit, 5, f"Node '{node_name}' max_hit ({max_hit}) must be <= 5")

    def test_tier2_shooting_range_daily_attempt_limit_and_exhausted_skip(self):
        """Verify daily shooting range attempt limit checking and exhausted skip routing."""
        check_node = self.pipeline["Shelter.CheckDailyShootingAttempts"]
        self.assertIn("Shelter.ExecuteTargetPractice", check_node.get("next", []))
        self.assertIn("Shelter.ShootingRangeExhaustedSkip", check_node.get("next", []))

        skip_node = self.pipeline["Shelter.ShootingRangeExhaustedSkip"]
        skip_expected = skip_node.get("expected", [])
        self.assertTrue(any("0/3" in s or "耗尽" in s or "已完成" in s for s in skip_expected))
        self.assertIn("Shelter.ShootingRangeReturn", skip_node.get("next", []))

    def test_tier2_training_center_operator_exp_claim_flow(self):
        """Verify training center operator EXP acceleration claim and popup dismissal flow."""
        enter_node = self.pipeline["Shelter.EnterTrainingCenter"]
        self.assertIn("Shelter.InspectOperatorStatus", enter_node.get("next", []))

        inspect_node = self.pipeline["Shelter.InspectOperatorStatus"]
        self.assertIn("Shelter.ClaimOperatorXP", inspect_node.get("next", []))

        claim_node = self.pipeline["Shelter.ClaimOperatorXP"]
        self.assertIn("Shelter.DismissTrainingPopup", claim_node.get("next", []))
        self.assertIn("Shelter.TrainingCenterReturn", claim_node.get("next", []))

    def test_tier2_all_action_types_valid(self):
        """Verify all action types declared in shelter.json conform to MaaFramework schema."""
        valid_actions = {
            "DoNothing",
            "Click",
            "ClickKey",
            "LongPress",
            "Swipe",
            "Scroll",
            "InputText",
            "StartApp",
            "StopApp",
            "StopTask",
            "Custom",
        }
        for name, spec in self.pipeline.items():
            action = spec.get("action")
            if action is not None:
                self.assertIn(
                    action,
                    valid_actions,
                    f"Node '{name}' declares invalid action type '{action}'",
                )


class TestTier3ShelterRuntimeOptions(unittest.TestCase):
    """Tier 3: Runtime options & pipeline override validation."""

    def setUp(self):
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()
        self.options = self.tasks.get("option", {})

    def test_tier3_routine_option_overrides(self):
        """Verify RoutineOption cases (FullRoutine, ShootingOnly, TrainingOnly, HarvestOnly)."""
        routine_opt = self.options.get("ShelterRoutineOption")
        self.assertIsNotNone(routine_opt)
        cases = {c["name"]: c for c in routine_opt.get("cases", [])}

        self.assertIn("FullRoutine", cases)
        self.assertIn("ShootingOnly", cases)
        self.assertIn("TrainingOnly", cases)
        self.assertIn("HarvestOnly", cases)

        # FullRoutine: enables all 4 facilities
        full_ov = cases["FullRoutine"]["pipeline_override"]
        self.assertTrue(full_ov["Shelter.ClaimCraftedItems"]["enabled"])
        self.assertTrue(full_ov["Shelter.EnterShootingRange"]["enabled"])
        self.assertTrue(full_ov["Shelter.EnterTrainingCenter"]["enabled"])
        self.assertTrue(full_ov["Shelter.CheckGenerator"]["enabled"])

        # ShootingOnly: enables shooting, disables others
        shoot_ov = cases["ShootingOnly"]["pipeline_override"]
        self.assertFalse(shoot_ov["Shelter.ClaimCraftedItems"]["enabled"])
        self.assertTrue(shoot_ov["Shelter.EnterShootingRange"]["enabled"])
        self.assertFalse(shoot_ov["Shelter.EnterTrainingCenter"]["enabled"])
        self.assertFalse(shoot_ov["Shelter.CheckGenerator"]["enabled"])

        # TrainingOnly: enables training, disables others
        train_ov = cases["TrainingOnly"]["pipeline_override"]
        self.assertFalse(train_ov["Shelter.ClaimCraftedItems"]["enabled"])
        self.assertFalse(train_ov["Shelter.EnterShootingRange"]["enabled"])
        self.assertTrue(train_ov["Shelter.EnterTrainingCenter"]["enabled"])
        self.assertFalse(train_ov["Shelter.CheckGenerator"]["enabled"])

        # HarvestOnly: enables harvest, disables others
        harvest_ov = cases["HarvestOnly"]["pipeline_override"]
        self.assertTrue(harvest_ov["Shelter.ClaimCraftedItems"]["enabled"])
        self.assertFalse(harvest_ov["Shelter.EnterShootingRange"]["enabled"])
        self.assertFalse(harvest_ov["Shelter.EnterTrainingCenter"]["enabled"])
        self.assertFalse(harvest_ov["Shelter.CheckGenerator"]["enabled"])

    def test_tier3_refuel_toggle_override(self):
        """Verify RefuelOption toggles generator refueling."""
        refuel_opt = self.options.get("ShelterRefuelOption")
        self.assertIsNotNone(refuel_opt)
        cases = {c["name"]: c for c in refuel_opt.get("cases", [])}

        self.assertIn("Enabled", cases)
        self.assertIn("Disabled", cases)
        self.assertTrue(cases["Enabled"]["pipeline_override"]["Shelter.Refuel"]["enabled"])
        self.assertFalse(cases["Disabled"]["pipeline_override"]["Shelter.Refuel"]["enabled"])

    def test_tier3_dry_run_zero_action_oracle(self):
        """Mathematical oracle: DryRun disables ClaimCraftedItems, Refuel, ExecuteTargetPractice, ClaimOperatorXP."""
        dryrun_opt = self.options.get("ShelterDryRunOption")
        self.assertIsNotNone(dryrun_opt)
        cases = {c["name"]: c for c in dryrun_opt.get("cases", [])}

        self.assertIn("DryRun", cases)
        self.assertIn("RealRun", cases)

        dry_ov = cases["DryRun"]["pipeline_override"]
        self.assertFalse(dry_ov["Shelter.ClaimCraftedItems"]["enabled"])
        self.assertFalse(dry_ov["Shelter.Refuel"]["enabled"])
        self.assertFalse(dry_ov["Shelter.ExecuteTargetPractice"]["enabled"])
        self.assertFalse(dry_ov["Shelter.ClaimOperatorXP"]["enabled"])

        # RealRun enables them
        real_ov = cases["RealRun"]["pipeline_override"]
        self.assertTrue(real_ov["Shelter.ClaimCraftedItems"]["enabled"])
        self.assertTrue(real_ov["Shelter.Refuel"]["enabled"])
        self.assertTrue(real_ov["Shelter.ExecuteTargetPractice"]["enabled"])
        self.assertTrue(real_ov["Shelter.ClaimOperatorXP"]["enabled"])

    def test_tier3_override_targets_exist_in_pipeline(self):
        """Verify EVERY node modified in any option's pipeline_override exists in the base pipeline."""
        for opt_name, opt_def in self.options.items():
            for case in opt_def.get("cases", []):
                for target_node in case.get("pipeline_override", {}).keys():
                    self.assertIn(
                        target_node,
                        self.pipeline,
                        f"Override target '{target_node}' from option '{opt_name}' must exist in shelter.json",
                    )


class TestTier4ShelterSimulationAndOracles(unittest.TestCase):
    """Tier 4: Graph reachability, safe return ladder, and simulated E2E runs."""

    def setUp(self):
        self.tasks = load_tasks()
        self.pipeline = load_pipeline()

    def test_tier4_safe_return_ladder_reachability(self):
        """Verify reachability of all nodes to Startup.CheckLobby."""
        terminal = "Startup.CheckLobby"
        reachable = get_reachable_nodes(self.pipeline, start_node="Shelter.Start")
        self.assertIn(terminal, reachable, "Startup.CheckLobby must be reachable from Shelter.Start")

        # Check return paths from facility exit nodes
        exit_nodes = [
            "Shelter.ShootingRangeReturn",
            "Shelter.TrainingCenterReturn",
            "Shelter.CheckGenerator",
            "Shelter.ReturnToLobby",
            "Shelter.SubpageReturn",
            "Shelter.EscReturn",
        ]
        for exit_node in exit_nodes:
            sub_reachable = get_reachable_nodes(self.pipeline, start_node=exit_node)
            self.assertIn(
                terminal,
                sub_reachable,
                f"{exit_node} must have a valid path leading to {terminal}",
            )

    def test_tier4_simulated_e2e_full_routine(self):
        """Simulate full happy path routine: Enter -> Harvest -> Shooting -> Training EXP -> Refuel -> Lobby."""
        mock_tokens = [
            "特勤处",
            "全部收获",
            "战术靶场",
            "今日挑战",
            "开始挑战",
            "训练结算",
            "领取奖励",
            "返回",
            "训练中心",
            "干员训练",
            "领取",
            "确定",
            "重新训练",
            "发电机",
            "补充燃料",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(self.pipeline, "Shelter.Start", mock_tokens)
        self.assertTrue(terminated, f"Full routine must terminate cleanly. Visited: {visited}")
        self.assertIn("Shelter.EnterDepartment", visited)
        self.assertIn("Shelter.ClaimCraftedItems", visited)
        self.assertIn("Shelter.EnterShootingRange", visited)
        self.assertIn("Shelter.ExecuteTargetPractice", visited)
        self.assertIn("Shelter.EnterTrainingCenter", visited)
        self.assertIn("Shelter.ClaimOperatorXP", visited)
        self.assertIn("Shelter.CheckGenerator", visited)
        self.assertIn("Shelter.Refuel", visited)
        self.assertIn("Startup.CheckLobby", visited)

    def test_tier4_simulated_e2e_shooting_exhausted_skip(self):
        """Simulate scenario where daily shooting attempts are exhausted (0/3); should skip to Training Center."""
        mock_tokens = [
            "特勤处",
            "战术靶场",
            "0/3",
            "今日已完成",
            "返回",
            "训练中心",
            "干员训练",
            "领取",
            "确定",
            "发电机",
            "补充燃料",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(self.pipeline, "Shelter.Start", mock_tokens)
        self.assertTrue(terminated, f"Exhausted skip routine must terminate. Visited: {visited}")
        self.assertIn("Shelter.ShootingRangeExhaustedSkip", visited)
        self.assertNotIn("Shelter.ExecuteTargetPractice", visited)
        self.assertIn("Shelter.EnterTrainingCenter", visited)
        self.assertIn("Startup.CheckLobby", visited)

    def test_tier4_simulated_e2e_dryrun_path(self):
        """Simulate DryRun mode: verify no transactional claim or practice nodes are executed."""
        dryrun_patch = self.tasks["option"]["ShelterDryRunOption"]["cases"][0]["pipeline_override"]
        dryrun_nodes = apply_overrides(self.pipeline, dryrun_patch)

        mock_tokens = [
            "特勤处",
            "全部收获",
            "战术靶场",
            "今日挑战",
            "开始挑战",
            "训练中心",
            "干员训练",
            "领取",
            "发电机",
            "补充燃料",
            "返回",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(dryrun_nodes, "Shelter.Start", mock_tokens)
        self.assertTrue(terminated, f"DryRun must terminate cleanly. Visited: {visited}")

        # Assert no disabled transactional nodes were visited
        self.assertNotIn("Shelter.ClaimCraftedItems", visited)
        self.assertNotIn("Shelter.ExecuteTargetPractice", visited)
        self.assertNotIn("Shelter.StartShootingRoutine", visited)
        self.assertNotIn("Shelter.ClaimOperatorXP", visited)
        self.assertNotIn("Shelter.Refuel", visited)
        self.assertIn("Startup.CheckLobby", visited)

    def test_tier4_simulated_e2e_shooting_only(self):
        """Simulate ShootingOnly routine: only shooting range is visited, harvest and training are skipped."""
        shooting_patch = self.tasks["option"]["ShelterRoutineOption"]["cases"][1]["pipeline_override"]
        shooting_nodes = apply_overrides(self.pipeline, shooting_patch)

        mock_tokens = [
            "特勤处",
            "战术靶场",
            "今日挑战",
            "开始挑战",
            "训练结算",
            "领取奖励",
            "返回",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(shooting_nodes, "Shelter.Start", mock_tokens)
        self.assertTrue(terminated, f"ShootingOnly routine must terminate cleanly. Visited: {visited}")
        self.assertIn("Shelter.EnterShootingRange", visited)
        self.assertIn("Shelter.ExecuteTargetPractice", visited)
        self.assertIn("Shelter.ClaimShootingReward", visited)
        self.assertNotIn("Shelter.ClaimCraftedItems", visited)
        self.assertNotIn("Shelter.EnterTrainingCenter", visited)
        self.assertNotIn("Shelter.CheckGenerator", visited)
        self.assertNotIn("Shelter.Refuel", visited)
        self.assertIn("Startup.CheckLobby", visited)

    def test_tier4_simulated_e2e_training_only(self):
        """Simulate TrainingOnly routine: only training center is visited, harvest and shooting are skipped."""
        training_patch = self.tasks["option"]["ShelterRoutineOption"]["cases"][2]["pipeline_override"]
        training_nodes = apply_overrides(self.pipeline, training_patch)

        mock_tokens = [
            "特勤处",
            "训练中心",
            "干员训练",
            "领取",
            "确定",
            "重新训练",
            "返回",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(training_nodes, "Shelter.Start", mock_tokens)
        self.assertTrue(terminated, f"TrainingOnly routine must terminate cleanly. Visited: {visited}")
        self.assertIn("Shelter.EnterTrainingCenter", visited)
        self.assertIn("Shelter.ClaimOperatorXP", visited)
        self.assertIn("Shelter.RestartTraining", visited)
        self.assertNotIn("Shelter.ClaimCraftedItems", visited)
        self.assertNotIn("Shelter.EnterShootingRange", visited)
        self.assertNotIn("Shelter.CheckGenerator", visited)
        self.assertNotIn("Shelter.Refuel", visited)
        self.assertIn("Startup.CheckLobby", visited)

    def test_tier4_simulated_e2e_harvest_only(self):
        """Simulate HarvestOnly routine: only harvest is visited, shooting and training are skipped."""
        harvest_patch = self.tasks["option"]["ShelterRoutineOption"]["cases"][3]["pipeline_override"]
        harvest_nodes = apply_overrides(self.pipeline, harvest_patch)

        mock_tokens = [
            "特勤处",
            "全部收获",
            "返回",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(harvest_nodes, "Shelter.Start", mock_tokens)
        self.assertTrue(terminated, f"HarvestOnly routine must terminate cleanly. Visited: {visited}")
        self.assertIn("Shelter.ClaimCraftedItems", visited)
        self.assertNotIn("Shelter.EnterShootingRange", visited)
        self.assertNotIn("Shelter.EnterTrainingCenter", visited)
        self.assertNotIn("Shelter.CheckGenerator", visited)
        self.assertNotIn("Shelter.Refuel", visited)
        self.assertIn("Startup.CheckLobby", visited)

    def test_tier4_simulated_e2e_refuel_disabled(self):
        """Simulate Refuel Disabled routine: generator refuel action is not executed."""
        refuel_patch = self.tasks["option"]["ShelterRefuelOption"]["cases"][1]["pipeline_override"]
        refuel_disabled_nodes = apply_overrides(self.pipeline, refuel_patch)

        mock_tokens = [
            "特勤处",
            "全部收获",
            "战术靶场",
            "今日挑战",
            "开始挑战",
            "训练结算",
            "领取奖励",
            "返回",
            "训练中心",
            "干员训练",
            "领取",
            "确定",
            "重新训练",
            "发电机",
            "补充燃料",
            "开始游戏",
        ]
        visited, terminated = simulate_pipeline_run(refuel_disabled_nodes, "Shelter.Start", mock_tokens)
        self.assertTrue(terminated, f"Refuel disabled routine must terminate cleanly. Visited: {visited}")
        self.assertNotIn("Shelter.Refuel", visited)
        self.assertIn("Startup.CheckLobby", visited)


if __name__ == "__main__":
    unittest.main()

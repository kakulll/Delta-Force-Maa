"""
Adversarial Stress Test Suite for Delta-Force-Maa Shelter Maintenance Module.
Written by challenger_shelter_1 to empirically probe edge cases, failure modes,
and verify invariants under stress.
"""

import copy
import json
from pathlib import Path
import random
import sys
import unittest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

INTERFACE_PATH = ROOT_DIR / "interface.json"
TASK_PATH = ROOT_DIR / "tasks" / "shelter.json"
PIPELINE_PATH = ROOT_DIR / "resource" / "base" / "pipeline" / "shelter.json"
ALL_PIPELINES_DIR = ROOT_DIR / "resource" / "base" / "pipeline"


def load_all_pipeline_nodes():
    all_nodes = {}
    for p in ALL_PIPELINES_DIR.glob("*.json"):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in data.items():
                all_nodes[k] = v
    return all_nodes


def load_shelter_pipeline():
    with open(PIPELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_shelter_tasks():
    with open(TASK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def apply_overrides(base_nodes, *override_maps):
    nodes = copy.deepcopy(base_nodes)
    for omap in override_maps:
        for name, patch in omap.items():
            if name in nodes:
                nodes[name].update(patch)
    return nodes


def simulate_run_extended(nodes, entry_name, token_generator_fn, max_steps=100):
    """
    Step-by-step state machine runner using dynamic token generation per step.
    Returns (visited_nodes, terminated_normally)
    """
    current_name = entry_name
    visited = []
    step = 0

    while current_name and step < max_steps:
        step += 1
        visited.append(current_name)

        if current_name == "Startup.CheckLobby":
            return visited, True

        if current_name not in nodes:
            # If external known terminal
            if current_name.startswith("Startup.") or current_name == "CommonClosePopup":
                return visited, True
            return visited, False

        node = nodes[current_name]
        if node.get("enabled") is False:
            return visited, False

        screen_tokens = token_generator_fn(current_name, step)

        next_nodes = node.get("next", [])
        matched = None

        for nxt in next_nodes:
            clean = nxt.replace("[JumpBack]", "").strip()
            if clean not in nodes:
                if clean == "Startup.CheckLobby":
                    matched = clean
                    break
                continue

            target_spec = nodes[clean]
            if target_spec.get("enabled") is False:
                continue

            expected = target_spec.get("expected", [])
            # Action nodes with no expected or DirectHit
            if not expected or target_spec.get("recognition") == "DirectHit":
                matched = clean
                break

            if any(tok in screen_tokens for tok in expected):
                matched = clean
                break

        current_name = matched

    return visited, (current_name is None or current_name == "Startup.CheckLobby")


class TestAdversarialShelterIntegrity(unittest.TestCase):
    """Deep structural and integrity tests."""

    def setUp(self):
        self.shelter = load_shelter_pipeline()
        self.all_nodes = load_all_pipeline_nodes()
        self.tasks = load_shelter_tasks()

    def test_adv_zero_dangling_pointers_across_entire_repo(self):
        """Every target in 'next' and 'on_error' must resolve to an existing node in the repo."""
        for name, spec in self.shelter.items():
            for target in spec.get("next", []):
                clean = target.replace("[JumpBack]", "").strip()
                self.assertIn(
                    clean,
                    self.all_nodes,
                    f"Dangling pointer found: node '{name}' references non-existent '{clean}' in next",
                )
            for err in spec.get("on_error", []):
                clean = err.replace("[JumpBack]", "").strip()
                self.assertIn(
                    clean,
                    self.all_nodes,
                    f"Dangling pointer found: node '{name}' references non-existent '{clean}' in on_error",
                )

    def test_adv_topological_dag_and_no_unbounded_cycles(self):
        """Empirically prove that shelter.json forms a DAG with 0 internal cycles."""
        adj = {}
        in_degree = {k: 0 for k in self.shelter}
        for name, spec in self.shelter.items():
            adj[name] = [
                t.replace("[JumpBack]", "").strip()
                for t in spec.get("next", [])
                if t.replace("[JumpBack]", "").strip() in self.shelter
            ]

        for name, nxts in adj.items():
            for nxt in nxts:
                in_degree[nxt] += 1

        queue = [k for k, v in in_degree.items() if v == 0]
        visited_count = 0
        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for nxt in adj[curr]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        self.assertEqual(
            visited_count,
            len(self.shelter),
            "shelter.json must be a strict DAG without unhandled recursive cycles",
        )

    def test_adv_strict_coordinate_canvas_boundaries(self):
        """Verify strict non-degenerate 2560x1600 canvas coordinate bounds."""
        for name, spec in self.shelter.items():
            roi = spec.get("roi")
            if roi is not None:
                self.assertEqual(len(roi), 4, f"{name}: ROI must have 4 elements [x, y, w, h]")
                x, y, w, h = roi
                self.assertGreaterEqual(x, 0, f"{name}: x ({x}) < 0")
                self.assertGreaterEqual(y, 0, f"{name}: y ({y}) < 0")
                self.assertGreaterEqual(w, 50, f"{name}: width ({w}) suspiciously small (< 50)")
                self.assertGreaterEqual(h, 30, f"{name}: height ({h}) suspiciously small (< 30)")
                self.assertLessEqual(x + w, 2560, f"{name}: right edge ({x+w}) exceeds 2560")
                self.assertLessEqual(y + h, 1600, f"{name}: bottom edge ({y+h}) exceeds 1600")


class TestAdversarialShootingRangeExhausted(unittest.TestCase):
    """Stress tests specifically targeting the 0/3 daily shooting attempts exhausted logic."""

    def setUp(self):
        self.shelter = load_shelter_pipeline()
        self.tasks = load_shelter_tasks()

    def test_adv_exhausted_token_variants(self):
        """Test all textual variations of 0/3 attempt exhaustion cleanly transition to ShootingRangeReturn."""
        exhausted_markers = [
            "0/3",
            "今日已完成",
            "次数耗尽",
            "明日再来",
            "剩余次数: 0",
        ]
        for marker in exhausted_markers:
            tokens = [
                "特勤处",
                "战术靶场",
                marker,
                "返回",
                "训练中心",
                "干员训练",
                "领取",
                "确定",
                "发电机",
                "补充燃料",
                "开始游戏",
            ]
            visited, term = simulate_run_extended(
                self.shelter, "Shelter.Start", lambda n, s, t=tokens: t
            )
            self.assertTrue(term, f"Marker '{marker}' failed to terminate cleanly. Visited: {visited}")
            self.assertIn(
                "Shelter.ShootingRangeExhaustedSkip",
                visited,
                f"Marker '{marker}' should have triggered ShootingRangeExhaustedSkip",
            )
            self.assertNotIn(
                "Shelter.ExecuteTargetPractice",
                visited,
                f"Marker '{marker}' should NOT have executed TargetPractice",
            )
            self.assertIn("Shelter.EnterTrainingCenter", visited)
            self.assertIn("Startup.CheckLobby", visited)

    def test_adv_exhausted_when_check_attempts_matched_first(self):
        """When screen has '今日挑战' and '剩余次数' alongside '0/3', verify clean skip without infinite loop."""
        tokens = [
            "特勤处",
            "战术靶场",
            "今日挑战",
            "剩余次数",
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
        visited, term = simulate_run_extended(
            self.shelter, "Shelter.Start", lambda n, s: tokens
        )
        self.assertTrue(term, f"Combined tokens run failed to terminate. Visited: {visited}")
        self.assertIn("Shelter.CheckDailyShootingAttempts", visited)
        self.assertIn("Shelter.ShootingRangeExhaustedSkip", visited)
        self.assertIn("Shelter.ShootingRangeReturn", visited)
        self.assertIn("Startup.CheckLobby", visited)

    def test_adv_exhausted_when_button_text_retained(self):
        """Adversarial scenario: button retains disabled '开始挑战' text. Verify execution safely falls through to return."""
        tokens = [
            "特勤处",
            "战术靶场",
            "今日挑战",
            "开始挑战",  # Disabled button visible
            "0/3",
            "返回",
            "训练中心",
            "干员训练",
            "开始游戏",
        ]
        visited, term = simulate_run_extended(
            self.shelter, "Shelter.Start", lambda n, s: tokens
        )
        self.assertTrue(term, f"Disabled button scenario failed to terminate. Visited: {visited}")
        self.assertIn("Shelter.ShootingRangeReturn", visited)
        self.assertIn("Startup.CheckLobby", visited)

    def test_adv_shooting_only_with_0_3_exhausted(self):
        """In ShootingOnly mode, exhausting 0/3 attempts must directly return to lobby."""
        shooting_patch = self.tasks["option"]["ShelterRoutineOption"]["cases"][1]["pipeline_override"]
        shooting_nodes = apply_overrides(self.shelter, shooting_patch)

        tokens = [
            "特勤处",
            "战术靶场",
            "0/3",
            "今日已完成",
            "返回",
            "开始游戏",
        ]
        visited, term = simulate_run_extended(
            shooting_nodes, "Shelter.Start", lambda n, s: tokens
        )
        self.assertTrue(term, f"ShootingOnly + 0/3 failed. Visited: {visited}")
        self.assertIn("Shelter.ShootingRangeExhaustedSkip", visited)
        self.assertNotIn("Shelter.EnterTrainingCenter", visited)
        self.assertNotIn("Shelter.CheckGenerator", visited)
        self.assertIn("Shelter.ReturnToLobby", visited)
        self.assertIn("Startup.CheckLobby", visited)


class TestAdversarialOptionCombinatorics(unittest.TestCase):
    """Stress tests all 16 permutations of routine options, refuel options, and dryrun options."""

    def setUp(self):
        self.shelter = load_shelter_pipeline()
        self.tasks = load_shelter_tasks()

    def test_adv_all_16_option_combinations_reach_lobby(self):
        """Verify that every single permutation in the 4x2x2 option space terminates cleanly at Startup.CheckLobby."""
        routine_cases = self.tasks["option"]["ShelterRoutineOption"]["cases"]
        refuel_cases = self.tasks["option"]["ShelterRefuelOption"]["cases"]
        dryrun_cases = self.tasks["option"]["ShelterDryRunOption"]["cases"]

        full_token_pool = [
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

        combos_tested = 0
        for r_case in routine_cases:
            for f_case in refuel_cases:
                for d_case in dryrun_cases:
                    combos_tested += 1
                    r_ov = r_case.get("pipeline_override", {})
                    f_ov = f_case.get("pipeline_override", {})
                    d_ov = d_case.get("pipeline_override", {})

                    configured_nodes = apply_overrides(self.shelter, r_ov, f_ov, d_ov)

                    visited, terminated = simulate_run_extended(
                        configured_nodes,
                        "Shelter.Start",
                        lambda n, s: full_token_pool,
                    )

                    self.assertTrue(
                        terminated,
                        f"Combo ({r_case['name']}, {f_case['name']}, {d_case['name']}) failed to terminate. Visited: {visited}",
                    )
                    self.assertIn(
                        "Startup.CheckLobby",
                        visited,
                        f"Combo ({r_case['name']}, {f_case['name']}, {d_case['name']}) did not reach lobby",
                    )

                    # In DryRun mode, verify strict zero-transaction invariant
                    if d_case["name"] == "DryRun":
                        self.assertNotIn("Shelter.ClaimCraftedItems", visited)
                        self.assertNotIn("Shelter.ExecuteTargetPractice", visited)
                        self.assertNotIn("Shelter.ClaimOperatorXP", visited)
                        self.assertNotIn("Shelter.Refuel", visited)

        self.assertEqual(combos_tested, 16, "Must test exactly 4x2x2 = 16 combinations")


class TestAdversarialFuzzingAndResilience(unittest.TestCase):
    """Fuzzing and stochastic stress testing for unhandled crashes or stalls."""

    def setUp(self):
        self.shelter = load_shelter_pipeline()

    def test_adv_stochastic_empty_and_corrupt_tokens(self):
        """Under completely blank or corrupted screen OCR, pipeline must gracefully abort without infinite loop."""
        garbage_token_sets = [
            [],  # Empty screen
            ["UnknownToken123", "ErrorDialog", "Loading"],  # Noise
            ["SomeRandomGarbage"],
        ]

        for garbage in garbage_token_sets:
            visited, terminated = simulate_run_extended(
                self.shelter,
                "Shelter.Start",
                lambda n, s, g=garbage: g,
                max_steps=50,
            )
            self.assertLess(
                len(visited),
                50,
                f"Garbage tokens {garbage} caused infinite loop! Visited: {visited}",
            )


if __name__ == "__main__":
    unittest.main()

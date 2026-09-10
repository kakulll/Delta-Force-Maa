"""
Unit test suite for Milestone 1: Tactical Budget Backpack Planner (6-Slot MCKP DP Solver).
Following 4-tier test architecture:
- Tier 1: Functional Specifications & Discrete DP 6-Slot Feasibility
- Tier 2: Boundary Budgets & Exception Handling (Exact Fit, Zero Budget, Insufficiency)
- Tier 3: Stash Inventory Priority Allocation (0 Effective Cost Heuristic)
- Tier 4: Execution Performance Benchmarks (<50ms) & Large Catalog Stress Tests
"""

from __future__ import annotations

from pathlib import Path
import sys
import time
from typing import Dict, List
import unittest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "agent"))

from agent.algorithm.loadout_planner import (
    GearItem,
    InsufficientBudgetError,
    LoadoutPlan,
    LoadoutPlanner,
    SlotType,
)


def make_standard_catalog() -> List[GearItem]:
    """Generates a realistic multi-tier market catalog across all 6 slots."""
    items = []
    # HELMET
    items.append(GearItem("h_t3", "T3 战术轻盔", SlotType.HELMET, market_price=15_000, utility=30.0))
    items.append(GearItem("h_t4", "T4 凯夫拉头盔", SlotType.HELMET, market_price=45_000, utility=55.0))
    items.append(GearItem("h_t5", "T5 重装复合头盔", SlotType.HELMET, market_price=110_000, utility=80.0))
    items.append(GearItem("h_t6", "T6 泰坦防弹头盔", SlotType.HELMET, market_price=260_000, utility=135.0))

    # ARMOR
    items.append(GearItem("a_t3", "T3 轻型防弹衣", SlotType.ARMOR, market_price=20_000, utility=35.0))
    items.append(GearItem("a_t4", "T4 突击防弹衣", SlotType.ARMOR, market_price=60_000, utility=95.0))
    items.append(GearItem("a_t5", "T5 全防护插板甲", SlotType.ARMOR, market_price=150_000, utility=145.0))
    items.append(GearItem("a_t6", "T6 重型陶瓷装甲", SlotType.ARMOR, market_price=350_000, utility=210.0))

    # CHEST_RIG
    items.append(GearItem("cr_12", "12格轻型胸挂", SlotType.CHEST_RIG, market_price=8_000, utility=25.0))
    items.append(GearItem("cr_16", "16格战术胸挂", SlotType.CHEST_RIG, market_price=22_000, utility=40.0))
    items.append(GearItem("cr_20", "20格特种胸挂", SlotType.CHEST_RIG, market_price=55_000, utility=55.0))
    items.append(GearItem("cr_24", "24格重型突击挂", SlotType.CHEST_RIG, market_price=120_000, utility=70.0))

    # BACKPACK
    items.append(GearItem("bp_16", "16格突击背包", SlotType.BACKPACK, market_price=10_000, utility=28.0))
    items.append(GearItem("bp_22", "22格野战背包", SlotType.BACKPACK, market_price=28_000, utility=42.0))
    items.append(GearItem("bp_28", "28格战术背包", SlotType.BACKPACK, market_price=70_000, utility=56.0))
    items.append(GearItem("bp_35", "35格大型远征包", SlotType.BACKPACK, market_price=160_000, utility=70.0))

    # MEDS
    items.append(GearItem("m_basic", "基础急救药品包", SlotType.MEDS, market_price=5_000, utility=20.0))
    items.append(GearItem("m_tactical", "战术医疗组合", SlotType.MEDS, market_price=15_000, utility=35.0))
    items.append(GearItem("m_advanced", "全套手术与高阶针剂", SlotType.MEDS, market_price=35_000, utility=50.0))

    # AMMO
    items.append(GearItem("ammo_t3", "T3 穿甲弹 (90发)", SlotType.AMMO, market_price=12_000, utility=30.0))
    items.append(GearItem("ammo_t4", "T4 紫色特种弹 (120发)", SlotType.AMMO, market_price=40_000, utility=55.0))
    items.append(GearItem("ammo_t5", "T5 金色高穿弹 (120发)", SlotType.AMMO, market_price=120_000, utility=85.0))
    items.append(GearItem("ammo_t6", "T6 顶级钨芯穿甲弹 (180发)", SlotType.AMMO, market_price=280_000, utility=150.0))

    return items


class TestTier1LoadoutDPSolver(unittest.TestCase):
    """Tier 1: Functional specifications & discrete DP 6-slot feasibility."""

    def setUp(self):
        self.planner = LoadoutPlanner()
        self.market_items = make_standard_catalog()

    def test_tier1_six_slots_completeness_requirement(self):
        """Any successful loadout plan must equip exactly 6 slots."""
        plan = self.planner.solve_optimal_loadout(
            budget=300_000,
            stash_inventory=[],
            available_market_items=self.market_items,
        )
        self.assertEqual(len(plan.equipped_items), 6)
        expected_slots = {
            SlotType.HELMET,
            SlotType.ARMOR,
            SlotType.CHEST_RIG,
            SlotType.BACKPACK,
            SlotType.MEDS,
            SlotType.AMMO,
        }
        self.assertEqual(set(plan.equipped_items.keys()), expected_slots)

    def test_tier1_dp_solve_100k_budget(self):
        """Solves optimal loadout within 100k Hafe coins budget."""
        budget = 100_000
        plan = self.planner.solve_optimal_loadout(
            budget=budget,
            stash_inventory=[],
            available_market_items=self.market_items,
        )
        self.assertLessEqual(plan.actual_cash_expenditure, budget)
        self.assertEqual(len(plan.equipped_items), 6)
        # Verify utility is non-trivial (e.g. at least basic set = 30+35+25+28+20+30 = 168)
        self.assertGreaterEqual(plan.total_utility, 168.0)

    def test_tier1_dp_solve_300k_budget(self):
        """Solves optimal loadout within 300k Hafe coins budget."""
        plan_100k = self.planner.solve_optimal_loadout(100_000, [], self.market_items)
        plan_300k = self.planner.solve_optimal_loadout(300_000, [], self.market_items)

        self.assertLessEqual(plan_300k.actual_cash_expenditure, 300_000)
        # Higher budget must yield strictly higher utility
        self.assertGreater(plan_300k.total_utility, plan_100k.total_utility)
        # 300k budget should equip at least T4 armor and T4 helmet
        self.assertIn(plan_300k.equipped_items[SlotType.ARMOR].item_id, ["a_t4", "a_t5"])

    def test_tier1_dp_solve_1m_budget(self):
        """Solves optimal loadout within 1,000,000 Hafe coins budget."""
        plan_300k = self.planner.solve_optimal_loadout(300_000, [], self.market_items)
        plan_1m = self.planner.solve_optimal_loadout(1_000_000, [], self.market_items)

        self.assertLessEqual(plan_1m.actual_cash_expenditure, 1_000_000)
        self.assertGreater(plan_1m.total_utility, plan_300k.total_utility)
        # 1M budget should equip top-tier items (T6 helmet, T6 armor, T6 ammo)
        self.assertEqual(plan_1m.equipped_items[SlotType.HELMET].item_id, "h_t6")
        self.assertEqual(plan_1m.equipped_items[SlotType.ARMOR].item_id, "a_t6")
        self.assertEqual(plan_1m.equipped_items[SlotType.AMMO].item_id, "ammo_t6")

    def test_tier1_discretization_step_accuracy(self):
        """Discretization step (1000) must accurately compute cash expenditure."""
        plan = self.planner.solve_optimal_loadout(
            budget=200_000,
            stash_inventory=[],
            available_market_items=self.market_items,
            discretization_step=1_000,
        )
        # Re-sum exact item prices
        exact_sum = sum(item.effective_cost for item in plan.equipped_items.values())
        self.assertEqual(plan.actual_cash_expenditure, exact_sum)
        self.assertLessEqual(plan.actual_cash_expenditure, 200_000)


class TestTier2BoundaryBudgets(unittest.TestCase):
    """Tier 2: Boundary budgets, exact fit, insufficiency exceptions, and zero budgets."""

    def setUp(self):
        self.planner = LoadoutPlanner()
        self.market_items = make_standard_catalog()

    def test_tier2_exact_budget_fit(self):
        """Available cheapest items sum up to 70k (15+20+8+10+5+12 = 70k). Exact budget must succeed."""
        cheapest_sum = 15_000 + 20_000 + 8_000 + 10_000 + 5_000 + 12_000
        plan = self.planner.solve_optimal_loadout(
            budget=cheapest_sum,
            stash_inventory=[],
            available_market_items=self.market_items,
        )
        self.assertEqual(plan.actual_cash_expenditure, cheapest_sum)
        self.assertEqual(len(plan.equipped_items), 6)

    def test_tier2_insufficient_budget_exception(self):
        """Budget below cheapest 6-slot sum (70k) must raise InsufficientBudgetError."""
        with self.assertRaises(InsufficientBudgetError) as cm:
            self.planner.solve_optimal_loadout(
                budget=50_000,  # 50k < 70k minimum
                stash_inventory=[],
                available_market_items=self.market_items,
            )
        self.assertIn("Insufficient budget", str(cm.exception))

    def test_tier2_zero_budget_with_empty_stash(self):
        """Zero budget with empty stash must raise InsufficientBudgetError."""
        with self.assertRaises(InsufficientBudgetError):
            self.planner.solve_optimal_loadout(0, [], self.market_items)

    def test_tier2_zero_budget_with_full_stash(self):
        """Zero budget with complete 6-slot stash inventory must succeed with 0 cash expenditure."""
        stash = [
            GearItem("s_h", "仓库头盔", SlotType.HELMET, market_price=50_000, in_stash=True, utility=60.0),
            GearItem("s_a", "仓库防弹衣", SlotType.ARMOR, market_price=70_000, in_stash=True, utility=65.0),
            GearItem("s_cr", "仓库胸挂", SlotType.CHEST_RIG, market_price=20_000, in_stash=True, utility=40.0),
            GearItem("s_bp", "仓库背包", SlotType.BACKPACK, market_price=25_000, in_stash=True, utility=45.0),
            GearItem("s_m", "仓库药品", SlotType.MEDS, market_price=10_000, in_stash=True, utility=30.0),
            GearItem("s_ammo", "仓库弹药", SlotType.AMMO, market_price=30_000, in_stash=True, utility=50.0),
        ]
        plan = self.planner.solve_optimal_loadout(0, stash, self.market_items)
        self.assertEqual(plan.actual_cash_expenditure, 0)
        self.assertEqual(plan.stash_items_count, 6)
        self.assertEqual(plan.purchased_items_count, 0)
        self.assertEqual(len(plan.equipped_items), 6)

    def test_tier2_ultra_high_budget_saturation(self):
        """10,000,000 budget selects highest utility items without memory exhaustion or loops."""
        plan = self.planner.solve_optimal_loadout(10_000_000, [], self.market_items)
        self.assertEqual(len(plan.equipped_items), 6)
        self.assertEqual(plan.equipped_items[SlotType.HELMET].item_id, "h_t6")
        self.assertEqual(plan.equipped_items[SlotType.ARMOR].item_id, "a_t6")
        self.assertEqual(plan.equipped_items[SlotType.CHEST_RIG].item_id, "cr_24")
        self.assertEqual(plan.equipped_items[SlotType.BACKPACK].item_id, "bp_35")
        self.assertEqual(plan.equipped_items[SlotType.MEDS].item_id, "m_advanced")
        self.assertEqual(plan.equipped_items[SlotType.AMMO].item_id, "ammo_t6")

    def test_tier2_single_item_per_slot_monopoly(self):
        """Catalog containing exactly 1 item per slot within budget must trivially equip all 6."""
        minimal_catalog = [
            GearItem("m1", "H1", SlotType.HELMET, 10_000, utility=10.0),
            GearItem("m2", "A1", SlotType.ARMOR, 10_000, utility=10.0),
            GearItem("m3", "C1", SlotType.CHEST_RIG, 10_000, utility=10.0),
            GearItem("m4", "B1", SlotType.BACKPACK, 10_000, utility=10.0),
            GearItem("m5", "M1", SlotType.MEDS, 10_000, utility=10.0),
            GearItem("m6", "AM1", SlotType.AMMO, 10_000, utility=10.0),
        ]
        plan = self.planner.solve_optimal_loadout(60_000, [], minimal_catalog)
        self.assertEqual(plan.actual_cash_expenditure, 60_000)
        self.assertEqual(len(plan.equipped_items), 6)


class TestTier3StashPriority(unittest.TestCase):
    """Tier 3: Stash inventory priority allocation (0 marginal cost heuristic)."""

    def setUp(self):
        self.planner = LoadoutPlanner()
        self.market_items = make_standard_catalog()

    def test_tier3_stash_high_tier_zero_cost_priority(self):
        """Tier 6 helmet in stash (cost 0, utility 95) must be chosen over purchasing T3 helmet on 100k budget."""
        stash_t6_helmet = GearItem(
            item_id="stash_h_t6",
            name="仓库顶级T6头盔",
            slot=SlotType.HELMET,
            market_price=260_000,
            in_stash=True,
            utility=95.0,
        )
        plan = self.planner.solve_optimal_loadout(
            budget=100_000,
            stash_inventory=[stash_t6_helmet],
            available_market_items=self.market_items,
        )
        # Must equip stash helmet
        equipped_helmet = plan.equipped_items[SlotType.HELMET]
        self.assertEqual(equipped_helmet.item_id, "stash_h_t6")
        self.assertTrue(equipped_helmet.in_stash)
        self.assertEqual(equipped_helmet.effective_cost, 0)
        # Because helmet cost 0, the remaining 100k budget is used to buy higher tier armor (e.g. T4 armor)
        equipped_armor = plan.equipped_items[SlotType.ARMOR]
        self.assertEqual(equipped_armor.item_id, "a_t4")

    def test_tier3_stash_partial_coverage(self):
        """Stash provides 3 slots (Helmet, Armor, Backpack); market supplies remaining 3 slots."""
        stash = [
            GearItem("s_h", "仓库存盔", SlotType.HELMET, 50_000, in_stash=True, utility=60.0),
            GearItem("s_a", "仓库存甲", SlotType.ARMOR, 80_000, in_stash=True, utility=70.0),
            GearItem("s_bp", "仓库存包", SlotType.BACKPACK, 30_000, in_stash=True, utility=50.0),
        ]
        plan = self.planner.solve_optimal_loadout(100_000, stash, self.market_items)
        self.assertEqual(plan.stash_items_count, 3)
        self.assertEqual(plan.purchased_items_count, 3)
        self.assertEqual(len(plan.equipped_items), 6)
        # Cash is spent only on purchased items
        purchased_cost = sum(
            item.effective_cost for item in plan.equipped_items.values() if not item.in_stash
        )
        self.assertEqual(plan.actual_cash_expenditure, purchased_cost)
        self.assertLessEqual(plan.actual_cash_expenditure, 100_000)

    def test_tier3_stash_vs_market_upgrade_decision(self):
        """Planner upgrades low-tier stash gear when budget surplus exists and higher utility is achievable."""
        # Low utility meds in stash (utility 5, cost 0)
        low_stash_meds = GearItem("s_m_low", "破旧急救包", SlotType.MEDS, 2_000, in_stash=True, utility=5.0)
        # With huge budget (1M), planner should upgrade to m_advanced (utility 80, cost 35k)
        plan_rich = self.planner.solve_optimal_loadout(1_000_000, [low_stash_meds], self.market_items)
        self.assertEqual(plan_rich.equipped_items[SlotType.MEDS].item_id, "m_advanced")

        # But with tight budget (70k), planner should retain the stash meds to afford basic armor/ammo
        tight_catalog = [
            GearItem("h", "H", SlotType.HELMET, 15_000, utility=20.0),
            GearItem("a", "A", SlotType.ARMOR, 20_000, utility=20.0),
            GearItem("cr", "CR", SlotType.CHEST_RIG, 10_000, utility=20.0),
            GearItem("bp", "BP", SlotType.BACKPACK, 10_000, utility=20.0),
            GearItem("med_market", "M", SlotType.MEDS, 10_000, utility=25.0),
            GearItem("am", "AM", SlotType.AMMO, 15_000, utility=20.0),
        ]
        # Total cost with market meds = 15+20+10+10+10+15 = 80k. Budget is 70k.
        # With stash meds (cost 0), total = 70k -> feasible!
        plan_tight = self.planner.solve_optimal_loadout(70_000, [low_stash_meds], tight_catalog)
        self.assertEqual(plan_tight.equipped_items[SlotType.MEDS].item_id, "s_m_low")

    def test_tier3_stash_duplicate_items_selection(self):
        """When stash has two items for the same slot, planner selects the higher utility item."""
        stash = [
            GearItem("s_a_t4", "仓库T4甲", SlotType.ARMOR, 60_000, in_stash=True, utility=60.0),
            GearItem("s_a_t5", "仓库T5甲", SlotType.ARMOR, 150_000, in_stash=True, utility=85.0),
        ]
        plan = self.planner.solve_optimal_loadout(200_000, stash, self.market_items)
        self.assertEqual(plan.equipped_items[SlotType.ARMOR].item_id, "s_a_t5")

    def test_tier3_accounting_integrity(self):
        """Mathematical integrity check: total_market_value == actual_cash + sum(stash market prices)."""
        stash = [
            GearItem("s_h", "仓库盔", SlotType.HELMET, 45_000, in_stash=True, utility=55.0),
            GearItem("s_bp", "仓库包", SlotType.BACKPACK, 28_000, in_stash=True, utility=52.0),
        ]
        plan = self.planner.solve_optimal_loadout(150_000, stash, self.market_items)
        stash_value = sum(
            item.market_price for item in plan.equipped_items.values() if item.in_stash
        )
        self.assertEqual(plan.total_market_value, plan.actual_cash_expenditure + stash_value)
        self.assertEqual(plan.stash_items_count + plan.purchased_items_count, 6)


class TestTier4PerformanceAndStress(unittest.TestCase):
    """Tier 4: Execution performance benchmarks (<50ms) and large catalog stress tests."""

    def setUp(self):
        self.planner = LoadoutPlanner()
        self.market_items = make_standard_catalog()

    def test_tier4_performance_single_solve_under_50ms(self):
        """Single solve across 100k, 300k, 1M budgets must execute in < 50ms (target < 5ms)."""
        budgets = [100_000, 300_000, 1_000_000]
        for b in budgets:
            with self.subTest(budget=b):
                start = time.perf_counter()
                plan = self.planner.solve_optimal_loadout(b, [], self.market_items)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                self.assertLess(elapsed_ms, 50.0, f"Solve took {elapsed_ms:.2f}ms, expected < 50ms")
                self.assertEqual(len(plan.equipped_items), 6)

    def test_tier4_performance_100_consecutive_solves_benchmark(self):
        """100 consecutive solves must complete in < 0.50s (average < 5ms per solve)."""
        start = time.perf_counter()
        for i in range(100):
            b = 100_000 + (i % 9) * 100_000
            self.planner.solve_optimal_loadout(b, [], self.market_items)
        total_time = time.perf_counter() - start
        avg_ms = (total_time / 100.0) * 1000.0
        self.assertLess(total_time, 0.50, f"100 solves took {total_time:.3f}s (avg {avg_ms:.2f}ms/solve)")

    def test_tier4_stress_large_candidate_catalog(self):
        """Stress test with 25 candidate items per slot (25^6 = 244 million combinations)."""
        large_catalog = []
        for slot in SlotType:
            for i in range(1, 26):
                price = i * 15_000
                utility = float(i * 4)
                large_catalog.append(
                    GearItem(f"{slot.value}_{i}", f"Item_{slot.value}_{i}", slot, price, utility=utility)
                )

        start = time.perf_counter()
        plan = self.planner.solve_optimal_loadout(500_000, [], large_catalog)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.assertLess(elapsed_ms, 100.0, f"Large catalog solve took {elapsed_ms:.2f}ms, expected < 100ms")
        self.assertEqual(len(plan.equipped_items), 6)
        self.assertLessEqual(plan.actual_cash_expenditure, 500_000)

    def test_tier4_deterministic_solution_oracle(self):
        """10 repeated executions with identical inputs must produce bit-identical plans."""
        results = []
        for _ in range(10):
            plan = self.planner.solve_optimal_loadout(250_000, [], self.market_items)
            equipped_tuple = tuple(sorted(
                (slot.value, item.item_id, item.effective_cost)
                for slot, item in plan.equipped_items.items()
            ))
            results.append((plan.actual_cash_expenditure, plan.total_utility, equipped_tuple))

        # All 10 must be identical to the first
        first = results[0]
        for idx, res in enumerate(results[1:], start=2):
            self.assertEqual(res, first, f"Run #{idx} produced non-deterministic output!")


if __name__ == "__main__":
    unittest.main()

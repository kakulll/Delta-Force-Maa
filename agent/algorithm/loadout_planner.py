"""Tactical Budget Loadout Planner for Delta-Force-Maa.

Solves the 6-Slot Multi-Choice Knapsack Problem (MCKP) with discrete Dynamic Programming.
Supports 100k / 300k / 1M budget tiers, 0-cost stash inventory reuse, and Pareto pruning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


class SlotType(str, Enum):
    """The 6 standard tactical gear slots in Delta Force."""
    HELMET = "helmet"          # 头盔
    ARMOR = "armor"            # 防弹衣 / 护甲
    CHEST_RIG = "chest_rig"    # 战术胸挂
    BACKPACK = "backpack"      # 战术背包
    MEDS = "meds"              # 战救医疗包 / 手术组
    AMMO = "ammo"              # 备用穿甲弹药组


class BudgetTier(int, Enum):
    """Standard preset budget limits in Hafe currency."""
    LOW = 100_000       # 10万 哈夫币 (经济跑刀 / 低保过渡)
    MEDIUM = 300_000    # 30万 哈夫币 (标准排位 / 均衡攻守)
    HIGH = 1_000_000    # 100万 哈夫币 (顶级要塞 / 豪华重装)


class InsufficientBudgetError(ValueError):
    """Raised when available budget cannot equip all 6 required tactical slots."""
    pass


@dataclass
class GearItem:
    """Tactical gear item definition.

    Attributes:
        item_id: Unique identifier.
        name: In-game display name.
        slot: Target slot type.
        market_price: Baseline market purchase price in Hafe coins.
        in_stash: Whether player currently possesses this item in warehouse inventory.
        utility: Evaluated combat utility score.
        tier: Equipment level / grade (e.g. 1 to 6).
        quantity: Bundled count.
        metadata: Optional dictionary for game-specific properties.
    """
    item_id: str
    name: str
    slot: SlotType
    market_price: int
    in_stash: bool = False
    utility: float = 0.0
    tier: int = 0
    quantity: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.market_price < 0:
            raise ValueError(f"Item market_price cannot be negative: {self.market_price}")
        if self.utility < 0:
            raise ValueError(f"Item utility cannot be negative: {self.utility}")

    @property
    def cost(self) -> int:
        return self.market_price

    @property
    def effective_cost(self) -> int:
        return 0 if self.in_stash else self.market_price


@dataclass
class Item:
    """Tactical gear item definition matching m1_explorer_2 interface."""
    name: str
    slot: SlotType
    cost: int
    utility: float
    in_stash: bool = False
    item_id: str = ""
    tier: int = 0
    quantity: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.item_id:
            self.item_id = self.name
        if self.cost < 0:
            raise ValueError(f"Item cost cannot be negative: {self.cost}")
        if self.utility < 0:
            raise ValueError(f"Item utility cannot be negative: {self.utility}")

    @property
    def market_price(self) -> int:
        return self.cost

    @property
    def effective_cost(self) -> int:
        return 0 if self.in_stash else self.cost


@dataclass
class LoadoutPlan:
    """Comprehensive result returned by the MCKP loadout planner."""
    budget_limit: int
    total_market_value: int
    actual_cash_expenditure: int
    equipped_items: Dict[SlotType, Any]
    stash_items_count: int
    purchased_items_count: int
    total_utility: float
    is_feasible: bool = True
    missing_slots: List[SlotType] = field(default_factory=list)
    scaled_cost: int = 0
    details: str = ""

    # Compatibility properties for LoadoutSolution interface
    @property
    def budget(self) -> int:
        return self.budget_limit

    @property
    def total_effective_cost(self) -> int:
        return self.actual_cash_expenditure

    @property
    def total_cost(self) -> int:
        return self.actual_cash_expenditure

    @property
    def items(self) -> Dict[SlotType, Any]:
        return self.equipped_items

    @property
    def stash_count(self) -> int:
        return self.stash_items_count

    @property
    def purchase_count(self) -> int:
        return self.purchased_items_count

    def get_item(self, slot: SlotType) -> Optional[Any]:
        return self.equipped_items.get(slot)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget": self.budget_limit,
            "total_effective_cost": self.actual_cash_expenditure,
            "total_market_value": self.total_market_value,
            "total_utility": round(self.total_utility, 3),
            "is_feasible": self.is_feasible,
            "stash_count": self.stash_items_count,
            "purchase_count": self.purchased_items_count,
            "missing_slots": [s.value for s in self.missing_slots],
            "scaled_cost": self.scaled_cost,
            "details": self.details,
            "items": {
                slot.value: {
                    "item_id": getattr(item, "item_id", item.name),
                    "name": item.name,
                    "cost": getattr(item, "cost", item.market_price),
                    "effective_cost": item.effective_cost,
                    "utility": round(item.utility, 3),
                    "in_stash": item.in_stash,
                    "tier": getattr(item, "tier", 0),
                    "quantity": getattr(item, "quantity", 1),
                }
                for slot, item in self.equipped_items.items()
            },
        }


# Alias for backward compatibility
LoadoutSolution = LoadoutPlan


def get_default_market_items() -> List[Item]:
    """Returns standard baseline market catalog across all 6 slots."""
    return [
        # Slot 1: HELMET
        Item("基础轻便头盔", SlotType.HELMET, cost=15_000, utility=35.0, tier=3),
        Item("战术侦察头盔", SlotType.HELMET, cost=55_000, utility=60.0, tier=4),
        Item("全防头盔", SlotType.HELMET, cost=140_000, utility=82.0, tier=5),
        Item("重装全防头盔", SlotType.HELMET, cost=280_000, utility=96.0, tier=6),

        # Slot 2: BODY ARMOR
        Item("经济防弹衣", SlotType.ARMOR, cost=20_000, utility=36.0, tier=3),
        Item("高机动防弹衣", SlotType.ARMOR, cost=70_000, utility=62.0, tier=4),
        Item("重装防弹衣", SlotType.ARMOR, cost=180_000, utility=85.0, tier=5),
        Item("突击复合防弹衣", SlotType.ARMOR, cost=350_000, utility=98.0, tier=6),

        # Slot 3: CHEST RIG
        Item("便携胸挂", SlotType.CHEST_RIG, cost=12_000, utility=30.0, tier=3),
        Item("侦察胸挂", SlotType.CHEST_RIG, cost=40_000, utility=55.0, tier=4),
        Item("突击胸挂", SlotType.CHEST_RIG, cost=95_000, utility=78.0, tier=5),
        Item("重型战术胸挂", SlotType.CHEST_RIG, cost=180_000, utility=92.0, tier=6),

        # Slot 4: BACKPACK
        Item("便携小背包", SlotType.BACKPACK, cost=10_000, utility=28.0, tier=3),
        Item("中型战术背包", SlotType.BACKPACK, cost=35_000, utility=52.0, tier=4),
        Item("战术大背包", SlotType.BACKPACK, cost=85_000, utility=75.0, tier=5),
        Item("军用野战巨包", SlotType.BACKPACK, cost=160_000, utility=90.0, tier=6),

        # Slot 5: MEDICAL BUNDLE
        Item("简易急救包组", SlotType.MEDS, cost=8_000, utility=25.0, tier=3),
        Item("敏捷急救医疗组", SlotType.MEDS, cost=25_000, utility=50.0, tier=4),
        Item("全套高阶手术医疗组", SlotType.MEDS, cost=65_000, utility=76.0, tier=5),
        Item("军用综合自救与兴奋剂组", SlotType.MEDS, cost=120_000, utility=92.0, tier=6),

        # Slot 6: AMMUNITION BUNDLE
        Item("5.56x45mm M855 常规弹", SlotType.AMMO, cost=15_000, utility=30.0, tier=3, quantity=90),
        Item("5.56x45mm M855A1 穿甲弹", SlotType.AMMO, cost=60_000, utility=58.0, tier=4, quantity=120),
        Item("5.56x45mm M995 高穿金弹", SlotType.AMMO, cost=150_000, utility=84.0, tier=5, quantity=120),
        Item("7.62x51mm M61 顶级钨芯弹", SlotType.AMMO, cost=280_000, utility=98.0, tier=6, quantity=120),
    ]


class LoadoutPlanner:
    """Multi-Choice Knapsack Problem (MCKP) Dynamic Programming Solver."""

    ALL_SLOTS: List[SlotType] = [
        SlotType.HELMET,
        SlotType.ARMOR,
        SlotType.CHEST_RIG,
        SlotType.BACKPACK,
        SlotType.MEDS,
        SlotType.AMMO,
    ]

    def __init__(self, default_step: int = 1000, stash_tie_bonus: float = 1e-4):
        self.default_step = default_step
        self.stash_tie_bonus = stash_tie_bonus

    def _filter_pareto_candidates(self, items: List[Any], step: int) -> List[Tuple[Any, int, float]]:
        """Filters candidate items for a single slot using Pareto efficiency."""
        # Sort items deterministically: effective_cost asc, utility desc, stash first
        sorted_items = sorted(
            items,
            key=lambda it: (
                it.effective_cost,
                -it.utility,
                0 if it.in_stash else 1,
                getattr(it, "item_id", it.name),
            ),
        )

        pareto: List[Tuple[Any, int, float]] = []
        max_u_seen = -1.0
        seen_costs: Dict[int, float] = {}

        for it in sorted_items:
            eff_cost = it.effective_cost
            scaled_w = 0 if eff_cost == 0 else (eff_cost + step - 1) // step
            eff_u = it.utility + (self.stash_tie_bonus if it.in_stash else 0.0)

            # Skip items with same effective cost but lower utility
            if eff_cost in seen_costs and eff_u <= seen_costs[eff_cost]:
                continue
            seen_costs[eff_cost] = eff_u

            # If higher cost doesn't yield higher utility, it is dominated
            if eff_u > max_u_seen:
                pareto.append((it, scaled_w, eff_u))
                max_u_seen = eff_u
            elif it.in_stash and pareto and pareto[-1][0].effective_cost == eff_cost:
                # Stash item replaces market item of identical cost
                pareto[-1] = (it, scaled_w, eff_u)

        return pareto

    def solve_optimal_loadout(
        self,
        budget: int,
        stash_inventory: Optional[Sequence[Any]] = None,
        available_market_items: Optional[Sequence[Any]] = None,
        step: Optional[int] = None,
        discretization_step: Optional[int] = None,
        raise_on_insufficient: bool = True,
    ) -> LoadoutPlan:
        """Solves the 6-slot MCKP optimization problem."""
        stash = list(stash_inventory) if stash_inventory is not None else []
        market = list(available_market_items) if available_market_items is not None else get_default_market_items()

        step_val = discretization_step if discretization_step is not None else (step if step is not None else self.default_step)
        if step_val <= 0:
            step_val = 1000

        # 1. Bucket candidates by slot
        slot_candidates: Dict[SlotType, List[Any]] = {s: [] for s in self.ALL_SLOTS}

        for it in stash:
            if it.slot in slot_candidates:
                # Ensure in_stash is True for items from stash_inventory
                if not it.in_stash:
                    if isinstance(it, GearItem):
                        it = GearItem(
                            item_id=it.item_id,
                            name=it.name,
                            slot=it.slot,
                            market_price=it.market_price,
                            in_stash=True,
                            utility=it.utility,
                            tier=it.tier,
                            quantity=it.quantity,
                            metadata=it.metadata,
                        )
                    else:
                        it = Item(
                            name=it.name,
                            slot=it.slot,
                            cost=it.cost,
                            utility=it.utility,
                            in_stash=True,
                            item_id=getattr(it, "item_id", it.name),
                            tier=getattr(it, "tier", 0),
                            quantity=getattr(it, "quantity", 1),
                            metadata=getattr(it, "metadata", {}),
                        )
                slot_candidates[it.slot].append(it)

        for it in market:
            if it.slot in slot_candidates:
                slot_candidates[it.slot].append(it)

        # Check for missing slots
        missing = [s for s in self.ALL_SLOTS if len(slot_candidates[s]) == 0]
        if missing:
            err_msg = f"Insufficient budget or candidates: Missing items for slots: {[s.value for s in missing]}"
            if raise_on_insufficient:
                raise InsufficientBudgetError(err_msg)
            return LoadoutPlan(
                budget_limit=budget,
                total_market_value=0,
                actual_cash_expenditure=0,
                equipped_items={},
                stash_items_count=0,
                purchased_items_count=0,
                total_utility=0.0,
                is_feasible=False,
                missing_slots=missing,
                details=err_msg,
            )

        # Check theoretical minimum cost across all 6 slots
        min_possible_cash = sum(
            min(it.effective_cost for it in slot_candidates[s]) for s in self.ALL_SLOTS
        )
        if budget < min_possible_cash:
            err_msg = f"Insufficient budget: {budget:,} is less than minimum required cost {min_possible_cash:,}."
            if raise_on_insufficient:
                raise InsufficientBudgetError(err_msg)

        # 2. Pareto filter each slot
        pareto_by_slot: Dict[SlotType, List[Tuple[Any, int, float]]] = {}
        for s in self.ALL_SLOTS:
            pareto_by_slot[s] = self._filter_pareto_candidates(slot_candidates[s], step_val)

        # 3. Dynamic Programming Table
        # Cap w_max by theoretical maximum expenditure to avoid unbounded allocation
        max_possible_cash = sum(
            max(item.effective_cost for item, _, _ in pareto_by_slot[s]) for s in self.ALL_SLOTS
        )
        w_max = max(0, min(budget, max_possible_cash) // step_val)

        num_stages = len(self.ALL_SLOTS)
        dp: List[Dict[int, Tuple[float, int]]] = [{} for _ in range(num_stages + 1)]
        parent: List[Dict[int, Tuple[Any, int]]] = [{} for _ in range(num_stages + 1)]

        dp[0][0] = (0.0, 0)

        for s_idx, slot in enumerate(self.ALL_SLOTS):
            curr_stage = s_idx + 1
            candidates = pareto_by_slot[slot]
            prev_dp = dp[s_idx]

            for prev_w, (prev_u, prev_cash) in prev_dp.items():
                for item, item_sw, item_u in candidates:
                    new_w = prev_w + item_sw
                    if new_w > w_max:
                        continue

                    new_cash = prev_cash + item.effective_cost
                    if new_cash > budget:
                        continue

                    new_u = prev_u + item_u

                    if new_w not in dp[curr_stage]:
                        dp[curr_stage][new_w] = (new_u, new_cash)
                        parent[curr_stage][new_w] = (item, prev_w)
                    else:
                        cur_u, cur_cash = dp[curr_stage][new_w]
                        if new_u > cur_u or (abs(new_u - cur_u) < 1e-6 and new_cash < cur_cash):
                            dp[curr_stage][new_w] = (new_u, new_cash)
                            parent[curr_stage][new_w] = (item, prev_w)

        # 4. Check if final stage reached
        final_dp = dp[num_stages]
        if not final_dp:
            err_msg = f"Insufficient budget: budget {budget:,} cannot equip all 6 slots."
            if raise_on_insufficient:
                raise InsufficientBudgetError(err_msg)

            # Infeasible fallback: cheapest available combination
            fallback_items: Dict[SlotType, Any] = {}
            min_cash = 0
            for slot in self.ALL_SLOTS:
                cheapest = min(slot_candidates[slot], key=lambda it: (it.effective_cost, -it.utility))
                fallback_items[slot] = cheapest
                min_cash += cheapest.effective_cost

            total_mv = sum(getattr(it, "market_price", getattr(it, "cost", 0)) for it in fallback_items.values())
            total_u = sum(it.utility for it in fallback_items.values())
            stash_cnt = sum(1 for it in fallback_items.values() if it.in_stash)
            return LoadoutPlan(
                budget_limit=budget,
                total_market_value=total_mv,
                actual_cash_expenditure=min_cash,
                equipped_items=fallback_items,
                stash_items_count=stash_cnt,
                purchased_items_count=len(fallback_items) - stash_cnt,
                total_utility=total_u,
                is_feasible=False,
                missing_slots=[],
                details=err_msg,
            )

        # 5. Extract optimal state
        best_w = None
        best_u = -1.0
        best_cash = float("inf")

        # Sort keys deterministically
        for w in sorted(final_dp.keys()):
            u, cash = final_dp[w]
            if u > best_u or (abs(u - best_u) < 1e-6 and cash < best_cash):
                best_u = u
                best_cash = cash
                best_w = w

        # Backtrack items
        equipped: Dict[SlotType, Any] = {}
        curr_w = best_w
        for s_idx in range(num_stages, 0, -1):
            slot = self.ALL_SLOTS[s_idx - 1]
            chosen_item, prev_w = parent[s_idx][curr_w]
            equipped[slot] = chosen_item
            curr_w = prev_w

        actual_cash = sum(it.effective_cost for it in equipped.values())
        total_market = sum(getattr(it, "market_price", getattr(it, "cost", 0)) for it in equipped.values())
        total_u = sum(it.utility for it in equipped.values())
        stash_cnt = sum(1 for it in equipped.values() if it.in_stash)
        purchased_cnt = len(equipped) - stash_cnt

        return LoadoutPlan(
            budget_limit=budget,
            total_market_value=total_market,
            actual_cash_expenditure=actual_cash,
            equipped_items=equipped,
            stash_items_count=stash_cnt,
            purchased_items_count=purchased_cnt,
            total_utility=total_u,
            is_feasible=True,
            scaled_cost=best_w or 0,
            details=f"Optimal solution found: {stash_cnt} stash items, {purchased_cnt} market purchases. Total expenditure: {actual_cash:,}/{budget:,} Hafe.",
        )

    def solve_tier(
        self,
        tier: Union[BudgetTier, str, int],
        stash_inventory: Optional[Sequence[Any]] = None,
        market_items: Optional[Sequence[Any]] = None,
    ) -> LoadoutPlan:
        """Convenience wrapper for standard budget tiers."""
        if isinstance(tier, BudgetTier):
            budget = tier.value
        elif isinstance(tier, str):
            t_str = tier.upper()
            if "100" in t_str or "LOW" in t_str:
                budget = BudgetTier.LOW.value
            elif "300" in t_str or "MED" in t_str:
                budget = BudgetTier.MEDIUM.value
            elif "1M" in t_str or "HIGH" in t_str or "1000" in t_str:
                budget = BudgetTier.HIGH.value
            else:
                budget = int(tier)
        else:
            budget = int(tier)

        return self.solve_optimal_loadout(budget, stash_inventory, market_items)

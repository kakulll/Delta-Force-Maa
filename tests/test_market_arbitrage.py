"""
Unit test suite for Milestone 1: Market Arbitrage & Dynamic Pricing Solver.
Following 4-tier test architecture:
- Tier 1: Functional Specifications & Base Fee Calculations
- Tier 2: Dynamic Pricing & OCR Text Cleaning Robustness
- Tier 3: Floor Price Protection & Anti-Misbuy Bounds
- Tier 4: Simulated E2E PriceEvaluator Recognition Oracles
"""

from __future__ import annotations

import math
from pathlib import Path
import sys
from typing import Any, Optional
import unittest
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "agent"))

from agent.algorithm.market_arbitrage import (
    ArbitrageDecision,
    DynamicPricingEngine,
    FloorProtectionBounds,
    OcrTextCleaner,
    TradingFeeModel,
)
from agent.custom.reco.price_evaluator import PriceEvaluator


class TestTier1FeeModelAndBreakEven(unittest.TestCase):
    """Tier 1: Fee calculations, VIP discounts, minimum listing fee ($100), break-even ceilings."""

    def setUp(self):
        self.model = TradingFeeModel()

    def test_tier1_base_tax_standard_rate(self):
        """Standard tax rate must be 12% (0.12)."""
        test_cases = [
            (10_000, 1_200),
            (50_000, 6_000),
            (100_000, 12_000),
            (1_000_000, 120_000),
            (1_250, 150),
        ]
        for sale_price, expected_tax in test_cases:
            with self.subTest(sale_price=sale_price):
                actual_tax = self.model.calc_tax(sale_price, is_vip=False)
                self.assertEqual(actual_tax, expected_tax)

    def test_tier1_vip_privilege_tax_discount(self):
        """VIP discount reduces effective tax rate to 10% (0.10)."""
        test_cases = [
            (10_000, 1_000),
            (50_000, 5_000),
            (100_000, 10_000),
            (1_000_000, 100_000),
            (1_250, 125),
        ]
        for sale_price, expected_tax in test_cases:
            with self.subTest(sale_price=sale_price):
                actual_tax = self.model.calc_tax(sale_price, is_vip=True)
                self.assertEqual(actual_tax, expected_tax)

    def test_tier1_minimum_listing_fee_boundary(self):
        """Listing fee is max(100, floor(price * 0.01)). Floor at 100 applies up to 10,000."""
        test_cases = [
            (500, 100),       # 5 < 100 -> 100
            (5_000, 100),     # 50 < 100 -> 100
            (9_999, 100),     # 99 < 100 -> 100
            (10_000, 100),    # exactly 100
            (10_100, 101),    # 101 > 100 -> 101
            (50_000, 500),    # 500
            (100_000, 1_000), # 1,000
            (2_000_000, 20_000),
        ]
        for sale_price, expected_fee in test_cases:
            with self.subTest(sale_price=sale_price):
                actual_fee = self.model.calc_listing_fee(sale_price)
                self.assertEqual(actual_fee, expected_fee)

    def test_tier1_net_proceeds_standard_vs_vip(self):
        """Net proceeds = sale_price - tax - fee."""
        # 10,000 standard: tax=1200, fee=100 -> net=8700
        self.assertEqual(self.model.calculate_net_proceeds(10_000, is_vip=False), 8_700)
        # 10,000 VIP: tax=1000, fee=100 -> net=8900
        self.assertEqual(self.model.calculate_net_proceeds(10_000, is_vip=True), 8_900)

        # 50,000 standard: tax=6000, fee=500 -> net=43500
        self.assertEqual(self.model.calculate_net_proceeds(50_000, is_vip=False), 43_500)
        # 50,000 VIP: tax=5000, fee=500 -> net=44500
        self.assertEqual(self.model.calculate_net_proceeds(50_000, is_vip=True), 44_500)

    def test_tier1_breakeven_purchase_ceiling(self):
        """Break-even purchase ceiling must strictly equal net proceeds."""
        sale_price = 1_000
        # tax = 120, fee = 100, net = 780
        net = self.model.calculate_net_proceeds(sale_price, is_vip=False)
        self.assertEqual(net, 780)
        breakeven = self.model.calc_breakeven_buy_price(sale_price, is_vip=False)
        self.assertEqual(breakeven, 780)

        # Buying at 780 yields 0 profit; buying at 781 loses 1 Hafe coin
        self.assertEqual(net - breakeven, 0)
        self.assertLess(net - (breakeven + 1), 0)

    def test_tier1_micro_price_negative_proceeds_guard(self):
        """At sale_price=100, tax=12, fee=100 -> net = -12. Break-even buy price must be 0 or negative."""
        net = self.model.calculate_net_proceeds(100, is_vip=False)
        self.assertEqual(net, -12)
        breakeven = self.model.calc_breakeven_buy_price(100, is_vip=False)
        self.assertLessEqual(breakeven, 0)


class TestTier2DynamicPricingAndOcrCleaner(unittest.TestCase):
    """Tier 2: Dynamic pricing thresholds & OCR text normalization/repair matrix."""

    def setUp(self):
        self.engine = DynamicPricingEngine()

    def test_tier2_dynamic_pricing_fixed_profit_target(self):
        """Dynamic buy ceiling with fixed profit target (e.g. min_profit = 2,000)."""
        ref_sale_price = 50_000  # net proceeds = 43,500
        max_buy = self.engine.get_max_buy_price(
            ref_market_price=ref_sale_price,
            min_profit=2_000,
            target_roi=0.0,
            is_vip=False,
        )
        self.assertEqual(max_buy, 41_500)
        # Verify profit at max_buy
        fee_model = TradingFeeModel()
        net = fee_model.calculate_net_proceeds(ref_sale_price, is_vip=False)
        self.assertGreaterEqual(net - max_buy, 2_000)

    def test_tier2_dynamic_pricing_roi_target(self):
        """Dynamic buy ceiling with target ROI (e.g. target_roi = 0.10)."""
        ref_sale_price = 50_000  # net proceeds = 43,500
        # max_buy = floor(43500 / 1.10) = 39,545
        max_buy = self.engine.get_max_buy_price(
            ref_market_price=ref_sale_price,
            min_profit=0,
            target_roi=0.10,
            is_vip=False,
        )
        self.assertEqual(max_buy, 39_545)
        profit = 43_500 - max_buy
        roi = profit / max_buy
        self.assertGreaterEqual(roi, 0.10)

    def test_tier2_dynamic_pricing_combined_conservative_cap(self):
        """Dynamic pricing takes min of fixed profit, ROI target, and incorporates volatility discount."""
        ref_sale_price = 100_000
        # With 3% volatility discount, effective sell price = 97,000
        # Net proceeds for 97,000 standard: tax = 11,640, fee = 970 -> net = 84,390
        # With min_profit = 5,000 -> max_buy_abs = 79,390
        # With target_roi = 0.10 -> max_buy_roi = floor(84,390 / 1.10) = 76,718
        max_buy = self.engine.get_max_buy_price(
            ref_market_price=ref_sale_price,
            min_profit=5_000,
            target_roi=0.10,
            is_vip=False,
            volatility_discount=0.03,
        )
        self.assertEqual(max_buy, 76_718)

    def test_tier2_ocr_cleaner_delimiters_and_spaces(self):
        """Standard thousands delimiters (commas, dots, spaces, full-width) must be stripped cleanly."""
        cases = [
            ("1,234", 1234),
            ("120.000", 120000),
            ("1 500 000", 1500000),
            ("2，500", 2500),
            ("3。000", 3000),
            (" 45,000 ", 45000),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(OcrTextCleaner.clean_and_parse(raw), expected)

    def test_tier2_ocr_cleaner_confusion_matrix_digits(self):
        """OCR confusion matrix: O/Q/D->0, I/l/!->1, Z->2, S->$->5, b->6, B->8, g/q->9."""
        cases = [
            ("l2O,OOD", 120000),  # l->1, O->0, D->0
            ("5O,OOO", 50000),    # O->0
            ("1!8", 118),         # !->1
            ("l23", 123),         # l->1
            ("|000", 1000),       # |->1
            ("Z500", 2500),       # Z->2
            ("S000", 5000),       # S->5
            ("s500", 5500),       # s->5
            ("b500", 6500),       # b->6
            ("B50", 850),         # B->8
            ("B000", 8000),       # B->8
            ("g50", 950),         # g->9
            ("q90", 990),         # q->9
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(OcrTextCleaner.clean_and_parse(raw), expected)

    def test_tier2_ocr_cleaner_unit_multipliers(self):
        """Unit multipliers (k/K/千 = 1e3, w/W/万 = 1e4, m/M = 1e6) must scale appropriately."""
        cases = [
            ("123k", 123000),
            ("50K", 50000),
            ("1.5k", 1500),
            ("2w", 20000),
            ("1.2W", 12000),
            ("5万", 50000),
            ("10.5w", 105000),
            ("1.5m", 1500000),
            ("2M", 2000000),
            ("8千", 8000),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(OcrTextCleaner.clean_and_parse(raw), expected)

    def test_tier2_ocr_cleaner_currency_prefixes_and_noise(self):
        """Currency prefixes, labels, and punctuation noise must be stripped."""
        cases = [
            ("哈夫币 1,250", 1250),
            ("¥ 50,000", 50000),
            ("￥1000", 1000),
            ("单价: 3500哈克币", 3500),
            ("三角券: 800", 800),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(OcrTextCleaner.clean_and_parse(raw), expected)

    def test_tier2_ocr_cleaner_invalid_and_boundary_inputs(self):
        """Invalid strings, empty inputs, non-numeric strings, and negative values must return None."""
        cases = [
            "",
            "   ",
            "Sold Out",
            "暂无库存",
            "-500",
            "---",
            "N/A",
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertIsNone(OcrTextCleaner.clean_and_parse(raw))


class TestTier3FloorProtectionAndAntiMisbuy(unittest.TestCase):
    """Tier 3: Floor price protection ratios against dropped digits and sanity bounds."""

    def test_tier3_floor_protection_dropped_digits_high_tier_card(self):
        """Critical Defense: 2M item dropped to 2k must be rejected (alpha=0.35 floor is 700k)."""
        ref_price = 2_000_000
        detected_price = 2_000  # OCR dropped 3 digits
        self.assertFalse(
            FloorProtectionBounds.is_valid_price(detected_price, ref_price, alpha_floor=0.35),
            "Must reject dropped digit price of 2,000 for 2,000,000 reference price!",
        )

    def test_tier3_floor_protection_legitimate_discount_accepted(self):
        """Legitimate market discount (e.g. 100k item listed at 85k) must be accepted."""
        ref_price = 100_000
        detected_price = 85_000
        self.assertTrue(
            FloorProtectionBounds.is_valid_price(detected_price, ref_price, alpha_floor=0.35),
            "Legitimate 15% discount should be accepted.",
        )

    def test_tier3_floor_protection_steep_discount_boundary(self):
        """With alpha=0.35, exactly 35% of ref_price is accepted; below 35% is rejected."""
        ref_price = 100_000
        # 35,000 is exactly 35%
        self.assertTrue(FloorProtectionBounds.is_valid_price(35_000, ref_price, alpha_floor=0.35))
        # 34,999 is below 35%
        self.assertFalse(FloorProtectionBounds.is_valid_price(34_999, ref_price, alpha_floor=0.35))

    def test_tier3_ceiling_protection_overpriced_listings(self):
        """Listings above beta_ceiling (e.g. 1.05 * ref_price) must be rejected."""
        ref_price = 100_000
        self.assertTrue(FloorProtectionBounds.is_valid_price(105_000, ref_price, beta_ceiling=1.05))
        self.assertFalse(FloorProtectionBounds.is_valid_price(105_001, ref_price, beta_ceiling=1.05))
        self.assertFalse(FloorProtectionBounds.is_valid_price(150_000, ref_price, beta_ceiling=1.05))

    def test_tier3_digit_length_discrepancy_check(self):
        """Severe digit count discrepancies (|len(det) - len(ref)| > 1) must be rejected immediately."""
        ref_price = 1_500_000  # 7 digits
        # 1,500 has 4 digits (diff = 3)
        self.assertFalse(FloorProtectionBounds.is_valid_price(1_500, ref_price))
        # 15,000 has 5 digits (diff = 2)
        self.assertFalse(FloorProtectionBounds.is_valid_price(15_000, ref_price))
        # 150,000 has 6 digits (diff = 1, allowed by length, but fails alpha_floor=0.35 since 150k < 525k)
        self.assertFalse(FloorProtectionBounds.is_valid_price(150_000, ref_price))
        # 1,200,000 has 7 digits (diff = 0, passes alpha_floor)
        self.assertTrue(FloorProtectionBounds.is_valid_price(1_200_000, ref_price))


class TestTier4PriceEvaluatorEndToEnd(unittest.TestCase):
    """Tier 4: End-to-end PriceEvaluator recognition validation with simulated OCR data."""

    def _create_mock_context(self, text_output: str, is_hit_return: bool = True):
        context = MagicMock()
        reco_detail = MagicMock()
        reco_detail.is_hit = is_hit_return
        reco_detail.hit = is_hit_return
        best_result = MagicMock()
        best_result.text = text_output
        reco_detail.best_result = best_result
        reco_detail.box = (100, 200, 80, 30)
        context.run_recognition.return_value = reco_detail
        return context

    def test_tier4_price_evaluator_noisy_ocr_hit(self):
        """PriceEvaluator repairs OCR noise 'l2O,OOD' to 120,000 and matches max_price=150,000."""
        evaluator = PriceEvaluator()
        context = self._create_mock_context("l2O,OOD")
        argv = MagicMock()
        argv.custom_recognition_param = {
            "ocr_node": "Trading.OcrPrice",
            "max_price": 150_000,
            "min_price": 50_000,
        }
        argv.image = MagicMock()

        result = evaluator.analyze(context, argv)
        self.assertIsNotNone(result, "Should successfully hit valid repaired price")
        self.assertEqual(result.detail["detected_price"], 120_000)
        self.assertEqual(result.detail["max_price"], 150_000)

    def test_tier4_price_evaluator_dropped_digit_defense(self):
        """PriceEvaluator rejects '2,000' when ref_market_price is 1,500,000, preventing 1.5M misbuy."""
        evaluator = PriceEvaluator()
        context = self._create_mock_context("2,000")
        argv = MagicMock()
        argv.custom_recognition_param = {
            "ocr_node": "Trading.OcrPrice",
            "max_price": 1_000_000,
            "min_price": 500,
            "ref_market_price": 1_500_000,
            "alpha_floor": 0.35,
        }
        argv.image = MagicMock()

        result = evaluator.analyze(context, argv)
        self.assertIsNone(result, "Must reject dropped-digit price under floor protection")

    def test_tier4_price_evaluator_over_budget_rejection(self):
        """PriceEvaluator returns None when clean price exceeds budget."""
        evaluator = PriceEvaluator()
        context = self._create_mock_context("165,000")
        argv = MagicMock()
        argv.custom_recognition_param = {
            "ocr_node": "Trading.OcrPrice",
            "max_price": 150_000,
            "min_price": 50_000,
        }
        argv.image = MagicMock()

        result = evaluator.analyze(context, argv)
        self.assertIsNone(result, "Price over max_price must return None")

    def test_tier4_price_evaluator_backward_compatibility(self):
        """Legacy callers passing only ocr_node, max_price, min_price must continue working."""
        evaluator = PriceEvaluator()
        context = self._create_mock_context("45,000")
        argv = MagicMock()
        argv.custom_recognition_param = {
            "ocr_node": "Trading.OcrPrice",
            "max_price": 50_000,
            "min_price": 100,
        }
        argv.image = MagicMock()

        result = evaluator.analyze(context, argv)
        self.assertIsNotNone(result)
        self.assertEqual(result.detail["detected_price"], 45_000)


if __name__ == "__main__":
    unittest.main()

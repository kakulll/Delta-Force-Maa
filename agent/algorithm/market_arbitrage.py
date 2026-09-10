"""Market Arbitrage & Dynamic Pricing Mathematical Engine.

Features:
- F1: Quantitative Trading Fee & Tax Mathematical Model
- F2: Dynamic Pricing Solver (Breakeven, Absolute Profit, ROI Margin)
- F3: Robust OCR Text Normalization & Confusion Matrix Repair
- F4: Relative Ratio Dynamic Floor Protection & Anti-Misbuy Bounds

This module is self-contained with zero external dependencies,
operating on pure Python 3.12 standard library primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import re
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# F1: Trading Fee & Tax Mathematical Model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TradingFeeModel:
    """Mathematical fee and tax model for Delta Force market transactions.

    Rules:
    - Base market tax: 12% (0.12)
    - VIP / Tactical privilege tax: 10% (0.10)
    - Listing fee: 1% (0.01) with minimum floor of 100 Hafe currency.
    """

    base_tax_rate: float = 0.12
    vip_tax_rate: float = 0.10
    privilege_discount: float = 0.0
    listing_fee_rate: float = 0.01
    min_listing_fee: int = 100

    def calculate_listing_fee(self, sale_price: int) -> int:
        """Calculate listing fee: max(min_fee, floor(sale_price * 0.01)).

        Handles sale_price <= 0 safely by returning 0.
        """
        if sale_price <= 0:
            return 0
        fee_rate = self.listing_fee_rate
        min_fee = self.min_listing_fee
        return max(min_fee, int(math.floor(sale_price * fee_rate + 1e-9)))

    calc_listing_fee = calculate_listing_fee

    def calculate_tax(self, sale_price: int, is_vip: bool = False) -> int:
        """Calculate transaction tax: floor(sale_price * (0.10 if VIP else 0.12)).

        Handles sale_price <= 0 safely by returning 0.
        """
        if sale_price <= 0:
            return 0
        effective_rate = self.vip_tax_rate if is_vip else self.base_tax_rate
        return int(math.floor(sale_price * effective_rate + 1e-9))

    calc_tax = calculate_tax

    def calculate_net_proceeds(self, sale_price: int, is_vip: bool = False) -> int:
        """Calculate net cash realized after listing fee and transaction tax.

        Formula:
            Net = sale_price - ListingFee - Tax
        """
        if sale_price <= 0:
            return 0
        fee = self.calculate_listing_fee(sale_price)
        tax = self.calculate_tax(sale_price, is_vip=is_vip)
        return sale_price - fee - tax

    def calc_breakeven_buy_price(self, sale_price: int, is_vip: bool = False) -> int:
        """Calculate breakeven buy price: strictly equals net proceeds."""
        if sale_price <= 0:
            return 0
        net = self.calculate_net_proceeds(sale_price, is_vip=is_vip)
        return net if net <= 0 else net

    # Class-level static wrappers for functional or static invocation
    @classmethod
    def static_listing_fee(cls, sale_price: int) -> int:
        return cls().calculate_listing_fee(sale_price)

    @classmethod
    def static_tax(cls, sale_price: int, is_vip: bool = False) -> int:
        return cls().calculate_tax(sale_price, is_vip=is_vip)

    @classmethod
    def static_net_proceeds(cls, sale_price: int, is_vip: bool = False) -> int:
        return cls().calculate_net_proceeds(sale_price, is_vip=is_vip)


# ---------------------------------------------------------------------------
# F2: Dynamic Pricing Solver & Arbitrage Decision
# ---------------------------------------------------------------------------

@dataclass
class ArbitrageDecision:
    """Structured valuation and trade decision record."""

    is_safe: bool
    is_profitable: bool
    should_buy: bool
    detected_price: int
    ref_market_price: int
    net_proceeds: int
    breakeven_buy_price: int
    max_buy_price: int
    expected_profit: int
    expected_roi: float
    rejection_reason: Optional[str] = None


class DynamicPricingEngine:
    """Dynamic purchase ceiling and arbitrage profit solver."""

    def __init__(self, fee_model: Optional[TradingFeeModel] = None) -> None:
        self.fee_model = fee_model or TradingFeeModel()

    @classmethod
    def get_breakeven_buy_price(
        cls,
        ref_market_price: int,
        is_vip: bool = False,
    ) -> int:
        """Calculate the absolute zero-profit buy ceiling.

        Any purchase above this price will result in net deficit upon sale.
        """
        if ref_market_price <= 0:
            return 0
        net = TradingFeeModel().calculate_net_proceeds(ref_market_price, is_vip=is_vip)
        return max(0, net)

    @classmethod
    def get_max_buy_price(
        cls,
        ref_market_price: int,
        min_profit: int = 1000,
        target_roi: float = 0.05,
        is_vip: bool = False,
        budget_cap: Optional[int] = None,
        volatility_discount: float = 0.0,
    ) -> int:
        """Calculate the maximum purchase price satisfying both absolute profit and ROI.

        Parameters:
            ref_market_price: Expected resale price in market.
            min_profit: Minimum required absolute currency profit (e.g. 1000).
            target_roi: Minimum required return on investment (e.g. 0.05 for 5%).
            is_vip: Whether seller privilege discount applies.
            budget_cap: Optional user-configured hard budget ceiling.
            volatility_discount: Market price fluctuation buffer (e.g. 0.03 for 3%).

        Returns:
            Maximum integer purchase price, or 0 if unreachable.
        """
        if ref_market_price <= 0:
            return 0

        # Adjust reference price for volatility discount
        vol_discount = max(0.0, float(volatility_discount))
        effective_ref = int(math.floor(ref_market_price * (1.0 - vol_discount) + 1e-9))
        if effective_ref <= 0:
            return 0

        net_proceeds = TradingFeeModel().calculate_net_proceeds(effective_ref, is_vip=is_vip)
        if net_proceeds <= 0:
            return 0

        # Absolute profit constraint: Net - P_buy >= min_profit => P_buy <= Net - min_profit
        max_buy_abs = net_proceeds - min_profit
        if max_buy_abs <= 0:
            return 0

        # ROI constraint: (Net - P_buy) / P_buy >= target_roi => P_buy <= Net / (1 + target_roi)
        safe_target_roi = max(0.0, float(target_roi))
        max_buy_roi = int(math.floor(net_proceeds / (1.0 + safe_target_roi) + 1e-9))

        ceiling = min(max_buy_abs, max_buy_roi)
        if budget_cap is not None and budget_cap > 0:
            ceiling = min(ceiling, budget_cap)

        return max(0, ceiling)

    @classmethod
    def evaluate_arbitrage(
        cls,
        detected_price: int,
        ref_market_price: int,
        min_profit: int = 1000,
        target_roi: float = 0.05,
        is_vip: bool = False,
        budget_cap: Optional[int] = None,
        alpha_floor: float = 0.35,
        beta_ceiling: float = 1.05,
        volatility_discount: float = 0.0,
    ) -> ArbitrageDecision:
        """Perform end-to-end quantitative evaluation of an observed market listing."""
        net = TradingFeeModel().calculate_net_proceeds(ref_market_price, is_vip=is_vip)
        breakeven = max(0, net)
        max_buy = cls.get_max_buy_price(
            ref_market_price=ref_market_price,
            min_profit=min_profit,
            target_roi=target_roi,
            is_vip=is_vip,
            budget_cap=budget_cap,
            volatility_discount=volatility_discount,
        )

        # Floor and safety check
        is_safe, reason = FloorProtectionBounds.validate_price_bounds(
            detected_price=detected_price,
            ref_market_price=ref_market_price,
            alpha=alpha_floor,
            beta=beta_ceiling,
        )

        expected_profit = net - detected_price if detected_price > 0 else 0
        expected_roi = (expected_profit / detected_price) if detected_price > 0 else 0.0

        is_profitable = (detected_price <= max_buy) and (expected_profit >= min_profit)

        if not is_safe:
            should_buy = False
            rejection_reason = reason
        elif not is_profitable:
            should_buy = False
            rejection_reason = (
                f"UNPROFITABLE (detected={detected_price} > max_buy={max_buy}, "
                f"profit={expected_profit} < {min_profit}, roi={expected_roi:.1%})"
            )
        else:
            should_buy = True
            rejection_reason = None

        return ArbitrageDecision(
            is_safe=is_safe,
            is_profitable=is_profitable,
            should_buy=should_buy,
            detected_price=detected_price,
            ref_market_price=ref_market_price,
            net_proceeds=net,
            breakeven_buy_price=breakeven,
            max_buy_price=max_buy,
            expected_profit=expected_profit,
            expected_roi=expected_roi,
            rejection_reason=rejection_reason,
        )


# ---------------------------------------------------------------------------
# F3: OCR Text Normalization & Repair Engine
# ---------------------------------------------------------------------------

class OcrTextCleaner:
    """Robust OCR text cleaner with confusion matrix repair and unit normalization."""

    # Optical character confusion matrix for numeric UI fonts
    CONFUSION_MAP: Dict[str, str] = {
        "O": "0", "o": "0", "Q": "0", "D": "0", "U": "0",
        "I": "1", "l": "1", "|": "1", "!": "1", "]": "1", "[": "1",
        "Z": "2", "z": "2",
        "S": "5", "s": "5",
        "b": "6",
        "B": "8",
        "g": "9", "q": "9",
    }

    # Standard quantity multipliers
    UNIT_MAP: Dict[str, int] = {
        "万": 10_000,
        "w": 10_000,
        "W": 10_000,
        "千": 1_000,
        "k": 1_000,
        "K": 1_000,
        "m": 1_000_000,
        "M": 1_000_000,
    }

    # Currency and header tokens to strip
    PREFIX_REGEX = re.compile(
        r"^(?:[¥￥$]|哈夫币|哈克币|三角券|单价|售价|价格|总计|Price|Cost|Total|[:：])\s*",
        re.IGNORECASE,
    )

    # Unit multiplier suffix detector
    UNIT_SUFFIX_REGEX = re.compile(r"^(.*?)\s*([万wW千kKmM])\s*$")

    @classmethod
    def clean_price(cls, raw_text: Optional[Union[str, int, float]]) -> Optional[int]:
        """Normalize raw OCR string into a sanitized integer price.

        Steps:
        1. Null and empty check.
        2. Replace full-width punctuation and digits.
        3. Detect and reject negative numbers.
        4. Check for presence of real numeric anchor digits.
        5. Strip leading currency prefixes and table headers.
        6. Check and parse unit multipliers (k/w/m).
        7. Apply confusion matrix (I/l/! -> 1, Z -> 2, S -> 5, b -> 6, B -> 8, g/q -> 9).
        8. Strip thousands separators (commas/dots) and trailing cents (.00).
        9. Convert to integer.
        """
        if raw_text is None:
            return None

        text = str(raw_text).strip()
        if not text:
            return None

        # Negative number safety guard
        if re.search(r"-\s*\d", text) or text.startswith("-") or set(text) <= {"-", "—"}:
            logger.debug("OcrTextCleaner: 拦截到负数价格文本: %s", text)
            return None

        # Must contain at least one real digit before confusion replacement,
        # preventing purely alphabetic text ("Sold Out", "N/A", "暂无库存") from falsely mutating.
        if not any(c.isdigit() for c in text):
            logger.debug("OcrTextCleaner: 文本中无基准数字: %s", text)
            return None

        # Normalize full-width punctuation
        text = (
            text.replace("，", ",")
            .replace("。", ".")
            .replace("、", ",")
            .replace("_", "")
            .replace("'", "")
        )

        # Strip known currency prefixes and table header tokens
        text = cls.PREFIX_REGEX.sub("", text).strip()
        # Also strip trailing currency labels (e.g. "3500哈克币" -> "3500")
        text = re.sub(r"\s*(?:哈夫币|哈克币|三角券)$", "", text, flags=re.IGNORECASE).strip()
        if not text:
            return None

        # Check for unit multipliers (e.g. 1.2W, 150k, 2.5M, 80万)
        unit_match = cls.UNIT_SUFFIX_REGEX.match(text)
        if unit_match:
            num_part = unit_match.group(1).strip()
            unit_char = unit_match.group(2)
            multiplier = cls.UNIT_MAP.get(unit_char, 1)

            # Apply confusion map to numeric prefix
            for src, target in cls.CONFUSION_MAP.items():
                num_part = num_part.replace(src, target)

            # Replace comma with dot for decimal float parsing
            num_part = num_part.replace(",", ".").replace(" ", "")
            try:
                val = float(num_part)
                if val < 0:
                    return None
                return int(round(val * multiplier))
            except ValueError:
                logger.debug("OcrTextCleaner: 带有单位的数值部分解析失败: %s", num_part)
                return None

        # No unit suffix - full text confusion matrix replacement
        for src, target in cls.CONFUSION_MAP.items():
            text = text.replace(src, target)

        # Strip trailing currency decimals (.00 or ,00)
        text = re.sub(r"[\.,]00$", "", text)

        # Remove all thousands separators and spaces
        text = text.replace(",", "").replace(".", "").replace(" ", "")

        # Extract remaining digits
        digits = re.findall(r"\d+", text)
        if not digits:
            logger.debug("OcrTextCleaner: 未提取到有效数字, 原始文本: %s", raw_text)
            return None

        try:
            return int("".join(digits))
        except ValueError:
            return None

    clean_and_parse = clean_price


# ---------------------------------------------------------------------------
# F4: Relative Ratio Dynamic Floor Protection
# ---------------------------------------------------------------------------

class FloorProtectionBounds:
    """Dynamic lower and upper bound protection preventing dropped-digit misbuys."""

    @classmethod
    def get_floor_bound(cls, ref_market_price: int, alpha: float = 0.35) -> int:
        """Calculate dynamic minimum price bound: floor(alpha * ref_market_price)."""
        if ref_market_price <= 0:
            return 0
        return int(math.floor(ref_market_price * alpha))

    @classmethod
    def get_ceiling_bound(cls, ref_market_price: int, beta: float = 1.05) -> int:
        """Calculate dynamic maximum price bound: floor(beta * ref_market_price)."""
        if ref_market_price <= 0:
            return 0
        return int(math.floor(ref_market_price * beta))

    @classmethod
    def validate_price_bounds(
        cls,
        detected_price: int,
        ref_market_price: int,
        alpha: float = 0.35,
        beta: float = 1.05,
        check_digit_length: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """Validate whether detected_price falls into safe dynamic corridor.

        Returns:
            (is_valid, rejection_reason)
        """
        if detected_price <= 0:
            return False, f"NON_POSITIVE_PRICE (detected={detected_price})"

        # If no reference price is known, basic positivity is satisfied
        if ref_market_price <= 0:
            return True, None

        # Floor threshold check
        floor_val = cls.get_floor_bound(ref_market_price, alpha=alpha)
        if detected_price < floor_val:
            return (
                False,
                f"PRICE_BELOW_FLOOR (detected={detected_price} < floor={floor_val}, ref={ref_market_price}, alpha={alpha})",
            )

        # Ceiling threshold check
        ceiling_val = cls.get_ceiling_bound(ref_market_price, beta=beta)
        if detected_price > ceiling_val:
            return (
                False,
                f"PRICE_EXCEEDS_CEILING (detected={detected_price} > ceiling={ceiling_val}, ref={ref_market_price}, beta={beta})",
            )

        # Digit length consistency guard (defense-in-depth against OCR dropped zero)
        if check_digit_length and ref_market_price >= 100:
            ref_len = len(str(ref_market_price))
            det_len = len(str(detected_price))
            if (ref_len - det_len) >= 2:
                return (
                    False,
                    f"DROPPED_DIGITS (detected={detected_price} has {det_len} digits vs ref={ref_market_price} with {ref_len} digits)",
                )

        return True, None

    @classmethod
    def is_valid_price(
        cls,
        detected_price: int,
        ref_market_price: int,
        alpha: Optional[float] = None,
        alpha_floor: Optional[float] = None,
        beta: Optional[float] = None,
        beta_ceiling: Optional[float] = None,
    ) -> bool:
        """Convenience predicate matching PROJECT.md and test interface contracts."""
        eff_alpha = alpha_floor if alpha_floor is not None else (alpha if alpha is not None else 0.35)
        eff_beta = beta_ceiling if beta_ceiling is not None else (beta if beta is not None else 1.05)
        valid, _ = cls.validate_price_bounds(
            detected_price=detected_price,
            ref_market_price=ref_market_price,
            alpha=eff_alpha,
            beta=eff_beta,
        )
        return valid

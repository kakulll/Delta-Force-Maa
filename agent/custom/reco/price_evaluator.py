"""PriceEvaluator Custom Recognition Module.

Integrates MaaFramework Universal Pipeline OCR nodes with quantitative
arbitrage solving, robust OCR normalization, and anti-misbuy floor protection.

Maintains 100% backward compatibility with existing tasks and test contracts.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, cast
from unittest.mock import MagicMock

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import RectType

from utils import logger
from utils.maa_types import is_hit
from utils.params import parse_params

# Resilient dual-path import supporting both root and agent-relative execution
try:
    from agent.algorithm.market_arbitrage import (
        DynamicPricingEngine,
        FloorProtectionBounds,
        OcrTextCleaner,
        TradingFeeModel,
    )
except ImportError:
    from algorithm.market_arbitrage import (
        DynamicPricingEngine,
        FloorProtectionBounds,
        OcrTextCleaner,
        TradingFeeModel,
    )


@AgentServer.custom_recognition("PriceEvaluator")
class PriceEvaluator(CustomRecognition):
    """MaaFramework 自定义价格阈值评估识别器。

    基于 MaaFramework Pipeline 协议设计，配合 OCR 节点实现数值提取、
    混淆字符修复、动态相对底价防丢位过滤及保本/目标利润上限判定。

    参数说明 (custom_recognition_param):
        基础参数 (完全兼容旧版):
            ocr_node: str              # 执行 OCR 识别的节点名 (默认 "Trading.OcrPrice")
            max_price: int             # 预算最高限价 (默认 99999999)
            min_price: int             # 基础底价过滤 (默认 50)
        算法高级扩展参数 (可选):
            ref_market_price: int      # 市场参考公允售价 (用于动态计算保本与相对底价)
            min_profit: int            # 最低保底净利润 (默认 1000)
            target_roi: float          # 目标投资回报率 (默认 0.05, 即 5%)
            is_vip: bool               # 是否享受特权 10% 交易税 (默认 False, 即 12%)
            alpha_floor: float         # 相对底价保护比例 (默认 0.35)
            beta_ceiling: float        # 相对顶价保护比例 (默认 1.05)
            use_dynamic_pricing: bool  # 是否启用动态定价 (若提供 ref_market_price 则默认为 True)
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult | None:
        try:
            params = parse_params(argv.custom_recognition_param)
            ocr_node = str(params.get("ocr_node", "Trading.OcrPrice"))
            max_price = int(params.get("max_price", 99999999))
            min_price = int(params.get("min_price", 50))

            # Optional quantitative algorithm parameters
            raw_ref = params.get("ref_market_price")
            ref_market_price: Optional[int] = int(raw_ref) if raw_ref is not None else None
            min_profit = int(params.get("min_profit", 1000))
            target_roi = float(params.get("target_roi", 0.05))
            is_vip = bool(params.get("is_vip", False))
            alpha_floor = float(params.get("alpha_floor", 0.35))
            beta_ceiling = float(params.get("beta_ceiling", 1.05))
            use_dynamic_pricing = bool(
                params.get("use_dynamic_pricing", ref_market_price is not None and ref_market_price > 0)
            )
        except (ValueError, TypeError) as err:
            logger.error("PriceEvaluator param error: %s", err)
            return None

        # 运行底层 OCR 节点识别
        reco_detail = context.run_recognition(ocr_node, argv.image)
        if reco_detail is None:
            return None

        # Check hit condition handling both MaaFramework RecognitionDetail and mock objects
        if hasattr(reco_detail, "is_hit") and not isinstance(getattr(reco_detail, "is_hit"), MagicMock):
            if not reco_detail.is_hit:
                return None
        elif hasattr(reco_detail, "hit") and not isinstance(getattr(reco_detail, "hit"), MagicMock):
            if not reco_detail.hit:
                return None
        elif not is_hit(reco_detail):
            return None

        raw_text = self._extract_raw_text(reco_detail)
        if not raw_text:
            logger.debug("PriceEvaluator: OCR 节点未返回有效文本")
            return None

        # 核心清洗：全矩阵字符纠错 (O/Q/D->0, I/l/!->1, Z->2, S->5, b->6, B->8, g/q->9, k/w/m换算)
        detected_price = OcrTextCleaner.clean_price(raw_text)
        if detected_price is None:
            logger.debug("PriceEvaluator: 未提取到有效价格数字, 原始文本: %s", raw_text)
            return None

        logger.info(
            "PriceEvaluator: 识别价格=%d (原始文本='%s', 预算上限=%d, 底价=%d)",
            detected_price,
            raw_text,
            max_price,
            min_price,
        )

        # 1. 基础绝对底价拦截 (防误操作)
        if detected_price < min_price:
            logger.warning(
                "PriceEvaluator: 识别价格 %d 低于基础安全底价 %d，放弃购买",
                detected_price,
                min_price,
            )
            return None

        # 2. 动态相对比例底价保护 (防 OCR 丢位买错)
        if ref_market_price is not None and ref_market_price > 0:
            is_valid_bounds, bound_reason = FloorProtectionBounds.validate_price_bounds(
                detected_price=detected_price,
                ref_market_price=ref_market_price,
                alpha=alpha_floor,
                beta=beta_ceiling,
            )
            if not is_valid_bounds:
                logger.warning(
                    "PriceEvaluator: 相对底价/溢价保护拦截 (原因: %s, 识别价=%d, 参考价=%d)",
                    bound_reason,
                    detected_price,
                    ref_market_price,
                )
                return None

        # 3. 动态利润限价求解
        effective_max_price = max_price
        dynamic_ceiling: Optional[int] = None
        if use_dynamic_pricing and ref_market_price is not None and ref_market_price > 0:
            dynamic_ceiling = DynamicPricingEngine.get_max_buy_price(
                ref_market_price=ref_market_price,
                min_profit=min_profit,
                target_roi=target_roi,
                is_vip=is_vip,
                budget_cap=max_price,
            )
            effective_max_price = min(max_price, dynamic_ceiling)
            logger.debug(
                "PriceEvaluator: 动态求解最高买入价=%d (参考售价=%d, 保底利润=%d, ROI=%.1f%%)",
                effective_max_price,
                ref_market_price,
                min_profit,
                target_roi * 100,
            )

        # 4. 最终买入决策判定
        if detected_price <= effective_max_price:
            logger.info(
                "🎉 价格命中！当前价格 %d <= 有效买入上限 %d (静态预算=%d)，触发购买",
                detected_price,
                effective_max_price,
                max_price,
            )
            reco_box = getattr(reco_detail, "box", (0, 0, 100, 100))
            return CustomRecognition.AnalyzeResult(
                box=cast(RectType, reco_box),
                detail={
                    "detected_price": detected_price,
                    "max_price": max_price,
                    "effective_max_price": effective_max_price,
                    "raw_text": raw_text,
                    "ref_market_price": ref_market_price,
                    "is_vip": is_vip,
                    "dynamic_pricing_applied": use_dynamic_pricing and dynamic_ceiling is not None,
                },
            )

        logger.debug(
            "PriceEvaluator: 当前价格 %d 高于有效上限 %d，继续监控",
            detected_price,
            effective_max_price,
        )
        return None

    @staticmethod
    def _extract_raw_text(reco_detail: Any) -> str:
        """Extract plain string text from heterogeneous MaaFramework reco_detail structures."""
        if hasattr(reco_detail, "best_result") and reco_detail.best_result and hasattr(reco_detail.best_result, "text"):
            return str(reco_detail.best_result.text)
        if hasattr(reco_detail, "all_results") and reco_detail.all_results:
            return " ".join(str(r.text) for r in reco_detail.all_results if hasattr(r, "text"))
        if hasattr(reco_detail, "raw_detail"):
            return str(reco_detail.raw_detail)

        detail_obj = getattr(reco_detail, "detail", None)
        if isinstance(detail_obj, dict):
            return str(detail_obj.get("text", ""))
        if isinstance(detail_obj, list) and detail_obj:
            return "".join(str(item.get("text", "")) for item in detail_obj if isinstance(item, dict))
        return str(detail_obj or "")

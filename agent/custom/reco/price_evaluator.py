from __future__ import annotations

import re
from typing import Any, cast

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import RectType
from utils import logger
from utils.maa_types import is_hit
from utils.params import parse_params


@AgentServer.custom_recognition("PriceEvaluator")
class PriceEvaluator(CustomRecognition):
    """MaaFramework 自定义价格阈值评估识别器。

    基于 MaaFramework Pipeline 协议设计，配合 OCR 节点实现数值提取、
    异常底价防丢位过滤及最高预算上限判定。

    参数说明:
        custom_recognition_param:
            {
                "ocr_node": "Trading.OcrPrice",  # 执行 OCR 识别的节点名
                "max_price": 50000,              # 预算最高限价，低于等于该价格时判定命中
                "min_price": 100                 # 异常过滤底价，防止漏位误买
            }
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
        except (ValueError, TypeError) as err:
            logger.error("PriceEvaluator param error: %s", err)
            return None

        # 运行底层 OCR 节点识别
        reco_detail = context.run_recognition(ocr_node, argv.image)
        if not is_hit(reco_detail):
            return None

        detail_obj = getattr(reco_detail, "detail", None)
        raw_text = ""
        if isinstance(detail_obj, dict):
            raw_text = str(detail_obj.get("text", ""))
        elif isinstance(detail_obj, list) and detail_obj:
            raw_text = "".join(str(item.get("text", "")) for item in detail_obj if isinstance(item, dict))
        else:
            raw_text = str(detail_obj or "")

        # 借鉴 GTImaster 的字符清洗算法：纠正常见 OCR 误识别（O/Q/D -> 0）及标点
        cleaned_text = (
            raw_text.upper()
            .replace(",", "")
            .replace(".", "")
            .replace(" ", "")
            .replace("，", "")
            .replace("。", "")
            .replace("O", "0")
            .replace("Q", "0")
            .replace("D", "0")
        )

        digits = re.findall(r"\d+", cleaned_text)
        if not digits:
            logger.debug("PriceEvaluator: 未提取到有效数字, 原始文本: %s", raw_text)
            return None

        try:
            detected_price = int("".join(digits))
        except ValueError:
            return None

        logger.info("PriceEvaluator: 识别价格=%d (预算上限=%d, 底价=%d)", detected_price, max_price, min_price)

        # 异常过低保护（可能由于识别漏位）
        if detected_price < min_price:
            logger.warning("PriceEvaluator: 识别价格 %d 低于安全底价 %d，可能为识别丢位，放弃购买", detected_price, min_price)
            return None

        # 价格符合预算
        if detected_price <= max_price:
            logger.info("🎉 价格命中！当前价格 %d <= 目标预算 %d，触发购买", detected_price, max_price)
            reco_box = getattr(reco_detail, "box", (0, 0, 100, 100))
            return CustomRecognition.AnalyzeResult(
                box=cast(RectType, reco_box),
                detail={
                    "detected_price": detected_price,
                    "max_price": max_price,
                    "raw_text": raw_text,
                },
            )

        logger.debug("PriceEvaluator: 当前价格 %d 高于预算 %d，继续监控", detected_price, max_price)
        return None

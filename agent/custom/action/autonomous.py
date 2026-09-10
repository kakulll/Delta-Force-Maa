"""Autonomous Scheduling Custom Actions — Delta-Force-Maa.

Provides:
- AutonomousReport: Collect stats and push Webhook battle report.
- AutonomousPostRun: Execute post-run action (stay / shutdown / hibernate).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction
from utils import logger
from utils.params import parse_params
from custom.sink.notifier import BattleReport, get_notifier


@AgentServer.custom_action("AutonomousReport")
class AutonomousReport(CustomAction):
    """Collect session statistics and push Webhook battle report.

    custom_action_param:
        {
            "report_type": "daily_summary",
            "webhook_enabled": true,
            "hafe_earned": 0,          // optional — filled by runtime tracking
            "items_claimed": 0,        // optional
            "ammo_flipped": 0          // optional
        }
    """

    # Class-level session accumulator shared across pipeline run
    _session: dict[str, Any] = {
        "start_time": None,
        "hafe_earned": 0,
        "items_claimed": 0,
        "ammo_flipped": 0,
        "tasks_completed": [],
        "tasks_failed": [],
    }

    @classmethod
    def reset_session(cls) -> None:
        cls._session = {
            "start_time": time.time(),
            "hafe_earned": 0,
            "items_claimed": 0,
            "ammo_flipped": 0,
            "tasks_completed": [],
            "tasks_failed": [],
        }

    @classmethod
    def record_task(cls, task_name: str, success: bool) -> None:
        if success:
            if task_name not in cls._session["tasks_completed"]:
                cls._session["tasks_completed"].append(task_name)
        else:
            if task_name not in cls._session["tasks_failed"]:
                cls._session["tasks_failed"].append(task_name)

    @classmethod
    def add_earnings(cls, hafe: int = 0, items: int = 0, ammo_batches: int = 0) -> None:
        cls._session["hafe_earned"] += hafe
        cls._session["items_claimed"] += items
        cls._session["ammo_flipped"] += ammo_batches

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            params = parse_params(argv.custom_action_param)
        except ValueError as err:
            logger.error("AutonomousReport: param parse error: {}", err)
            return CustomAction.RunResult(success=True)  # non-fatal

        webhook_enabled = bool(params.get("webhook_enabled", False))

        sess = self._session
        start = sess.get("start_time") or time.time()
        report = BattleReport(
            task_name="全托管日常",
            success=len(sess["tasks_failed"]) == 0,
            start_time=start,
            end_time=time.time(),
            hafe_earned=int(sess.get("hafe_earned", 0)),
            items_claimed=int(sess.get("items_claimed", 0)),
            ammo_flipped=int(sess.get("ammo_flipped", 0)),
            tasks_completed=list(sess.get("tasks_completed", [])),
            tasks_failed=list(sess.get("tasks_failed", [])),
        )

        logger.info(
            "AutonomousReport: 任务完成 | 耗时={} | 哈夫币={:,} | 物资={} | 子弹批次={}",
            report.duration_str,
            report.hafe_earned,
            report.items_claimed,
            report.ammo_flipped,
        )

        if webhook_enabled:
            notifier = get_notifier()
            ok = notifier.send_battle_report(report)
            if ok:
                logger.info("AutonomousReport: 战报推送成功 ✅")
            else:
                logger.warning("AutonomousReport: 战报推送失败（请检查 config/webhook_config.json）")

        return CustomAction.RunResult(success=True)


@AgentServer.custom_action("AutonomousPostRun")
class AutonomousPostRun(CustomAction):
    """Execute post-run action after full autonomous pipeline completes.

    custom_action_param:
        {
            "action": "stay" | "shutdown" | "hibernate",
            "delay_seconds": 30
        }
    """

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            params = parse_params(argv.custom_action_param)
        except ValueError as err:
            logger.error("AutonomousPostRun: param parse error: {}", err)
            return CustomAction.RunResult(success=True)

        action = str(params.get("action", "stay")).lower()
        delay = int(params.get("delay_seconds", 30))

        if action == "stay":
            logger.info("AutonomousPostRun: 保持大厅待机，任务已完成")
            return CustomAction.RunResult(success=True)

        if delay > 0:
            logger.info("AutonomousPostRun: {} 将在 {} 秒后执行...", action, delay)
            time.sleep(delay)

        if action == "shutdown":
            logger.info("AutonomousPostRun: 发送系统关机指令")
            if sys.platform.startswith("win"):
                subprocess.Popen(["shutdown", "/s", "/t", "10", "/c", "三角洲行动 Maa 任务完成，系统关机"])
            else:
                subprocess.Popen(["shutdown", "-h", "+0"])

        elif action == "hibernate":
            logger.info("AutonomousPostRun: 发送系统休眠指令")
            if sys.platform.startswith("win"):
                os.system("rundll32.exe powrprof.dll,SetSuspendState 1,1,0")
            else:
                os.system("systemctl hibernate")

        else:
            logger.warning("AutonomousPostRun: 未知动作 '{}', 保持待机", action)

        return CustomAction.RunResult(success=True)

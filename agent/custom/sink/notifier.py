"""Webhook Notification Sink — Delta-Force-Maa.

Sends structured Markdown battle reports and anomaly alerts to
WeChat Work / DingTalk / Feishu / Server酱 via standard Webhook APIs.

Configuration file: config/webhook_config.json
{
    "enabled": true,
    "provider": "wecom" | "dingtalk" | "feishu" | "serverchain",
    "webhook_url": "https://...",
    "mention_all": false,
    "secret": "<HMAC signing secret — DingTalk only>"
}
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils import logger


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "provider": "wecom",
    "webhook_url": "",
    "mention_all": False,
    "secret": "",
}


def _load_webhook_config(project_root: Optional[Path] = None) -> Dict[str, Any]:
    root = project_root or _find_project_root()
    config_path = root / "config" / "webhook_config.json"
    if not config_path.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged = dict(_DEFAULT_CONFIG)
            merged.update(data)
            return merged
    except (OSError, json.JSONDecodeError) as err:
        logger.warning("webhook_config.json load error: {}", err)
    return dict(_DEFAULT_CONFIG)


def _find_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Battle Report Data Model
# ---------------------------------------------------------------------------

@dataclass
class BattleReport:
    """Structured daily battle report for push notification."""

    task_name: str = "全托管日常"
    success: bool = True
    start_time: float = field(default_factory=time.time)
    end_time: float = field(default_factory=time.time)
    hafe_earned: int = 0
    items_claimed: int = 0
    ammo_flipped: int = 0
    tasks_completed: List[str] = field(default_factory=list)
    tasks_failed: List[str] = field(default_factory=list)
    error_message: str = ""

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_time - self.start_time)

    @property
    def duration_str(self) -> str:
        secs = int(self.duration_seconds)
        mins, s = divmod(secs, 60)
        if mins:
            return f"{mins}分{s:02d}秒"
        return f"{s}秒"


# ---------------------------------------------------------------------------
# Webhook Dispatcher
# ---------------------------------------------------------------------------

class WebhookNotifier:
    """Multi-provider Webhook dispatcher for battle reports and alerts."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self._cfg = _load_webhook_config(project_root)

    @property
    def enabled(self) -> bool:
        return bool(self._cfg.get("enabled")) and bool(self._cfg.get("webhook_url", "").strip())

    def send_battle_report(self, report: BattleReport) -> bool:
        """Build and dispatch a Markdown battle report card."""
        if not self.enabled:
            logger.debug("WebhookNotifier disabled or no URL configured.")
            return False

        status_icon = "✅" if report.success else "❌"
        completed_str = "\n".join(f"  • {t}" for t in report.tasks_completed) or "  (无)"
        failed_str = "\n".join(f"  • {t}" for t in report.tasks_failed) or "  (无)"

        title = f"{status_icon} 三角洲行动 Maa — {report.task_name}战报"
        body_lines = [
            f"**执行状态**: {'成功' if report.success else '部分失败'}",
            f"**耗时**: {report.duration_str}",
            "",
            f"**到账哈夫币**: +{report.hafe_earned:,}",
            f"**领取物资**: {report.items_claimed} 件",
            f"**倒卖子弹**: {report.ammo_flipped} 批次",
            "",
            f"**已完成任务**:\n{completed_str}",
        ]
        if report.tasks_failed:
            body_lines.append(f"\n**失败任务**:\n{failed_str}")
        if report.error_message:
            body_lines.append(f"\n**错误信息**: {report.error_message}")

        content = f"## {title}\n\n" + "\n".join(body_lines)
        return self._dispatch(title=title, content=content)

    def send_alert(self, title: str, message: str) -> bool:
        """Send an anomaly alert message."""
        if not self.enabled:
            return False
        full_content = f"## ⚠️ {title}\n\n{message}"
        return self._dispatch(title=f"⚠️ 异常告警: {title}", content=full_content)

    def _dispatch(self, title: str, content: str) -> bool:
        provider = str(self._cfg.get("provider", "wecom")).lower()
        url = str(self._cfg.get("webhook_url", "")).strip()
        if not url:
            logger.warning("WebhookNotifier: webhook_url is empty.")
            return False

        try:
            if provider == "wecom":
                return self._send_wecom(url, content)
            elif provider == "dingtalk":
                return self._send_dingtalk(url, title, content)
            elif provider == "feishu":
                return self._send_feishu(url, title, content)
            elif provider in ("serverchain", "serverchan"):
                return self._send_serverchan(url, title, content)
            else:
                logger.warning("WebhookNotifier: unknown provider '{}'", provider)
                return False
        except Exception as err:
            logger.error("WebhookNotifier dispatch error: {}", err)
            return False

    # -------------------------------------------------------------------------
    # Provider-specific payloads
    # -------------------------------------------------------------------------

    def _send_wecom(self, url: str, content: str) -> bool:
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }
        return self._post_json(url, payload)

    def _send_dingtalk(self, url: str, title: str, content: str) -> bool:
        secret = str(self._cfg.get("secret", "")).strip()
        final_url = url
        if secret:
            ts = str(round(time.time() * 1000))
            sign_str = f"{ts}\n{secret}"
            sign = b64encode(
                hmac.new(secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).digest()
            ).decode("utf-8")
            final_url = f"{url}&timestamp={ts}&sign={urllib.parse.quote_plus(sign)}"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content,
            },
        }
        if self._cfg.get("mention_all"):
            payload["at"] = {"isAtAll": True}
        return self._post_json(final_url, payload)

    def _send_feishu(self, url: str, title: str, content: str) -> bool:
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content,
                    }
                ],
            },
        }
        return self._post_json(url, payload)

    def _send_serverchan(self, url: str, title: str, content: str) -> bool:
        payload = {"title": title, "desp": content}
        return self._post_json(url, payload)

    @staticmethod
    def _post_json(url: str, payload: Dict[str, Any]) -> bool:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_body = resp.read().decode("utf-8", errors="replace")
                logger.debug("WebhookNotifier response: {}", resp_body[:200])
                return resp.status < 400
        except urllib.error.HTTPError as err:
            logger.error("WebhookNotifier HTTP {}: {}", err.code, err.reason)
            return False
        except urllib.error.URLError as err:
            logger.error("WebhookNotifier URL error: {}", err.reason)
            return False


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_notifier: Optional[WebhookNotifier] = None


def get_notifier(project_root: Optional[Path] = None) -> WebhookNotifier:
    global _notifier
    if _notifier is None:
        _notifier = WebhookNotifier(project_root=project_root)
    return _notifier

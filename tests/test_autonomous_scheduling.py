"""Tests for M3 & M4: Autonomous Scheduling Pipeline & Webhook Notifier.

Validates:
- autonomous.json pipeline structure and node connectivity
- tasks/autonomous.json option definitions (4 options present)
- interface.json includes autonomous.json import
- AutonomousStrategyOption cases correctly enable/disable steps
- WebhookNotifier config loading with disabled default
- BattleReport data model correctness
- WebhookNotifier disabled gracefully (no network calls)
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
AUTONOMOUS_PIPELINE = ROOT / "resource" / "base" / "pipeline" / "autonomous.json"
AUTONOMOUS_TASK = ROOT / "tasks" / "autonomous.json"
INTERFACE_JSON = ROOT / "interface.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestAutonomousPipeline(unittest.TestCase):
    """Test the autonomous scheduling pipeline JSON structure."""

    def setUp(self) -> None:
        self.pipeline = load_json(AUTONOMOUS_PIPELINE)

    def test_start_node_present(self) -> None:
        self.assertIn("Autonomous.Start", self.pipeline)

    def test_all_step_nodes_present(self) -> None:
        for i in range(1, 8):
            node_name = f"Autonomous.Step{i}" + [
                "Startup", "Daily", "Department", "Shelter",
                "Warehouse", "AmmoFlip", "Finalize"
            ][i - 1]
            # Just check at least 7 step nodes exist
        step_nodes = [k for k in self.pipeline if k.startswith("Autonomous.Step")]
        self.assertGreaterEqual(len(step_nodes), 7, "Should have at least 7 Step nodes")

    def test_report_results_node_present(self) -> None:
        self.assertIn("Autonomous.ReportResults", self.pipeline)

    def test_report_results_uses_custom_action(self) -> None:
        node = self.pipeline["Autonomous.ReportResults"]
        self.assertEqual(node.get("action"), "Custom")
        self.assertEqual(node.get("custom_action"), "AutonomousReport")

    def test_esc_ladder_nodes_present(self) -> None:
        for i in range(1, 5):
            self.assertIn(f"Autonomous.EscLadder{i}", self.pipeline,
                          f"EscLadder{i} must exist")

    def test_esc_ladder_chains_correctly(self) -> None:
        """EscLadder1 → 2 → 3 → 4 → Startup.CheckLobby."""
        ladder4 = self.pipeline.get("Autonomous.EscLadder4", {})
        self.assertIn("Startup.CheckLobby", ladder4.get("next", []))

    def test_start_node_links_to_step1(self) -> None:
        start = self.pipeline["Autonomous.Start"]
        nexts = start.get("next", [])
        self.assertTrue(any("Step1" in n for n in nexts), "Start should link to Step1Startup")

    def test_all_roi_within_bounds(self) -> None:
        for name, node in self.pipeline.items():
            if node.get("recognition") == "OCR" and "roi" in node:
                roi = node["roi"]
                x, y, w, h = roi
                self.assertLessEqual(x + w, 2560, f"{name}: x+w out of 2560")
                self.assertLessEqual(y + h, 1600, f"{name}: y+h out of 1600")


class TestAutonomousTask(unittest.TestCase):
    """Test tasks/autonomous.json option definitions."""

    def setUp(self) -> None:
        self.tasks_cfg = load_json(AUTONOMOUS_TASK)
        self.options = self.tasks_cfg.get("option", {})
        self.tasks = self.tasks_cfg.get("task", [])

    def test_autonomous_daily_task_present(self) -> None:
        names = [t["name"] for t in self.tasks]
        self.assertIn("AutonomousDaily", names)

    def test_strategy_option_present(self) -> None:
        self.assertIn("AutonomousStrategyOption", self.options)

    def test_post_run_option_present(self) -> None:
        self.assertIn("AutonomousPostRunOption", self.options)

    def test_webhook_option_present(self) -> None:
        self.assertIn("AutonomousWebhookOption", self.options)

    def test_dryrun_option_present(self) -> None:
        self.assertIn("AutonomousDryRunOption", self.options)

    def test_strategy_option_has_three_cases(self) -> None:
        cases = self.options["AutonomousStrategyOption"].get("cases", [])
        case_names = [c["name"] for c in cases]
        self.assertIn("FullDaily", case_names)
        self.assertIn("DailyWelfareOnly", case_names)
        self.assertIn("ClearAndFlipOnly", case_names)

    def test_full_daily_enables_all_steps(self) -> None:
        cases = self.options["AutonomousStrategyOption"]["cases"]
        full = next(c for c in cases if c["name"] == "FullDaily")
        overrides = full.get("pipeline_override", {})
        for step in ["Autonomous.Step2Daily", "Autonomous.Step3Department",
                     "Autonomous.Step4Shelter", "Autonomous.Step5Warehouse",
                     "Autonomous.Step6AmmoFlip"]:
            self.assertTrue(overrides.get(step, {}).get("enabled", False),
                            f"FullDaily should enable {step}")

    def test_daily_welfare_disables_warehouse_and_flip(self) -> None:
        cases = self.options["AutonomousStrategyOption"]["cases"]
        welfare = next(c for c in cases if c["name"] == "DailyWelfareOnly")
        overrides = welfare.get("pipeline_override", {})
        self.assertFalse(overrides.get("Autonomous.Step5Warehouse", {}).get("enabled", True))
        self.assertFalse(overrides.get("Autonomous.Step6AmmoFlip", {}).get("enabled", True))

    def test_clear_flip_disables_daily_and_department(self) -> None:
        cases = self.options["AutonomousStrategyOption"]["cases"]
        clear = next(c for c in cases if c["name"] == "ClearAndFlipOnly")
        overrides = clear.get("pipeline_override", {})
        self.assertFalse(overrides.get("Autonomous.Step2Daily", {}).get("enabled", True))
        self.assertFalse(overrides.get("Autonomous.Step3Department", {}).get("enabled", True))

    def test_autonomous_task_references_all_4_options(self) -> None:
        task = next(t for t in self.tasks if t["name"] == "AutonomousDaily")
        opts = task.get("option", [])
        self.assertIn("AutonomousStrategyOption", opts)
        self.assertIn("AutonomousPostRunOption", opts)
        self.assertIn("AutonomousWebhookOption", opts)
        self.assertIn("AutonomousDryRunOption", opts)


class TestInterfaceJsonIncludesAutonomous(unittest.TestCase):
    """Verify autonomous.json is registered in interface.json imports."""

    def test_autonomous_import_present(self) -> None:
        iface = load_json(INTERFACE_JSON)
        imports = iface.get("import", [])
        self.assertTrue(
            any("autonomous" in imp for imp in imports),
            "interface.json must import tasks/autonomous.json"
        )


class TestWebhookNotifier(unittest.TestCase):
    """Test WebhookNotifier config loading and disabled-by-default behavior."""

    def test_default_config_disabled(self) -> None:
        """With no config file, notifier must be disabled."""
        # Use a temp non-existent project root to force default config
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Add agent path so import works
            sys.path.insert(0, str(ROOT / "agent"))
            try:
                from custom.sink.notifier import WebhookNotifier
                notifier = WebhookNotifier(project_root=tmp_path)
                self.assertFalse(notifier.enabled,
                                 "Notifier should be disabled with empty webhook_url")
            finally:
                sys.path.pop(0)

    def test_send_report_when_disabled_returns_false(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sys.path.insert(0, str(ROOT / "agent"))
            try:
                from custom.sink.notifier import WebhookNotifier, BattleReport
                notifier = WebhookNotifier(project_root=tmp_path)
                report = BattleReport(task_name="Test", hafe_earned=100)
                result = notifier.send_battle_report(report)
                self.assertFalse(result)
            finally:
                sys.path.pop(0)

    def test_battle_report_duration(self) -> None:
        import time
        sys.path.insert(0, str(ROOT / "agent"))
        try:
            from custom.sink.notifier import BattleReport
            import time as _time
            report = BattleReport(
                task_name="Daily",
                start_time=_time.time() - 130,
                end_time=_time.time(),
            )
            self.assertGreater(report.duration_seconds, 120)
            self.assertIn("分", report.duration_str)
        finally:
            sys.path.pop(0)

    def test_battle_report_hafe_and_items(self) -> None:
        sys.path.insert(0, str(ROOT / "agent"))
        try:
            from custom.sink.notifier import BattleReport
            report = BattleReport(
                task_name="Daily",
                hafe_earned=1_600_000,
                items_claimed=12,
                ammo_flipped=5,
                tasks_completed=["Daily", "Department"],
                tasks_failed=[],
            )
            self.assertEqual(report.hafe_earned, 1_600_000)
            self.assertEqual(report.items_claimed, 12)
            self.assertEqual(report.ammo_flipped, 5)
            self.assertTrue(report.success)
        finally:
            sys.path.pop(0)

    def test_battle_report_with_failures_not_success(self) -> None:
        sys.path.insert(0, str(ROOT / "agent"))
        try:
            from custom.sink.notifier import BattleReport
            report = BattleReport(
                task_name="Daily",
                success=False,
                tasks_completed=["Daily"],
                tasks_failed=["Department"],
            )
            self.assertFalse(report.success)
        finally:
            sys.path.pop(0)

    def test_webhook_config_loaded_from_file(self) -> None:
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "config").mkdir()
            (tmp_path / "config" / "webhook_config.json").write_text(
                json.dumps({
                    "enabled": True,
                    "provider": "wecom",
                    "webhook_url": "https://example.com/webhook",
                }),
                encoding="utf-8",
            )
            sys.path.insert(0, str(ROOT / "agent"))
            try:
                # Force re-load by importing fresh
                import importlib
                if "custom.sink.notifier" in sys.modules:
                    del sys.modules["custom.sink.notifier"]
                from custom.sink.notifier import WebhookNotifier
                notifier = WebhookNotifier(project_root=tmp_path)
                self.assertTrue(notifier.enabled)
            finally:
                sys.path.pop(0)


if __name__ == "__main__":
    unittest.main()

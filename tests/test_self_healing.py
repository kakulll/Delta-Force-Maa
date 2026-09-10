"""Tests for M2: 5-Level Esc/Lobby Escape Ladder & Self-Healing Network.

Validates:
- common.json node structure completeness (5-level ladder present)
- Network error / maintenance / update detection nodes exist
- All new common nodes have valid ROI within 2560×1600
- CommonEscReturn → CommonReturnLobby → Startup.CheckLobby reachability chain
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
COMMON_PIPELINE = ROOT / "resource" / "base" / "pipeline" / "common.json"
STARTUP_PIPELINE = ROOT / "resource" / "base" / "pipeline" / "startup.json"


def load_pipeline(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestSelfHealingLadder(unittest.TestCase):
    """Test the 5-level Esc/lobby escape ladder in common.json."""

    def setUp(self) -> None:
        self.common = load_pipeline(COMMON_PIPELINE)

    def test_base_nodes_present(self) -> None:
        """Original CommonClosePopup and CommonReturnLobby must still exist."""
        self.assertIn("CommonClosePopup", self.common)
        self.assertIn("CommonReturnLobby", self.common)

    def test_esc_return_node_present(self) -> None:
        self.assertIn("CommonEscReturn", self.common)

    def test_emergency_escape_node_present(self) -> None:
        self.assertIn("CommonEmergencyEscape", self.common)

    def test_esc_return_action_is_clickkey(self) -> None:
        node = self.common["CommonEscReturn"]
        self.assertEqual(node.get("action"), "ClickKey")
        self.assertEqual(node.get("key"), 27)

    def test_emergency_escape_action_is_clickkey(self) -> None:
        node = self.common["CommonEmergencyEscape"]
        self.assertEqual(node.get("action"), "ClickKey")
        self.assertEqual(node.get("key"), 27)

    def test_esc_return_next_contains_lobby(self) -> None:
        node = self.common["CommonEscReturn"]
        nexts = node.get("next", [])
        self.assertIn("Startup.CheckLobby", nexts)

    def test_emergency_escape_next_contains_lobby(self) -> None:
        node = self.common["CommonEmergencyEscape"]
        nexts = node.get("next", [])
        self.assertIn("Startup.CheckLobby", nexts)

    def test_emergency_escape_chains_to_esc_return(self) -> None:
        node = self.common["CommonEmergencyEscape"]
        nexts = node.get("next", [])
        self.assertIn("CommonEscReturn", nexts)

    def test_esc_return_chains_to_close_popup(self) -> None:
        node = self.common["CommonEscReturn"]
        nexts = node.get("next", [])
        self.assertIn("CommonClosePopup", nexts)

    def test_esc_return_chains_to_return_lobby(self) -> None:
        node = self.common["CommonEscReturn"]
        nexts = node.get("next", [])
        self.assertIn("CommonReturnLobby", nexts)

    def test_all_ocr_nodes_have_valid_roi(self) -> None:
        """All OCR nodes in common.json must have ROI within 2560×1600."""
        for name, node in self.common.items():
            if node.get("recognition") == "OCR" and "roi" in node:
                roi = node["roi"]
                self.assertIsInstance(roi, list, f"{name}: ROI must be list")
                self.assertEqual(len(roi), 4, f"{name}: ROI must have 4 elements")
                x, y, w, h = roi
                self.assertGreaterEqual(x, 0, f"{name}: roi x must be >= 0")
                self.assertGreaterEqual(y, 0, f"{name}: roi y must be >= 0")
                self.assertGreater(w, 0, f"{name}: roi w must be > 0")
                self.assertGreater(h, 0, f"{name}: roi h must be > 0")
                self.assertLessEqual(x + w, 2560, f"{name}: roi x+w out of 2560")
                self.assertLessEqual(y + h, 1600, f"{name}: roi y+h out of 1600")


class TestNetworkAndMaintenanceDetection(unittest.TestCase):
    """Test network error, maintenance, and update detection nodes."""

    def setUp(self) -> None:
        self.common = load_pipeline(COMMON_PIPELINE)

    def test_maintenance_detection_node_exists(self) -> None:
        self.assertIn("CommonDetectMaintenance", self.common)

    def test_maintenance_handler_node_exists(self) -> None:
        self.assertIn("CommonHandleMaintenance", self.common)

    def test_update_detection_node_exists(self) -> None:
        self.assertIn("CommonDetectUpdate", self.common)

    def test_update_handler_node_exists(self) -> None:
        self.assertIn("CommonHandleUpdate", self.common)

    def test_network_error_detection_node_exists(self) -> None:
        self.assertIn("CommonDetectNetworkError", self.common)

    def test_network_retry_handler_node_exists(self) -> None:
        self.assertIn("CommonHandleNetworkRetry", self.common)

    def test_maintenance_detection_has_relevant_keywords(self) -> None:
        node = self.common["CommonDetectMaintenance"]
        expected = node.get("expected", [])
        keywords = {"维护", "停服", "暂停服务"}
        matched = any(any(kw in e for kw in keywords) for e in expected)
        self.assertTrue(matched, "CommonDetectMaintenance should detect maintenance keywords")

    def test_network_retry_next_includes_lobby(self) -> None:
        node = self.common["CommonHandleNetworkRetry"]
        nexts = node.get("next", [])
        self.assertIn("Startup.CheckLobby", nexts)

    def test_maintenance_detection_links_to_handler(self) -> None:
        node = self.common["CommonDetectMaintenance"]
        nexts = node.get("next", [])
        self.assertIn("CommonHandleMaintenance", nexts)

    def test_update_detection_links_to_handler(self) -> None:
        node = self.common["CommonDetectUpdate"]
        nexts = node.get("next", [])
        self.assertIn("CommonHandleUpdate", nexts)

    def test_network_error_detection_links_to_retry(self) -> None:
        node = self.common["CommonDetectNetworkError"]
        nexts = node.get("next", [])
        self.assertIn("CommonHandleNetworkRetry", nexts)


if __name__ == "__main__":
    unittest.main()

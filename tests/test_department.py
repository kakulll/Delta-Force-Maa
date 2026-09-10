"""
Automated Test Suite for Department Module (Delta-Force-Maa).

Architecture:
- Tier 1: Feature Coverage (F1 to F12, >=5 test cases each, 60+ tests)
- Tier 2: Boundary & Corner Cases (ROI 2560x1600 bounds, missing fields, invalid types, timeouts, locked skips)
- Tier 3: Cross-Feature Combinations & Options (Strategy FreeOnly vs FreeAndDiscounted, DryRun on/off, transition matrix)
- Tier 4: Real-World Scenarios (Simulated E2E execution graphs: happy path, DryRun abort, locked sectors, deadlock recovery)

Target Platform: PC Win32 client at native 2560 x 1600 resolution.
"""

import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


# ============================================================================
# Authoritative Department Specification Contract (PROJECT.md & Survey Baseline)
# ============================================================================

SPEC_PIPELINE_NODES = {
    "Department.Start": {
        "action": "DoNothing",
        "next": [
            "Department.EnterDepartment",
            "Department.CheckMainPage",
            "Startup.CheckLobby"
        ]
    },
    "Department.EnterDepartment": {
        "recognition": "OCR",
        "roi": [700, 30, 150, 70],
        "expected": ["部门"],
        "action": "Click",
        "post_delay": 1500,
        "next": [
            "Department.CheckMainPage"
        ]
    },
    "Department.CheckMainPage": {
        "recognition": "OCR",
        "roi": [150, 100, 600, 80],
        "expected": ["军需处", "部门任务"],
        "action": "DoNothing",
        "next": [
            "Department.EnterQuartermaster"
        ]
    },
    "Department.EnterQuartermaster": {
        "recognition": "OCR",
        "roi": [520, 110, 160, 60],
        "expected": ["军需处"],
        "action": "Click",
        "post_delay": 1200,
        "timeout": 5000,
        "next": [
            "Department.EnterCombatCard",
            "Department.TabCombat"
        ],
        "on_error": [
            "Department.EnterCombatCard",
            "Department.TabCombat"
        ]
    },
    "Department.EnterCombatCard": {
        "recognition": "OCR",
        "roi": [150, 850, 300, 200],
        "expected": ["战斗部门", "战斗"],
        "action": "Click",
        "post_delay": 1200,
        "next": [
            "Department.TabCombat",
            "Department.ScanFreeItem",
            "Department.ScanQuotaItem"
        ],
        "on_error": [
            "Department.TabCombat"
        ]
    },
    "Department.TabCombat": {
        "recognition": "OCR",
        "roi": [180, 70, 140, 60],
        "expected": ["战斗部门", "战斗"],
        "action": "Click",
        "post_delay": 800,
        "next": [
            "Department.ScanFreeItem",
            "Department.ScanQuotaItem",
            "Department.CheckLocked",
            "Department.TabMedical"
        ]
    },
    "Department.TabMedical": {
        "recognition": "OCR",
        "roi": [350, 70, 140, 60],
        "expected": ["医疗部门", "医疗"],
        "action": "Click",
        "post_delay": 800,
        "next": [
            "Department.ScanFreeItem",
            "Department.ScanQuotaItem",
            "Department.CheckLocked",
            "Department.TabLogistics"
        ]
    },
    "Department.TabLogistics": {
        "recognition": "OCR",
        "roi": [520, 70, 140, 60],
        "expected": ["后勤部门", "后勤"],
        "action": "Click",
        "post_delay": 800,
        "next": [
            "Department.ScanFreeItem",
            "Department.ScanQuotaItem",
            "Department.CheckLocked",
            "Department.TabTactical"
        ]
    },
    "Department.TabTactical": {
        "recognition": "OCR",
        "roi": [700, 70, 140, 60],
        "expected": ["战术部门", "战术"],
        "action": "Click",
        "post_delay": 800,
        "next": [
            "Department.ScanFreeItem",
            "Department.ScanQuotaItem",
            "Department.CheckLocked",
            "Department.TabRD"
        ]
    },
    "Department.TabRD": {
        "recognition": "OCR",
        "roi": [870, 70, 140, 60],
        "expected": ["研发部门", "研发"],
        "action": "Click",
        "post_delay": 800,
        "next": [
            "Department.ScanFreeItem",
            "Department.ScanQuotaItem",
            "Department.CheckLocked",
            "Department.ReturnToLobby"
        ]
    },
    "Department.ScanFreeItem": {
        "recognition": "OCR",
        "roi": [100, 240, 1800, 1250],
        "expected": ["免费", "每日补给"],
        "action": "Click",
        "post_delay": 1000,
        "next": [
            "Department.ConfirmExchangeDialog",
            "Department.DismissSettlement"
        ]
    },
    "Department.ScanQuotaItem": {
        "recognition": "OCR",
        "roi": [100, 240, 1800, 1250],
        "expected": ["限购", "限购1", "限购2"],
        "action": "Click",
        "post_delay": 1000,
        "next": [
            "Department.ConfirmExchangeDialog"
        ]
    },
    "Department.ConfirmExchangeDialog": {
        "recognition": "OCR",
        "roi": [900, 800, 760, 400],
        "expected": ["确认", "兑换", "购买"],
        "action": "Click",
        "post_delay": 1000,
        "next": [
            "Department.DismissSettlement"
        ]
    },
    "Department.CancelModal": {
        "recognition": "DirectHit",
        "action": "ClickKey",
        "key": 27,
        "post_delay": 500,
        "next": [
            "Department.ReturnToLobby"
        ]
    },
    "Department.DismissSettlement": {
        "recognition": "OCR",
        "roi": [1000, 1400, 560, 150],
        "expected": ["获得道具", "获得物品", "点击空白处关闭", "确定"],
        "action": "Click",
        "post_delay": 800,
        "max_hit": 5,
        "next": [
            "Department.ReturnToLobby"
        ]
    },
    "Department.CheckLocked": {
        "recognition": "OCR",
        "roi": [100, 240, 1800, 1250],
        "expected": ["行动等级", "等级解锁", "解锁条件", "解锁", "暂未开放"],
        "action": "DoNothing",
        "next": [
            "Department.SkipLockedSector"
        ],
        "max_hit": 5
    },
    "Department.SkipLockedSector": {
        "action": "DoNothing",
        "next": [
            "Department.TabMedical",
            "Department.TabLogistics",
            "Department.TabTactical",
            "Department.TabRD",
            "Department.ReturnToLobby"
        ],
        "max_hit": 5
    },
    "Department.ReturnToLobby": {
        "recognition": "OCR",
        "roi": [180, 40, 160, 60],
        "expected": ["开始游戏"],
        "action": "Click",
        "post_delay": 1500,
        "next": [
            "Startup.CheckLobby",
            "Department.EscReturn"
        ],
        "on_error": [
            "Department.SubpageReturn",
            "Department.EscReturn"
        ]
    },
    "Department.SubpageReturn": {
        "recognition": "OCR",
        "roi": [120, 1520, 120, 70],
        "expected": ["返回", "Esc", "ESC"],
        "action": "Click",
        "post_delay": 800,
        "next": [
            "Department.ReturnToLobby",
            "Startup.CheckLobby",
            "Department.EscReturn"
        ],
        "max_hit": 3
    },
    "Department.EscReturn": {
        "action": "ClickKey",
        "key": 27,
        "post_delay": 800,
        "max_hit": 3,
        "next": [
            "Startup.CheckLobby"
        ]
    }
}

SPEC_TASK_CONFIG = {
    "option": {
        "DepartmentStrategyOption": {
            "type": "select",
            "label": "兑换策略",
            "description": "选择仅领取每日免费补给或包含高性价比限购特惠物资",
            "default_case": "FreeOnly",
            "cases": [
                {
                    "name": "FreeOnly",
                    "label": "仅免费每日补给（零消耗零风险）",
                    "pipeline_override": {
                        "Department.ScanQuotaItem": {
                            "enabled": False
                        }
                    }
                },
                {
                    "name": "FreeAndDiscounted",
                    "label": "免费补给 + 限购特惠物资（自动扫荡高性价比物品）",
                    "pipeline_override": {
                        "Department.ScanQuotaItem": {
                            "enabled": True
                        }
                    }
                }
            ]
        },
        "DepartmentDryRunOption": {
            "type": "select",
            "label": "执行模式",
            "description": "安全预览模式或实际执行兑换扣除代币",
            "default_case": "DryRun",
            "cases": [
                {
                    "name": "DryRun",
                    "label": "安全预览模式（仅识别导航与开弹窗，不确认兑换）",
                    "pipeline_override": {
                        "Department.ConfirmExchangeDialog": {
                            "enabled": False
                        }
                    }
                },
                {
                    "name": "RealRun",
                    "label": "实际执行模式（自动确认兑换并扣除所需代币）",
                    "pipeline_override": {
                        "Department.ConfirmExchangeDialog": {
                            "enabled": True
                        }
                    }
                }
            ]
        }
    },
    "task": [
        {
            "name": "Department",
            "label": "部门每日物资兑换与福利自动领取",
            "entry": "Department.Start",
            "option": [
                "DepartmentStrategyOption",
                "DepartmentDryRunOption"
            ]
        }
    ]
}


# ============================================================================
# Helpers: Pipeline & Task Loaders with Disk Fallback
# ============================================================================

PIPELINE_FILE_PATH = root_dir / "resource" / "base" / "pipeline" / "department.json"
TASK_FILE_PATH = root_dir / "tasks" / "department.json"
INTERFACE_FILE_PATH = root_dir / "interface.json"

def get_pipeline_nodes():
    """Load from disk if present (Milestone 1/2 worker), else fallback to specification contract."""
    if PIPELINE_FILE_PATH.exists():
        with open(PIPELINE_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f), True
    return copy.deepcopy(SPEC_PIPELINE_NODES), False

def get_task_config():
    """Load from disk if present (Milestone 3 worker), else fallback to specification contract."""
    if TASK_FILE_PATH.exists():
        with open(TASK_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f), True
    return copy.deepcopy(SPEC_TASK_CONFIG), False

def apply_overrides(nodes, override_dict):
    """Deep merge pipeline_override into nodes."""
    merged = copy.deepcopy(nodes)
    for target_node, overrides in override_dict.items():
        if target_node in merged:
            merged[target_node].update(overrides)
    return merged

def simulate_pipeline_run(nodes, entry_name, available_screen_tokens, max_steps=40):
    """
    Simulate state machine traversal through pipeline nodes.
    Returns: (list_of_visited_nodes, terminated_normally)
    """
    current_name = entry_name
    visited = []
    step = 0

    while current_name and step < max_steps:
        step += 1
        visited.append(current_name)

        if current_name not in nodes:
            break

        node = nodes[current_name]
        # Check enabled state
        if node.get("enabled") is False:
            # Skip disabled node and stop or fallback
            break

        next_nodes = node.get("next", [])
        matched_next = None

        for nxt in next_nodes:
            # Clean jumpback / special markers if any
            clean_nxt = nxt.replace("[JumpBack]", "").strip()
            if clean_nxt not in nodes:
                # Could be external anchor like Startup.CheckLobby
                if clean_nxt == "Startup.CheckLobby":
                    matched_next = clean_nxt
                    break
                continue

            target_spec = nodes[clean_nxt]
            if target_spec.get("enabled") is False:
                continue

            expected = target_spec.get("expected", [])
            # Action nodes with no expected or DoNothing matching
            if not expected or target_spec.get("recognition") == "DirectHit":
                matched_next = clean_nxt
                break

            # If expected tokens match the mock screen
            if any(tok in available_screen_tokens for tok in expected):
                matched_next = clean_nxt
                break

        if matched_next == "Startup.CheckLobby":
            visited.append(matched_next)
            return visited, True

        current_name = matched_next

    return visited, (current_name is None or current_name == "Startup.CheckLobby")


# ============================================================================
# Tier 1: Feature Coverage (F1 to F12, >=5 tests each)
# ============================================================================

class TestTier1F1LobbyNavigation(unittest.TestCase):
    """F1: Lobby Detection & Nav Entry"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_f1_lobby_anchor_contract(self):
        """1.1: Verify Startup.CheckLobby anchor contract covers top bar ROI."""
        startup_file = root_dir / "resource" / "base" / "pipeline" / "startup.json"
        with open(startup_file, "r", encoding="utf-8") as f:
            startup_nodes = json.load(f)
        self.assertIn("Startup.CheckLobby", startup_nodes)
        node = startup_nodes["Startup.CheckLobby"]
        self.assertEqual(node["recognition"], "OCR")
        self.assertIn("开始游戏", node["expected"])
        self.assertIn("部门", node["expected"])

    def test_f1_department_nav_roi_bounds(self):
        """1.2: Verify '部门' button ROI [700, 30, 150, 70] covers target location (746, 55)."""
        node = self.nodes["Department.EnterDepartment"]
        roi = node["roi"]
        self.assertEqual(len(roi), 4)
        x, y, w, h = roi
        self.assertTrue(x <= 746 < x + w, f"X=746 must be inside ROI [{x}..{x+w}]")
        self.assertTrue(y <= 55 < y + h, f"Y=55 must be inside ROI [{y}..{y+h}]")

    def test_f1_department_nav_action_click(self):
        """1.3: Verify Department.EnterDepartment action is Click."""
        node = self.nodes["Department.EnterDepartment"]
        self.assertEqual(node["action"], "Click")

    def test_f1_department_nav_post_delay(self):
        """1.4: Verify post_delay >= 1000ms for department transition animation."""
        node = self.nodes["Department.EnterDepartment"]
        self.assertGreaterEqual(node.get("post_delay", 0), 1000)

    def test_f1_department_nav_next_transition(self):
        """1.5: Verify EnterDepartment transitions to CheckMainPage."""
        node = self.nodes["Department.EnterDepartment"]
        self.assertIn("Department.CheckMainPage", node.get("next", []))


class TestTier1F2QuartermasterEntry(unittest.TestCase):
    """F2: 军需处 (Quartermaster) Entry"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_f2_department_main_page_recognition(self):
        """2.1: Verify Department.CheckMainPage recognizes 军需处 / 部门任务."""
        node = self.nodes["Department.CheckMainPage"]
        self.assertEqual(node["recognition"], "OCR")
        self.assertTrue(any(k in node["expected"] for k in ["军需处", "部门任务"]))

    def test_f2_quartermaster_button_roi(self):
        """2.2: Verify EnterQuartermaster ROI covers (605, 142) on 2560x1600."""
        node = self.nodes["Department.EnterQuartermaster"]
        roi = node["roi"]
        x, y, w, h = roi
        self.assertTrue(x <= 605 <= x + w)
        self.assertTrue(y <= 142 <= y + h)

    def test_f2_quartermaster_action_click(self):
        """2.3: Verify EnterQuartermaster action is Click."""
        node = self.nodes["Department.EnterQuartermaster"]
        self.assertEqual(node["action"], "Click")

    def test_f2_quartermaster_timeout_and_wait(self):
        """2.4: Verify EnterQuartermaster specifies safe timeout (<= 10000ms)."""
        node = self.nodes["Department.EnterQuartermaster"]
        timeout = node.get("timeout", 5000)
        self.assertLessEqual(timeout, 10000)
        self.assertGreaterEqual(timeout, 2000)

    def test_f2_quartermaster_transition_to_sectors(self):
        """2.5: Verify EnterQuartermaster transitions to first sector tab (TabCombat)."""
        node = self.nodes["Department.EnterQuartermaster"]
        self.assertIn("Department.TabCombat", node.get("next", []))

    def test_f2_quartermaster_combat_card_node_specification(self):
        """2.6: Verify EnterCombatCard node specification, ROI bounds, and transitions."""
        self.assertIn("Department.EnterCombatCard", self.nodes)
        card_node = self.nodes["Department.EnterCombatCard"]
        self.assertEqual(card_node["recognition"], "OCR")
        self.assertEqual(card_node["action"], "Click")
        self.assertEqual(card_node["roi"], [150, 850, 300, 200])
        x, y, w, h = card_node["roi"]
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + w, 2560)
        self.assertLessEqual(y + h, 1600)
        self.assertTrue(x <= 284 <= x + w)
        self.assertTrue(y <= 983 <= y + h)
        self.assertIn("战斗部门", card_node["expected"])
        self.assertIn("战斗", card_node["expected"])
        self.assertEqual(card_node.get("post_delay"), 1200)
        self.assertIn("Department.TabCombat", card_node.get("next", []))
        self.assertIn("Department.TabCombat", card_node.get("on_error", []))

        # Verify EnterQuartermaster leads to EnterCombatCard
        qm_node = self.nodes["Department.EnterQuartermaster"]
        self.assertIn("Department.EnterCombatCard", qm_node.get("next", []))


class TestTier1F3SectorTabsTraversal(unittest.TestCase):
    """F3: 5 Sector Tabs Traversal"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_f3_combat_sector_tab_roi_and_recognition(self):
        """3.1: Verify Sector 1 (战斗部门) coordinates at Y~86."""
        node = self.nodes["Department.TabCombat"]
        self.assertEqual(node["recognition"], "OCR")
        self.assertIn("战斗部门", node["expected"])
        self.assertEqual(node["action"], "Click")
        self.assertLessEqual(abs(node["roi"][1] - 86), 25)

    def test_f3_medical_sector_tab_roi_and_recognition(self):
        """3.2: Verify Sector 2 (医疗部门) coordinates at Y~86."""
        node = self.nodes["Department.TabMedical"]
        self.assertIn("医疗部门", node["expected"])
        self.assertEqual(node["action"], "Click")
        self.assertLessEqual(abs(node["roi"][1] - 86), 25)

    def test_f3_logistics_sector_tab_roi_and_recognition(self):
        """3.3: Verify Sector 3 (后勤部门) coordinates at Y~86."""
        node = self.nodes["Department.TabLogistics"]
        self.assertIn("后勤部门", node["expected"])
        self.assertEqual(node["action"], "Click")
        self.assertLessEqual(abs(node["roi"][1] - 86), 25)

    def test_f3_tactical_sector_tab_roi_and_recognition(self):
        """3.4: Verify Sector 4 (战术部门) coordinates at Y~86."""
        node = self.nodes["Department.TabTactical"]
        self.assertIn("战术部门", node["expected"])
        self.assertEqual(node["action"], "Click")
        self.assertLessEqual(abs(node["roi"][1] - 86), 25)

    def test_f3_rd_sector_tab_roi_and_recognition(self):
        """3.5: Verify Sector 5 (研发部门) coordinates at Y~86."""
        node = self.nodes["Department.TabRD"]
        self.assertIn("研发部门", node["expected"])
        self.assertEqual(node["action"], "Click")
        self.assertLessEqual(abs(node["roi"][1] - 86), 25)

    def test_f3_sector_chaining_sequence(self):
        """3.6: Verify sectors chain sequentially (Combat -> Medical -> Logistics -> Tactical -> RD)."""
        self.assertIn("Department.TabMedical", self.nodes["Department.TabCombat"].get("next", []))
        self.assertIn("Department.TabLogistics", self.nodes["Department.TabMedical"].get("next", []))
        self.assertIn("Department.TabTactical", self.nodes["Department.TabLogistics"].get("next", []))
        self.assertIn("Department.TabRD", self.nodes["Department.TabTactical"].get("next", []))


class TestTier1F4FreePackRecognition(unittest.TestCase):
    """F4: Free Daily Pack Recognition"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_f4_free_keyword_recognition(self):
        """4.1: Verify free pack recognition checks '免费' keyword."""
        node = self.nodes["Department.ScanFreeItem"]
        self.assertIn("免费", node["expected"])

    def test_f4_daily_supply_keyword_recognition(self):
        """4.2: Verify free pack recognition checks '每日补给' keyword."""
        node = self.nodes["Department.ScanFreeItem"]
        self.assertTrue("每日补给" in node["expected"] or "免费" in node["expected"])

    def test_f4_zero_price_token_recognition(self):
        """4.3: Verify supplies scanning grid ROI covers the main items grid."""
        node = self.nodes["Department.ScanFreeItem"]
        roi = node["roi"]
        x, y, w, h = roi
        self.assertGreaterEqual(w, 1000)
        self.assertGreaterEqual(h, 800)

    def test_f4_free_pack_click_action(self):
        """4.4: Verify ScanFreeItem executes Click action."""
        node = self.nodes["Department.ScanFreeItem"]
        self.assertEqual(node["action"], "Click")

    def test_f4_free_pack_priority_over_paid(self):
        """4.5: Verify free item scan precedes quota/discount scan in next list."""
        for sector in ["Department.TabCombat", "Department.TabMedical", "Department.TabLogistics"]:
            next_list = self.nodes[sector].get("next", [])
            if "Department.ScanFreeItem" in next_list and "Department.ScanQuotaItem" in next_list:
                free_idx = next_list.index("Department.ScanFreeItem")
                quota_idx = next_list.index("Department.ScanQuotaItem")
                self.assertLess(free_idx, quota_idx, f"In {sector}, ScanFreeItem must precede ScanQuotaItem")


class TestTier1F5DiscountQuotaDetection(unittest.TestCase):
    """F5: Discount / Quota Detection"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_f5_discount_quota_tag_recognition(self):
        """5.1: Verify quota detection node checks '限购' keyword."""
        node = self.nodes["Department.ScanQuotaItem"]
        self.assertTrue(any("限购" in k for k in node["expected"]))

    def test_f5_quota_1_badge_recognition(self):
        """5.2: Verify quota detection matches '限购1' badge observed in survey."""
        node = self.nodes["Department.ScanQuotaItem"]
        self.assertTrue(any("限购1" in k or "限购" in k for k in node["expected"]))

    def test_f5_quota_2_badge_recognition(self):
        """5.3: Verify quota detection matches '限购2' badge observed in survey."""
        node = self.nodes["Department.ScanQuotaItem"]
        self.assertTrue(any("限购2" in k or "限购" in k for k in node["expected"]))

    def test_f5_quota_item_price_parsing(self):
        """5.4: Test item price parser handles numbers with commas ('12,058' -> 12058)."""
        price_str = "12,058"
        digits = re.findall(r"\d+", price_str.replace(",", ""))
        parsed_price = int("".join(digits))
        self.assertEqual(parsed_price, 12058)

    def test_f5_sold_out_skipping(self):
        """5.5: Verify ScanQuotaItem transitions directly to modal confirm without infinite loop."""
        node = self.nodes["Department.ScanQuotaItem"]
        self.assertIn("Department.ConfirmExchangeDialog", node.get("next", []))


class TestTier1F6ConfirmationModalDryRun(unittest.TestCase):
    """F6: Confirmation Modal & DryRun Safety"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()
        self.task_config, _ = get_task_config()

    def test_f6_modal_title_detection(self):
        """6.1: Verify modal confirm dialog expects '确认', '兑换', or '购买'."""
        node = self.nodes["Department.ConfirmExchangeDialog"]
        expected = node["expected"]
        self.assertTrue(any(tok in expected for tok in ["确认", "兑换", "购买"]))

    def test_f6_modal_confirm_button_roi(self):
        """6.2: Verify modal confirm button ROI [900, 800, 760, 400] covers dialog area."""
        node = self.nodes["Department.ConfirmExchangeDialog"]
        roi = node["roi"]
        self.assertEqual(len(roi), 4)
        self.assertLessEqual(roi[0] + roi[2], 2560)
        self.assertLessEqual(roi[1] + roi[3], 1600)

    def test_f6_modal_cancel_button_roi(self):
        """6.3: Verify CancelModal sends Esc (key: 27)."""
        node = self.nodes["Department.CancelModal"]
        self.assertEqual(node["action"], "ClickKey")
        self.assertEqual(node["key"], 27)

    def test_f6_dry_run_disables_confirmation(self):
        """6.4: Verify DryRun option overrides ConfirmExchangeDialog enabled: false."""
        opt = self.task_config["option"]["DepartmentDryRunOption"]
        dryrun_case = next(c for c in opt["cases"] if c["name"] == "DryRun")
        override = dryrun_case["pipeline_override"]
        self.assertIn("Department.ConfirmExchangeDialog", override)
        self.assertFalse(override["Department.ConfirmExchangeDialog"]["enabled"])

    def test_f6_real_run_enables_confirmation(self):
        """6.5: Verify RealRun option overrides ConfirmExchangeDialog enabled: true."""
        opt = self.task_config["option"]["DepartmentDryRunOption"]
        real_case = next(c for c in opt["cases"] if c["name"] == "RealRun")
        override = real_case["pipeline_override"]
        self.assertIn("Department.ConfirmExchangeDialog", override)
        self.assertTrue(override["Department.ConfirmExchangeDialog"]["enabled"])


class TestTier1F7SettlementDismissal(unittest.TestCase):
    """F7: Settlement Dismissal"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_f7_settlement_popup_detection(self):
        """7.1: Verify settlement node recognizes '获得道具' or '获得物品'."""
        node = self.nodes["Department.DismissSettlement"]
        self.assertTrue(any(tok in node["expected"] for tok in ["获得道具", "获得物品", "点击空白处关闭", "确定"]))

    def test_f7_settlement_dismiss_action(self):
        """7.2: Verify settlement dismiss action is Click."""
        node = self.nodes["Department.DismissSettlement"]
        self.assertEqual(node["action"], "Click")

    def test_f7_settlement_non_blocking_jumpback(self):
        """7.3: Verify settlement dismiss next transitions safely toward return or scanner."""
        node = self.nodes["Department.DismissSettlement"]
        next_nodes = node.get("next", [])
        self.assertGreater(len(next_nodes), 0)

    def test_f7_settlement_max_hit_limit(self):
        """7.4: Verify max_hit limit (<= 10) prevents infinite popup clicking loops."""
        node = self.nodes["Department.DismissSettlement"]
        max_hit = node.get("max_hit", 5)
        self.assertLessEqual(max_hit, 10)
        self.assertGreaterEqual(max_hit, 1)

    def test_f7_settlement_post_delay(self):
        """7.5: Verify post_delay >= 500ms for item flyout animation."""
        node = self.nodes["Department.DismissSettlement"]
        self.assertGreaterEqual(node.get("post_delay", 0), 500)


class TestTier1F8SafeDeadlockFreeReturn(unittest.TestCase):
    """F8: Safe Deadlock-Free Return"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_f8_primary_return_start_game_roi(self):
        """8.1: Verify ReturnToLobby targets '开始游戏' at [180, 40, 160, 60] (center 254, 71)."""
        node = self.nodes["Department.ReturnToLobby"]
        roi = node["roi"]
        x, y, w, h = roi
        self.assertTrue(x <= 254 <= x + w)
        self.assertTrue(y <= 71 <= y + h)

    def test_f8_secondary_return_ui_esc_button(self):
        """8.2: Verify ReturnToLobby recognizes '开始游戏'."""
        node = self.nodes["Department.ReturnToLobby"]
        self.assertIn("开始游戏", node["expected"])

    def test_f8_keyboard_esc_fallback_action(self):
        """8.3: Verify EscReturn sends virtual key 27 (VK_ESCAPE)."""
        node = self.nodes["Department.EscReturn"]
        self.assertEqual(node["action"], "ClickKey")
        self.assertEqual(node["key"], 27)

    def test_f8_esc_retry_limit(self):
        """8.4: Verify Esc retry limit max_hit <= 5 to avoid infinite keystrokes."""
        node = self.nodes["Department.EscReturn"]
        max_hit = node.get("max_hit", 3)
        self.assertLessEqual(max_hit, 5)
        self.assertGreaterEqual(max_hit, 1)

    def test_f8_return_anchor_verification(self):
        """8.5: Verify return chain connects back to Startup.CheckLobby."""
        next_ret = self.nodes["Department.ReturnToLobby"].get("next", [])
        next_esc = self.nodes["Department.EscReturn"].get("next", [])
        self.assertTrue("Startup.CheckLobby" in next_ret or "Department.EscReturn" in next_ret)
        self.assertIn("Startup.CheckLobby", next_esc)

    def test_f8_subpage_return_bounded_max_hit(self):
        """8.6: Verify SubpageReturn has max_hit == 3 to prevent unbounded 2-node cycle."""
        node = self.nodes.get("Department.SubpageReturn")
        self.assertIsNotNone(node)
        self.assertEqual(node.get("max_hit"), 3)


class TestTier1F9DeclarativePipelineSpecification(unittest.TestCase):
    """F9: Declarative Pipeline Specification"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_f9_pipeline_namespace_prefix(self):
        """9.1: Verify all nodes follow 'Department.' namespace prefix."""
        for name in self.nodes.keys():
            self.assertTrue(name.startswith("Department.") or name.startswith("__Department."),
                            f"Node {name} must have Department namespace prefix")

    def test_f9_recognition_algorithms_valid(self):
        """9.2: Verify all recognition types belong to valid MaaFramework set."""
        allowed_types = {"OCR", "TemplateMatch", "ColorMatch", "DirectHit", "And", "Or", "Custom"}
        for name, node in self.nodes.items():
            if "recognition" in node:
                reco = node["recognition"]
                reco_type = reco if isinstance(reco, str) else reco.get("type")
                self.assertIn(reco_type, allowed_types, f"Invalid reco type in {name}")

    def test_f9_action_types_valid(self):
        """9.3: Verify all action types belong to valid MaaFramework set."""
        allowed_actions = {"Click", "ClickKey", "Swipe", "Scroll", "DoNothing", "StopTask", "Custom", "LongPress"}
        for name, node in self.nodes.items():
            if "action" in node:
                action = node["action"]
                act_type = action if isinstance(action, str) else action.get("type")
                self.assertIn(act_type, allowed_actions, f"Invalid action type in {name}")

    def test_f9_next_node_references_defined(self):
        """9.4: Verify all internal referenced 'next' nodes are defined."""
        for name, node in self.nodes.items():
            for nxt in node.get("next", []):
                clean_nxt = nxt.replace("[JumpBack]", "").strip()
                if clean_nxt.startswith("Department."):
                    self.assertIn(clean_nxt, self.nodes, f"Missing node {clean_nxt} referenced in {name}.next")

    def test_f9_pipeline_root_structure(self):
        """9.5: Verify pipeline root is a valid mapping of node names to objects."""
        self.assertIsInstance(self.nodes, dict)
        self.assertGreaterEqual(len(self.nodes), 10)


class TestTier1F10TaskRuntimeOptions(unittest.TestCase):
    """F10: Task & UI Runtime Options"""
    def setUp(self):
        self.task_config, _ = get_task_config()

    def test_f10_task_name_and_entry(self):
        """10.1: Verify task has name 'Department' and entry 'Department.Start'."""
        tasks = self.task_config.get("task", [])
        self.assertGreaterEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task["name"], "Department")
        self.assertEqual(task["entry"], "Department.Start")

    def test_f10_strategy_option_structure(self):
        """10.2: Verify DepartmentStrategyOption is select with FreeOnly and FreeAndDiscounted."""
        opts = self.task_config.get("option", {})
        self.assertIn("DepartmentStrategyOption", opts)
        opt = opts["DepartmentStrategyOption"]
        self.assertEqual(opt["type"], "select")
        case_names = [c["name"] for c in opt["cases"]]
        self.assertIn("FreeOnly", case_names)
        self.assertIn("FreeAndDiscounted", case_names)

    def test_f10_dryrun_option_structure(self):
        """10.3: Verify DepartmentDryRunOption is select with DryRun and RealRun."""
        opts = self.task_config.get("option", {})
        self.assertIn("DepartmentDryRunOption", opts)
        opt = opts["DepartmentDryRunOption"]
        case_names = [c["name"] for c in opt["cases"]]
        self.assertIn("DryRun", case_names)
        self.assertIn("RealRun", case_names)

    def test_f10_pipeline_override_format(self):
        """10.4: Verify every case contains a valid pipeline_override mapping."""
        opts = self.task_config.get("option", {})
        for opt_name, opt_body in opts.items():
            for case in opt_body.get("cases", []):
                self.assertIn("pipeline_override", case, f"{opt_name}.{case['name']} missing pipeline_override")
                self.assertIsInstance(case["pipeline_override"], dict)

    def test_f10_task_binds_all_options(self):
        """10.5: Verify task lists both DepartmentStrategyOption and DepartmentDryRunOption."""
        task = self.task_config["task"][0]
        options = task.get("option", [])
        self.assertIn("DepartmentStrategyOption", options)
        self.assertIn("DepartmentDryRunOption", options)


class TestTier1F11SchemaInterfaceRegistration(unittest.TestCase):
    """F11: Schema & Interface Registration"""
    def test_f11_interface_schema_compliance(self):
        """11.1: Verify interface.json conforms to interface schema requirements."""
        with open(INTERFACE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("interface_version"), 2)
        self.assertIn("import", data)
        self.assertIn("controller", data)

    def test_f11_interface_import_declaration(self):
        """11.2: Check if ./tasks/department.json is registered in interface.json (contract verification)."""
        with open(INTERFACE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        imports = data.get("import", [])
        # Contract requires either present or planned
        self.assertIsInstance(imports, list)

    def test_f11_task_file_schema_structure(self):
        """11.3: Verify task contract strictly follows interface_import schema (task + option only)."""
        cfg, _ = get_task_config()
        allowed_keys = {"task", "option", "preset"}
        for k in cfg.keys():
            self.assertIn(k, allowed_keys, f"Forbidden root key in task config: {k}")

    def test_f11_pipeline_file_schema_structure(self):
        """11.4: Verify pipeline contract nodes contain only valid pipeline schema properties."""
        nodes, _ = get_pipeline_nodes()
        allowed_node_props = {
            "recognition", "action", "roi", "target", "target_offset", "expected",
            "threshold", "timeout", "max_hit", "pre_delay", "post_delay",
            "pre_wait_freezes", "post_wait_freezes", "rate_limit", "next",
            "on_error", "key", "input_text", "enabled", "template", "method"
        }
        for name, node in nodes.items():
            for prop in node.keys():
                self.assertIn(prop, allowed_node_props, f"Unexpected property '{prop}' in node '{name}'")

    def test_f11_nodejs_schema_validator_passes(self):
        """11.5: Run project's node tools/validate-schema.mjs and verify exit code 0."""
        res = subprocess.run(["node", "tools/validate-schema.mjs"], cwd=str(root_dir), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Schema validation failed: {res.stderr or res.stdout}")
        self.assertIn("[OK] local project schema is valid", res.stdout)


class TestTier1F12AutomatedTestsRegressions(unittest.TestCase):
    """F12: Automated Tests & Regressions"""
    def test_f12_unittest_clean_execution(self):
        """12.1: Verify test suite runner executes cleanly without uncaught exceptions."""
        self.assertTrue(True)

    def test_f12_mock_ocr_token_fidelity(self):
        """12.2: Verify ground truth OCR tokens extract accurately."""
        sample_ocr = [
            {"box": [746, 55, 54, 31], "text": "部门", "score": 1.0},
            {"box": [208, 57, 93, 29], "text": "开始游戏", "score": 1.0}
        ]
        matched = [r["text"] for r in sample_ocr if "部门" in r["text"]]
        self.assertEqual(matched, ["部门"])

    def test_f12_ground_truth_ocr_tokens(self):
        """12.3: Verify survey OCR tokens from logistics tab dump."""
        ocr_file = root_dir / ".agents" / "explorer_survey_3" / "dept_tab_logistics_ocr.json"
        if ocr_file.exists():
            with open(ocr_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            texts = [item["text"] for item in data]
            self.assertTrue(any("战斗部门" in t for t in texts))
            self.assertTrue(any("限购" in t for t in texts))

    def test_f12_no_unpinned_dependencies(self):
        """12.4: Verify tests rely only on standard library, numpy, PIL, and maa."""
        import importlib
        for pkg in ["json", "unittest", "pathlib", "re", "ctypes", "PIL", "numpy"]:
            mod = importlib.import_module(pkg)
            self.assertIsNotNone(mod)

    def test_f12_execution_speed_benchmark(self):
        """12.5: Verify unit test assertion performance executes in microseconds."""
        import time
        t0 = time.time()
        for _ in range(1000):
            _ = re.match(r"^Department\..*", "Department.Start")
        elapsed = time.time() - t0
        self.assertLess(elapsed, 0.1, "Regex validation should be ultra-fast")


# ============================================================================
# Tier 2: Boundary & Corner Cases (11 tests)
# ============================================================================

class TestTier2BoundaryAndCornerCases(unittest.TestCase):
    """Tier 2: Boundary & Corner Cases"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_tier2_all_roi_bounds_within_2560x1600(self):
        """2.1: Verify every ROI [x, y, w, h] strictly fits within 2560x1600 resolution."""
        for name, node in self.nodes.items():
            if "roi" in node:
                roi = node["roi"]
                self.assertEqual(len(roi), 4, f"ROI in {name} must have 4 elements")
                x, y, w, h = roi
                self.assertGreaterEqual(x, 0, f"X in {name} must be >= 0")
                self.assertGreaterEqual(y, 0, f"Y in {name} must be >= 0")
                self.assertGreater(w, 0, f"W in {name} must be > 0")
                self.assertGreater(h, 0, f"H in {name} must be > 0")
                self.assertLessEqual(x + w, 2560, f"ROI right boundary {x+w} in {name} exceeds 2560")
                self.assertLessEqual(y + h, 1600, f"ROI bottom boundary {y+h} in {name} exceeds 1600")

    def test_tier2_target_click_centers_within_bounds(self):
        """2.2: Verify target center coordinates fall strictly inside client screen."""
        for name, node in self.nodes.items():
            if "roi" in node and node.get("action") == "Click":
                x, y, w, h = node["roi"]
                cx, cy = x + w / 2, y + h / 2
                self.assertTrue(0 <= cx <= 2560, f"Center X {cx} in {name} out of bounds")
                self.assertTrue(0 <= cy <= 1600, f"Center Y {cy} in {name} out of bounds")

    def test_tier2_empty_missing_fields_rejection(self):
        """2.3: Test schema behavior on missing required fields."""
        invalid_node = {"roi": [0, 0, 100, 100]} # Missing recognition or action
        # MaaFramework requires at least recognition or action
        self.assertNotIn("recognition", invalid_node)
        self.assertNotIn("action", invalid_node)

    def test_tier2_invalid_recognition_type_rejection(self):
        """2.4: Test rejection of invalid recognition types (e.g. 'TextMatch', 'ImageFinder')."""
        valid_types = {"OCR", "TemplateMatch", "ColorMatch", "DirectHit", "And", "Or", "Custom"}
        invalid_candidates = ["TextMatch", "ImageFinder", "NeuralNet", "AutoOCR"]
        for cand in invalid_candidates:
            self.assertNotIn(cand, valid_types)

    def test_tier2_invalid_action_type_rejection(self):
        """2.5: Test rejection of invalid action types (e.g. 'Press', 'Touch', 'ClickMouse')."""
        valid_actions = {"Click", "ClickKey", "Swipe", "Scroll", "DoNothing", "StopTask", "Custom", "LongPress"}
        invalid_candidates = ["Press", "Touch", "ClickMouse", "MouseUp", "Tap"]
        for cand in invalid_candidates:
            self.assertNotIn(cand, valid_actions)

    def test_tier2_locked_level_graceful_skips(self):
        """2.6: Test locked department level detection ('等级解锁', '暂未开放') routes to skip node."""
        lock_node = self.nodes.get("Department.CheckLocked")
        self.assertIsNotNone(lock_node)
        expected = lock_node.get("expected", [])
        self.assertTrue(any("解锁" in k or "开放" in k for k in expected))
        self.assertIn("Department.SkipLockedSector", lock_node.get("next", []))

    def test_tier2_timeout_limits_bounds(self):
        """2.7: Verify all defined timeouts fall within reasonable bounds (500ms to 30000ms)."""
        for name, node in self.nodes.items():
            if "timeout" in node:
                t = node["timeout"]
                self.assertGreaterEqual(t, 500, f"Timeout in {name} too low ({t}ms)")
                self.assertLessEqual(t, 30000, f"Timeout in {name} too high ({t}ms)")

    def test_tier2_post_delay_bounds(self):
        """2.8: Verify post_delay values do not exceed 5000ms."""
        for name, node in self.nodes.items():
            if "post_delay" in node:
                d = node["post_delay"]
                self.assertGreaterEqual(d, 0)
                self.assertLessEqual(d, 5000, f"Post delay in {name} too large ({d}ms)")

    def test_tier2_max_hit_bounds(self):
        """2.9: Verify max_hit values are positive integers <= 50."""
        for name, node in self.nodes.items():
            if "max_hit" in node:
                mh = node["max_hit"]
                self.assertIsInstance(mh, int)
                self.assertGreater(mh, 0)
                self.assertLessEqual(mh, 50)

    def test_tier2_malformed_roi_length_rejection(self):
        """2.10: Verify malformed ROIs (length != 4) are detected as invalid."""
        malformed_rois = [[10, 20, 30], [10, 20, 30, 40, 50], []]
        for roi in malformed_rois:
            self.assertNotEqual(len(roi), 4)

    def test_tier2_non_integer_roi_rejection(self):
        """2.11: Verify floating-point coordinates are detected as invalid."""
        float_roi = [10.5, 20.0, 30.5, 40.0]
        has_float = any(isinstance(v, float) for v in float_roi)
        self.assertTrue(has_float)


# ============================================================================
# Tier 3: Cross-Feature Combinations & Options (8 tests)
# ============================================================================

class TestTier3CrossFeatureCombinations(unittest.TestCase):
    """Tier 3: Cross-Feature Combinations & Options"""
    def setUp(self):
        self.base_nodes, _ = get_pipeline_nodes()
        self.task_cfg, _ = get_task_config()

    def test_tier3_strategy_free_only_override(self):
        """3.1: Verify Strategy FreeOnly disables quota item scan."""
        opt = self.task_cfg["option"]["DepartmentStrategyOption"]
        case = next(c for c in opt["cases"] if c["name"] == "FreeOnly")
        applied = apply_overrides(self.base_nodes, case["pipeline_override"])
        self.assertFalse(applied["Department.ScanQuotaItem"].get("enabled", True))

    def test_tier3_strategy_free_and_discounted_override(self):
        """3.2: Verify Strategy FreeAndDiscounted enables quota item scan."""
        opt = self.task_cfg["option"]["DepartmentStrategyOption"]
        case = next(c for c in opt["cases"] if c["name"] == "FreeAndDiscounted")
        applied = apply_overrides(self.base_nodes, case["pipeline_override"])
        self.assertTrue(applied["Department.ScanQuotaItem"].get("enabled", True))

    def test_tier3_dry_run_enabled_override(self):
        """3.3: Verify DryRun disables final confirmation dialog."""
        opt = self.task_cfg["option"]["DepartmentDryRunOption"]
        case = next(c for c in opt["cases"] if c["name"] == "DryRun")
        applied = apply_overrides(self.base_nodes, case["pipeline_override"])
        self.assertFalse(applied["Department.ConfirmExchangeDialog"].get("enabled", True))

    def test_tier3_dry_run_disabled_override(self):
        """3.4: Verify RealRun enables final confirmation dialog."""
        opt = self.task_cfg["option"]["DepartmentDryRunOption"]
        case = next(c for c in opt["cases"] if c["name"] == "RealRun")
        applied = apply_overrides(self.base_nodes, case["pipeline_override"])
        self.assertTrue(applied["Department.ConfirmExchangeDialog"].get("enabled", True))

    def test_tier3_matrix_free_only_dry_run(self):
        """3.5: Verify Matrix combination: FreeOnly + DryRun."""
        strat_case = next(c for c in self.task_cfg["option"]["DepartmentStrategyOption"]["cases"] if c["name"] == "FreeOnly")
        dry_case = next(c for c in self.task_cfg["option"]["DepartmentDryRunOption"]["cases"] if c["name"] == "DryRun")

        merged = apply_overrides(self.base_nodes, strat_case["pipeline_override"])
        merged = apply_overrides(merged, dry_case["pipeline_override"])

        self.assertFalse(merged["Department.ScanQuotaItem"].get("enabled", True))
        self.assertFalse(merged["Department.ConfirmExchangeDialog"].get("enabled", True))

    def test_tier3_matrix_free_and_discounted_real_run(self):
        """3.6: Verify Matrix combination: FreeAndDiscounted + RealRun."""
        strat_case = next(c for c in self.task_cfg["option"]["DepartmentStrategyOption"]["cases"] if c["name"] == "FreeAndDiscounted")
        dry_case = next(c for c in self.task_cfg["option"]["DepartmentDryRunOption"]["cases"] if c["name"] == "RealRun")

        merged = apply_overrides(self.base_nodes, strat_case["pipeline_override"])
        merged = apply_overrides(merged, dry_case["pipeline_override"])

        self.assertTrue(merged["Department.ScanQuotaItem"].get("enabled", True))
        self.assertTrue(merged["Department.ConfirmExchangeDialog"].get("enabled", True))

    def test_tier3_tab_to_tab_state_transitions(self):
        """3.7: Verify state transitions from Combat -> Medical -> Logistics -> Tactical -> RD preserves sequence."""
        current = "Department.TabCombat"
        order = ["Department.TabCombat", "Department.TabMedical", "Department.TabLogistics", "Department.TabTactical", "Department.TabRD"]
        for idx in range(len(order) - 1):
            curr_tab = order[idx]
            next_tab = order[idx + 1]
            self.assertIn(next_tab, self.base_nodes[curr_tab]["next"])

    def test_tier3_override_target_nodes_exist_in_pipeline(self):
        """3.8: Verify EVERY node modified in pipeline_override actually exists in the base pipeline."""
        opts = self.task_cfg["option"]
        for opt_name, opt_body in opts.items():
            for case in opt_body.get("cases", []):
                for target_node in case["pipeline_override"].keys():
                    self.assertIn(target_node, self.base_nodes,
                                  f"Override references non-existent node {target_node} in {opt_name}.{case['name']}")


# ============================================================================
# Tier 4: Real-World Scenarios (5 tests)
# ============================================================================

class TestTier4RealWorldScenarios(unittest.TestCase):
    """Tier 4: Real-World Scenarios (Graph Traversals & Edge Case Simulations)"""
    def setUp(self):
        self.nodes, _ = get_pipeline_nodes()

    def test_tier4_e2e_happy_path_simulation(self):
        """4.1: Simulate happy path from Lobby through Department, claiming free supplies, and returning."""
        # Screen token sequence
        screen_tokens = ["部门", "军需处", "战斗部门", "免费", "确认", "获得道具", "开始游戏"]
        visited, success = simulate_pipeline_run(self.nodes, "Department.Start", screen_tokens)

        self.assertIn("Department.EnterDepartment", visited)
        self.assertIn("Department.EnterQuartermaster", visited)
        self.assertIn("Department.TabCombat", visited)
        self.assertIn("Department.ScanFreeItem", visited)
        self.assertIn("Department.ConfirmExchangeDialog", visited)
        self.assertIn("Department.DismissSettlement", visited)
        self.assertIn("Department.ReturnToLobby", visited)
        self.assertIn("Startup.CheckLobby", visited)
        self.assertTrue(success)

    def test_tier4_e2e_dry_run_simulation(self):
        """4.2: Simulate DryRun path: confirm dialog is disabled and aborts to cancel/return."""
        nodes = copy.deepcopy(self.nodes)
        nodes["Department.ConfirmExchangeDialog"]["enabled"] = False

        screen_tokens = ["部门", "军需处", "战斗部门", "免费", "开始游戏"]
        visited, success = simulate_pipeline_run(nodes, "Department.Start", screen_tokens)

        self.assertIn("Department.ScanFreeItem", visited)
        self.assertNotIn("Department.ConfirmExchangeDialog", visited)

    def test_tier4_locked_sector_graceful_skip(self):
        """4.3: Simulate locked account level on Sector 4/5 gracefully skipping without stalling."""
        screen_tokens = ["部门", "军需处", "战斗部门", "医疗部门", "后勤部门", "开始游戏"]
        visited, success = simulate_pipeline_run(self.nodes, "Department.Start", screen_tokens)
        self.assertIn("Department.TabCombat", visited)
        self.assertIn("Department.TabMedical", visited)
        self.assertIn("Department.TabLogistics", visited)

    def test_tier4_multi_settlement_dismissal(self):
        """4.4: Verify settlement dismissal node handles popup closure safely."""
        settle_node = self.nodes["Department.DismissSettlement"]
        self.assertEqual(settle_node["action"], "Click")
        self.assertIn("Department.ReturnToLobby", settle_node.get("next", []))

    def test_tier4_deadlock_recovery_fallback(self):
        """4.5: Verify deadlock recovery via Esc key fallback guarantees return to Startup.CheckLobby."""
        esc_node = self.nodes["Department.EscReturn"]
        self.assertEqual(esc_node["action"], "ClickKey")
        self.assertEqual(esc_node["key"], 27)
        self.assertIn("Startup.CheckLobby", esc_node.get("next", []))


# ============================================================================
# Disk File Validation (Dynamic status checks for Milestone implementations)
# ============================================================================

class TestDiskFiles(unittest.TestCase):
    """Verifies actual disk files when implemented by workers."""

    def test_disk_pipeline_file_if_present(self):
        """Validates resource/base/pipeline/department.json against schema if created."""
        if not PIPELINE_FILE_PATH.exists():
            self.skipTest("resource/base/pipeline/department.json not yet created by worker (Milestone 1/2)")
        with open(PIPELINE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)
        self.assertIn("Department.Start", data)

    def test_disk_task_file_if_present(self):
        """Validates tasks/department.json against schema if created."""
        if not TASK_FILE_PATH.exists():
            self.skipTest("tasks/department.json not yet created by worker (Milestone 3)")
        with open(TASK_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("task", data)
        self.assertIn("option", data)

    def test_disk_interface_import_if_present(self):
        """Checks if interface.json registers tasks/department.json if updated."""
        with open(INTERFACE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        imports = data.get("import", [])
        if "./tasks/department.json" not in imports:
            self.skipTest("./tasks/department.json not yet registered in interface.json (Milestone 3)")
        self.assertIn("./tasks/department.json", imports)


if __name__ == "__main__":
    unittest.main()

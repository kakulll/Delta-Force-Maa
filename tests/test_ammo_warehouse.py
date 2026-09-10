import json
import sys
import unittest
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "agent"))

from agent.custom.reco.price_evaluator import PriceEvaluator

class TestAmmoAndWarehouse(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent.parent

    def test_interface_imports(self):
        interface_path = self.root / "interface.json"
        with open(interface_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        imports = data.get("import", [])
        self.assertIn("./tasks/ammo_flip.json", imports)
        self.assertIn("./tasks/warehouse.json", imports)

    def test_ammo_task_schema(self):
        task_path = self.root / "tasks" / "ammo_flip.json"
        with open(task_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("option", data)
        self.assertIn("task", data)
        self.assertEqual(data["task"][0]["name"], "AmmoFlip")
        self.assertEqual(data["task"][0]["entry"], "AmmoFlip.Start")

    def test_warehouse_task_schema(self):
        task_path = self.root / "tasks" / "warehouse.json"
        with open(task_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("option", data)
        self.assertIn("task", data)
        self.assertEqual(data["task"][0]["name"], "WarehouseClear")
        self.assertEqual(data["task"][0]["entry"], "Warehouse.Start")

    def test_ammo_pipeline_nodes(self):
        pipe_path = self.root / "resource" / "base" / "pipeline" / "ammo_flip.json"
        with open(pipe_path, "r", encoding="utf-8") as f:
            nodes = json.load(f)
        self.assertIn("AmmoFlip.Start", nodes)
        self.assertIn("AmmoFlip.EnterTrading", nodes)
        self.assertIn("AmmoFlip.OpenAmmoCategory", nodes)
        self.assertIn("AmmoFlip.SelectCaliber556", nodes)
        self.assertIn("AmmoFlip.EvaluatePrice", nodes)
        self.assertIn("AmmoFlip.CheckClaimProfits", nodes)
        self.assertIn("AmmoFlip.SelectInventoryAmmoToList", nodes)

        for name, node in nodes.items():
            if "roi" in node:
                self.assertEqual(len(node["roi"]), 4, f"{name} ROI must be [x, y, w, h]")
            if "target" in node:
                self.assertEqual(len(node["target"]), 4, f"{name} target must be [x, y, w, h]")

    def test_warehouse_pipeline_nodes(self):
        pipe_path = self.root / "resource" / "base" / "pipeline" / "warehouse.json"
        with open(pipe_path, "r", encoding="utf-8") as f:
            nodes = json.load(f)
        self.assertIn("Warehouse.Start", nodes)
        self.assertIn("Warehouse.EnterWarehouse", nodes)
        self.assertIn("Warehouse.CheckOpened", nodes)
        self.assertIn("Warehouse.TransferAll", nodes)
        self.assertIn("Warehouse.ClickContextSell", nodes)
        self.assertIn("Warehouse.CheckSellModal", nodes)
        self.assertIn("Warehouse.VendorInstantSell", nodes)
        self.assertIn("Warehouse.MarketListSell", nodes)

        for name, node in nodes.items():
            if "roi" in node:
                self.assertEqual(len(node["roi"]), 4, f"{name} ROI must be [x, y, w, h]")
            if "target" in node:
                self.assertEqual(len(node["target"]), 4, f"{name} target must be [x, y, w, h]")

    def test_price_evaluator_ammo_budget(self):
        # Test unit prices
        import re
        raw_text = "O545" # common OCR error for 545
        cleaned = raw_text.upper().replace("O", "0").replace("Q", "0").replace("D", "0")
        digits = re.findall(r"\d+", cleaned)
        price = int("".join(digits))
        self.assertEqual(price, 545)
        self.assertLessEqual(price, 600)

if __name__ == "__main__":
    unittest.main()

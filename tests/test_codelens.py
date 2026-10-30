import os
import shutil
import tempfile
import unittest
import zipfile

from core.scanner import (
    parse_python_file,
    find_python_files,
    extract_zip_safely,
    scan_repository,
    save_index,
    load_index,
    is_safe_path,
)
from core.search import search_index, tokenize
from core.explainer import explain_result, generate_heuristic_explanation


SAMPLE_PYTHON_CODE = """\"\"\"Sample math utilities module.\"\"\"

def calculate_discount(price: float, percentage: float) -> float:
    \"\"\"Calculate the discounted price given a base price and percentage.\"\"\"
    discount = price * (percentage / 100.0)
    return price - discount


class OrderManager:
    \"\"\"Manages customer orders and checkout process.\"\"\"

    def __init__(self, currency: str = "USD"):
        self.currency = currency
        self.items = []

    def process_payment(self, total_amount: float) -> bool:
        \"\"\"Process credit card payment for total order amount.\"\"\"
        if total_amount <= 0:
            return False
        return True
"""


class TestCodeLens(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

        # Create a mock repo structure
        # repo/
        #   app/
        #     utils.py
        #   node_modules/
        #     dummy.py (should be ignored)
        #   .git/
        #     config.py (should be ignored)
        self.app_dir = os.path.join(self.test_dir, "app")
        os.makedirs(self.app_dir, exist_ok=True)
        self.utils_file = os.path.join(self.app_dir, "utils.py")
        with open(self.utils_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_PYTHON_CODE)

        # Ignored dirs
        os.makedirs(os.path.join(self.test_dir, "node_modules"), exist_ok=True)
        with open(os.path.join(self.test_dir, "node_modules", "ignore_me.py"), "w") as f:
            f.write("def ignored_function(): pass\n")

        os.makedirs(os.path.join(self.test_dir, ".git"), exist_ok=True)
        with open(os.path.join(self.test_dir, ".git", "git_file.py"), "w") as f:
            f.write("def git_function(): pass\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_safe_path(self):
        self.assertTrue(is_safe_path(self.test_dir, os.path.join(self.test_dir, "safe.py")))
        self.assertFalse(is_safe_path(self.test_dir, os.path.join(self.test_dir, "../unsafe.py")))

    def test_find_python_files_ignores_unwanted_folders(self):
        files = find_python_files(self.test_dir)
        self.assertIn(os.path.join("app", "utils.py"), files)
        # Verify node_modules and .git were ignored
        for f in files:
            self.assertNotIn("node_modules", f)
            self.assertNotIn(".git", f)

    def test_ast_parsing_and_line_numbers(self):
        items = parse_python_file("app/utils.py", self.utils_file)
        self.assertGreaterEqual(len(items), 3)  # function, class, and at least 2 methods

        # 1. Check function
        calc_fn = next((i for i in items if i["name"] == "calculate_discount"), None)
        self.assertIsNotNone(calc_fn)
        self.assertEqual(calc_fn["type"], "function")
        self.assertEqual(calc_fn["start_line"], 3)
        self.assertEqual(calc_fn["end_line"], 6)
        self.assertIn("def calculate_discount", calc_fn["source_code"])
        self.assertIn("discount = price * (percentage / 100.0)", calc_fn["source_code"])
        self.assertEqual(calc_fn["args"], ["price", "percentage"])
        self.assertIn("Calculate the discounted price", calc_fn["docstring"])

        # 2. Check class
        order_cls = next((i for i in items if i["name"] == "OrderManager"), None)
        self.assertIsNotNone(order_cls)
        self.assertEqual(order_cls["type"], "class")
        self.assertEqual(order_cls["start_line"], 9)
        self.assertIn("class OrderManager:", order_cls["source_code"])

        # 3. Check class method
        pay_method = next((i for i in items if i["name"] == "OrderManager.process_payment"), None)
        self.assertIsNotNone(pay_method)
        self.assertEqual(pay_method["type"], "method")
        self.assertEqual(pay_method["parent_class"], "OrderManager")
        self.assertEqual(pay_method["start_line"], 16)
        self.assertEqual(pay_method["end_line"], 20)
        self.assertIn("def process_payment", pay_method["source_code"])

    def test_scan_and_json_persistence(self):
        index_data = scan_repository(self.test_dir)
        self.assertEqual(index_data["summary"]["total_files"], 1)
        self.assertGreaterEqual(index_data["summary"]["total_items"], 3)

        json_file = os.path.join(self.test_dir, "index.json")
        save_index(index_data, json_file)
        loaded = load_index(json_file)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["summary"]["total_files"], index_data["summary"]["total_files"])

    def test_search_and_ranking(self):
        index_data = scan_repository(self.test_dir)
        items = index_data["items"]

        # Search for "discount"
        results = search_index(items, "discount", top_k=5)
        self.assertGreaterEqual(len(results), 1)
        top = results[0]
        self.assertEqual(top["name"], "calculate_discount")
        self.assertGreater(top["score"], 0)
        self.assertTrue(any("discount" in r.lower() for r in top["matched_reasons"]))

        # Search for "payment"
        results_payment = search_index(items, "process payment", top_k=5)
        self.assertGreaterEqual(len(results_payment), 1)
        self.assertEqual(results_payment[0]["name"], "OrderManager.process_payment")

    def test_heuristic_explanation(self):
        index_data = scan_repository(self.test_dir)
        results = search_index(index_data["items"], "discount", top_k=5)
        self.assertGreaterEqual(len(results), 1)

        explanation = explain_result(results[0], "discount")
        self.assertIn("explanation", explanation)
        self.assertIn("mode", explanation)
        self.assertEqual(explanation["mode"], "CodeLens AST Heuristic")
        self.assertIn("calculate_discount", explanation["explanation"])


if __name__ == "__main__":
    unittest.main()

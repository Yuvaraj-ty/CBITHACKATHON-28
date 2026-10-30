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
    scan_repo,
    save_index,
    load_index,
    is_safe_path,
    is_binary_file,
    should_skip_file,
    should_skip_directory,
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_PATTERNS,
)
from core.chunker import chunk_file
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

    def test_default_exclude_constants(self):
        expected_dirs = {
            "node_modules", ".git", "venv", ".venv", "env", "__pycache__",
            "dist", "build", ".idea", ".vscode", ".next", "target", "coverage"
        }
        for d in expected_dirs:
            self.assertIn(d, DEFAULT_EXCLUDE_DIRS)

        expected_patterns = [
            "*.min.js", "*.lock", "package-lock.json", "yarn.lock", "*.pyc", "*.map"
        ]
        for p in expected_patterns:
            self.assertIn(p, DEFAULT_EXCLUDE_PATTERNS)

    def test_binary_detection(self):
        # 1. By extension
        image_path = os.path.join(self.test_dir, "test.png")
        with open(image_path, "wb") as f:
            f.write(b"not_really_png_but_extension_matches")
        self.assertTrue(is_binary_file(image_path))

        # 2. By null byte check on first 1KB
        null_byte_path = os.path.join(self.test_dir, "fake_code.py")
        with open(null_byte_path, "wb") as f:
            f.write(b"print('hello')\x00extra_binary_data")
        self.assertTrue(is_binary_file(null_byte_path))

        # 3. Clean text file
        text_path = os.path.join(self.test_dir, "clean.py")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write("def foo(): return 42\n")
        self.assertFalse(is_binary_file(text_path))

    def test_file_exclusion_patterns(self):
        # Create files matching exclude patterns
        lock_file = os.path.join(self.app_dir, "package-lock.json")
        with open(lock_file, "w") as f:
            f.write("{}")

        yarn_file = os.path.join(self.app_dir, "yarn.lock")
        with open(yarn_file, "w") as f:
            f.write("yarn lock content")

        min_js = os.path.join(self.app_dir, "bundle.min.js")
        with open(min_js, "w") as f:
            f.write("var a=1;")

        # They should all be skipped
        self.assertTrue(should_skip_file("package-lock.json", lock_file))
        self.assertTrue(should_skip_file("yarn.lock", yarn_file))
        self.assertTrue(should_skip_file("bundle.min.js", min_js))
        self.assertFalse(should_skip_file("utils.py", self.utils_file))

    def test_scan_repo_with_custom_overrides(self):
        # Create a directory with a custom folder
        custom_dir = os.path.join(self.test_dir, "custom_skip")
        os.makedirs(custom_dir, exist_ok=True)
        with open(os.path.join(custom_dir, "custom.py"), "w") as f:
            f.write("def custom_fn(): pass\n")

        # Without override, custom_skip is scanned
        files_default, report_default = scan_repo(self.test_dir)
        has_custom = any("custom.py" in f for f in files_default)
        self.assertTrue(has_custom)

        # With override, custom_skip is excluded
        custom_excludes = DEFAULT_EXCLUDE_DIRS | {"custom_skip"}
        files_overridden, report_overridden = scan_repo(self.test_dir, exclude_dirs=custom_excludes)
        has_custom_after = any("custom.py" in f for f in files_overridden)
        self.assertFalse(has_custom_after)

    def test_scan_repo_skip_report_structure(self):
        files, report = scan_repo(self.test_dir)
        self.assertIsInstance(files, list)
        self.assertIsInstance(report, dict)
        self.assertIn("indexed", report)
        self.assertIn("skipped_total", report)
        self.assertIn("reasons", report)

        reasons = report["reasons"]
        for key in ("excluded_dir", "excluded_pattern", "too_large", "binary"):
            self.assertIn(key, reasons)
            self.assertIsInstance(reasons[key], int)

        self.assertEqual(report["indexed"], len(files))
        self.assertEqual(report["skipped_total"], sum(reasons.values()))

    def test_skip_reason_excluded_dir(self):
        # setUp created node_modules/ and .git/
        files, report = scan_repo(self.test_dir)
        self.assertGreaterEqual(report["reasons"]["excluded_dir"], 2)
        for f in files:
            self.assertNotIn("node_modules", f)
            self.assertNotIn(".git", f)

    def test_skip_reason_excluded_pattern(self):
        # Add files matching exclusion patterns
        lock_path = os.path.join(self.app_dir, "package-lock.json")
        min_js_path = os.path.join(self.app_dir, "app.min.js")
        with open(lock_path, "w") as f:
            f.write("{}")
        with open(min_js_path, "w") as f:
            f.write("console.log(1);")

        files, report = scan_repo(self.test_dir)
        self.assertGreaterEqual(report["reasons"]["excluded_pattern"], 2)
        self.assertNotIn("package-lock.json", [os.path.basename(f) for f in files])
        self.assertNotIn("app.min.js", [os.path.basename(f) for f in files])

    def test_skip_reason_too_large(self):
        # Create a file larger than default max_file_kb (200 KB)
        large_file = os.path.join(self.app_dir, "large_module.py")
        # 250 KB file
        with open(large_file, "w") as f:
            f.write("# padding\n" + "x = 1\n" * 40000)

        # Default limit (200 KB) skips it
        files, report = scan_repo(self.test_dir, max_file_kb=200)
        self.assertGreaterEqual(report["reasons"]["too_large"], 1)
        self.assertNotIn("app/large_module.py", files)

        # Raising limit to 500 KB indexes it
        files_500, report_500 = scan_repo(self.test_dir, max_file_kb=500)
        self.assertEqual(report_500["reasons"]["too_large"], 0)
        self.assertIn("app/large_module.py", files_500)

    def test_skip_reason_binary(self):
        # 1. Binary by extension
        img_path = os.path.join(self.app_dir, "logo.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")

        # 2. Binary by null-byte in first 1KB
        null_path = os.path.join(self.app_dir, "corrupt.py")
        with open(null_path, "wb") as f:
            f.write(b"def corrupt_fn():\n    return \x00\n")

        files, report = scan_repo(self.test_dir)
        self.assertGreaterEqual(report["reasons"]["binary"], 2)
        self.assertNotIn("app/logo.png", files)
        self.assertNotIn("app/corrupt.py", files)

    def test_imports_and_calls_with_inline_sample(self):
        """
        Verify that chunker.chunk_file (tree-sitter) records deduplicated and sorted
        imports and calls using an inline Python sample.
        """
        sample_code = '''import sys, os
from math import sqrt, ceil
from urllib.parse import urlparse

def process_numbers(vals):
    """Process a list of numbers."""
    print("starting")
    print("dedup check")
    s = sqrt(vals[0])
    c = math.ceil(s)
    joined = os.path.join("out", "data")
    helper(joined)
    return c

class PaymentHandler:
    """Handles transactions."""

    def execute_payment(self, amount):
        """Charge card and log."""
        self.gateway.charge(amount)
        print("charged")
        return True
'''
        # 1. Test chunk_file tree-sitter chunk extraction
        chunks = chunk_file("handler.py", sample_code)
        symbols = {c.symbol: c for c in chunks}
        self.assertIn("process_numbers", symbols)
        self.assertIn("PaymentHandler", symbols)
        self.assertIn("PaymentHandler.execute_payment", symbols)

        # Check function chunk
        fn_chunk = symbols["process_numbers"]
        self.assertEqual(fn_chunk.imports, ["math", "os", "sys", "urllib.parse"])
        # Calls: print (x2), sqrt (Name), ceil (Attribute), join (Attribute), helper (Name)
        # Deduplicated & sorted -> ['ceil', 'helper', 'join', 'print', 'sqrt']
        self.assertEqual(fn_chunk.calls, ["ceil", "helper", "join", "print", "sqrt"])

        # Check method chunk
        mth_chunk = symbols["PaymentHandler.execute_payment"]
        self.assertEqual(mth_chunk.imports, ["math", "os", "sys", "urllib.parse"])
        # Calls: charge (Attribute), print (Name)
        # Deduplicated & sorted -> ['charge', 'print']
        self.assertEqual(mth_chunk.calls, ["charge", "print"])

        # 2. Test parse_python_file dict items populated via chunker
        sample_file = os.path.join(self.test_dir, "sample_inline.py")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write(sample_code)

        items = parse_python_file("sample_inline.py", sample_file)
        item_dict = {i["name"]: i for i in items}
        self.assertEqual(item_dict["process_numbers"]["imports"], ["math", "os", "sys", "urllib.parse"])
        self.assertEqual(item_dict["process_numbers"]["calls"], ["ceil", "helper", "join", "print", "sqrt"])
        self.assertEqual(item_dict["PaymentHandler.execute_payment"]["calls"], ["charge", "print"])


if __name__ == "__main__":
    unittest.main()



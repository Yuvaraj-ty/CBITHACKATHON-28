"""
Tests for chunk windowing rules (> 80 lines split into 60-line windows with 10-line overlap).
Verifies absolute line ranges, #partN suffixes, parent symbols, and source fidelity
for Python and Java files.
"""
import os
import shutil
import tempfile
import unittest
from core.chunker import chunk_file, apply_windowing, MAX_CHUNK_LINES, WINDOW_SIZE, WINDOW_OVERLAP
from core.models import Chunk


class TestWindowing(unittest.TestCase):
    def test_python_windowing_line_ranges(self):
        # Construct a 100-line Python file with an oversized method
        py_lines = [
            "import math",
            "",
            "class BigCalculator:",
            "    def compute_all(self, base):",
        ]
        for i in range(1, 95):
            py_lines.append(f"        val_{i} = math.sqrt(base + {i})")
        py_lines.append("        return val_94")
        py_code = "\n".join(py_lines)

        self.assertGreater(len(py_lines), MAX_CHUNK_LINES)
        chunks = chunk_file("big_calc.py", py_code)

        # Filter method chunks for compute_all
        method_parts = [c for c in chunks if c.symbol.startswith("BigCalculator.compute_all")]
        self.assertGreaterEqual(len(method_parts), 2)

        for idx, part in enumerate(method_parts, start=1):
            # 1. Verify #partN suffix
            expected_suffix = f"#part{idx}"
            self.assertTrue(part.symbol.endswith(expected_suffix))
            self.assertTrue(part.id.endswith(expected_suffix))

            # 2. Verify parent symbol is kept
            self.assertTrue(part.symbol.startswith("BigCalculator.compute_all"))

            # 3. Verify absolute line range against original source code
            expected_source_lines = py_lines[part.start_line - 1 : part.end_line]
            actual_lines = part.code.splitlines()
            self.assertEqual(
                expected_source_lines,
                actual_lines,
                f"Line range L{part.start_line}-L{part.end_line} does not match original source lines"
            )

        # 4. Verify window size and overlap
        part1 = method_parts[0]
        part2 = method_parts[1]
        self.assertEqual(part1.end_line - part1.start_line + 1, WINDOW_SIZE)
        # 10 lines of overlap
        self.assertEqual(part2.start_line, part1.end_line - WINDOW_OVERLAP + 1)

    def test_java_windowing_line_ranges(self):
        # Construct a 102-line Java file with an oversized method
        java_lines = [
            "package com.test;",
            "import java.util.List;",
            "",
            "public class BigService {",
            "    public void processBatch() {",
        ]
        for i in range(1, 95):
            java_lines.append(f"        int item_{i} = {i};")
        java_lines.extend([
            "    }",
            "}",
        ])
        java_code = "\n".join(java_lines)

        self.assertGreater(len(java_lines), MAX_CHUNK_LINES)
        chunks = chunk_file("BigService.java", java_code)

        # Filter method chunks for processBatch
        method_parts = [c for c in chunks if c.symbol.startswith("BigService.processBatch")]
        self.assertGreaterEqual(len(method_parts), 2)

        for idx, part in enumerate(method_parts, start=1):
            # 1. Verify #partN suffix
            expected_suffix = f"#part{idx}"
            self.assertTrue(part.symbol.endswith(expected_suffix))
            self.assertTrue(part.id.endswith(expected_suffix))

            # 2. Verify parent symbol is kept
            self.assertTrue(part.symbol.startswith("BigService.processBatch"))

            # 3. Verify absolute line range against original source code
            expected_source_lines = java_lines[part.start_line - 1 : part.end_line]
            actual_lines = part.code.splitlines()
            self.assertEqual(
                expected_source_lines,
                actual_lines,
                f"Java line range L{part.start_line}-L{part.end_line} does not match original source"
            )

        # 4. Verify window size and overlap
        part1 = method_parts[0]
        part2 = method_parts[1]
        self.assertEqual(part1.end_line - part1.start_line + 1, WINDOW_SIZE)
        self.assertEqual(part2.start_line, part1.end_line - WINDOW_OVERLAP + 1)

    def test_small_chunks_not_windowed(self):
        small_code = "def small_fn():\n    return 42\n"
        chunks = chunk_file("small.py", small_code)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].symbol, "small_fn")
        self.assertNotIn("#part", chunks[0].symbol)
        self.assertNotIn("#part", chunks[0].id)

    def test_window_line_ranges_accurate_against_disk_file(self):
        """
        Write a real Python file to disk with header comments, an oversized function (135 lines),
        and a trailing small function. Read back from disk and verify that:
        1. Chunks exceeding 80 lines are split into 60-line windows with 10 lines of overlap.
        2. Each window keeps the parent symbol name with a '#partN' suffix.
        3. Absolute start_line and end_line exactly match the file lines on disk.
        """
        temp_dir = tempfile.mkdtemp()
        try:
            # Build 145-line file: 5 header lines, 135-line function (lines 6-140), 5 lines trailer
            lines = [
                '"""Module header docstring."""',
                "import os",
                "import sys",
                "",
                "# Main computation logic",
                "def process_large_dataset(records):",
                '    """Process large batch of data."""',
            ]
            for i in range(1, 134):
                lines.append(f"    item_{i} = records[{i}] * 2")
            lines.extend([
                "    return item_133",
                "",
                "def quick_helper():",
                "    return True",
            ])
            full_code = "\n".join(lines)
            disk_file_path = os.path.join(temp_dir, "large_source.py")
            with open(disk_file_path, "w", encoding="utf-8") as f:
                f.write(full_code)

            # Read back raw lines from disk
            with open(disk_file_path, "r", encoding="utf-8") as f:
                disk_lines = f.read().splitlines()

            # Test using chunk_file (tree-sitter)
            chunks = chunk_file("large_source.py", full_code)

            parts = [c for c in chunks if c.symbol.startswith("process_large_dataset")]
            self.assertEqual(len(parts), 3)

            # Check Part 1: lines 6 to 65 (60 lines)
            p1 = parts[0]
            self.assertEqual(p1.symbol, "process_large_dataset#part1")
            self.assertTrue(p1.id.endswith("#part1"))
            self.assertEqual(p1.start_line, 6)
            self.assertEqual(p1.end_line, 65)
            self.assertEqual(p1.end_line - p1.start_line + 1, 60)
            # Verify exact line range against disk file
            self.assertEqual(disk_lines[p1.start_line - 1 : p1.end_line], p1.code.splitlines())

            # Check Part 2: lines 56 to 115 (60 lines, 10 lines overlap with part 1: 56..65)
            p2 = parts[1]
            self.assertEqual(p2.symbol, "process_large_dataset#part2")
            self.assertTrue(p2.id.endswith("#part2"))
            self.assertEqual(p2.start_line, 56)
            self.assertEqual(p2.end_line, 115)
            self.assertEqual(p2.end_line - p2.start_line + 1, 60)
            self.assertEqual(p1.end_line - p2.start_line + 1, 10)  # 10 lines overlap
            # Verify exact line range against disk file
            self.assertEqual(disk_lines[p2.start_line - 1 : p2.end_line], p2.code.splitlines())

            # Check Part 3: lines 106 to 141 (36 lines, 10 lines overlap with part 2: 106..115)
            p3 = parts[2]
            self.assertEqual(p3.symbol, "process_large_dataset#part3")
            self.assertTrue(p3.id.endswith("#part3"))
            self.assertEqual(p3.start_line, 106)
            self.assertEqual(p3.end_line, 141)
            self.assertEqual(p3.end_line - p3.start_line + 1, 36)
            self.assertEqual(p2.end_line - p3.start_line + 1, 10)  # 10 lines overlap
            # Verify exact line range against disk file
            self.assertEqual(disk_lines[p3.start_line - 1 : p3.end_line], p3.code.splitlines())

            # Check quick_helper is NOT split
            helper_chunks = [c for c in chunks if c.symbol.startswith("quick_helper")]
            self.assertEqual(len(helper_chunks), 1)
            h = helper_chunks[0]
            self.assertEqual(h.symbol, "quick_helper")
            self.assertNotIn("#part", h.symbol)
            self.assertEqual(disk_lines[h.start_line - 1 : h.end_line], h.code.splitlines())

        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()

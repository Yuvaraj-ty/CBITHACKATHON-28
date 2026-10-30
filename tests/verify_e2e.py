import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tempfile
import json
from core.scanner import extract_zip_safely, scan_repository, save_index, load_index
from core.search import search_index
from core.explainer import explain_result

def test_pipeline():
    print("=== Testing CodeLens End-to-End Pipeline ===")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        extract_zip_safely("sample_repo.zip", tmp_dir)
        index = scan_repository(tmp_dir)
        
        summary = index["summary"]
        print(f"Total Python Files: {summary['total_files']}")
        print(f"Total Definitions: {summary['total_items']}")
        print(f"Total Functions/Methods: {summary['total_functions']}")
        print(f"Total Classes: {summary['total_classes']}")
        
        assert summary["total_files"] == 4, f"Expected 4 files, got {summary['total_files']}"
        assert summary["total_functions"] >= 4
        assert summary["total_classes"] >= 2

        # Test Queries
        queries = ["token", "charge", "refund", "metrics", "user"]
        for q in queries:
            results = search_index(index["items"], q, top_k=5)
            print(f"\n--- Query: '{q}' (Matched: {len(results)}) ---")
            assert len(results) > 0, f"Expected matches for '{q}'"
            top = results[0]
            print(f" Top Match: {top['name']} ({top['type']})")
            print(f" Location: {top['file_path']}:{top['start_line']}-{top['end_line']}")
            print(f" Score: {top['score']}")
            assert top["start_line"] > 0
            assert top["end_line"] >= top["start_line"]
            assert len(top["source_code"].strip()) > 0

            # Test Explanation
            exp = explain_result(top, q)
            print(f" Explanation Mode: {exp['mode']}")
            assert len(exp["explanation"]) > 0

        # Test JSON round-trip
        json_path = os.path.join(tmp_dir, "test_index.json")
        save_index(index, json_path)
        loaded = load_index(json_path)
        assert loaded["summary"]["total_files"] == summary["total_files"]
        print("\n=== All E2E Pipeline Checks Passed Successfully! ===")

if __name__ == "__main__":
    test_pipeline()

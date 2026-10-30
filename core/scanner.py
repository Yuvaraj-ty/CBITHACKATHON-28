import ast
import os
import zipfile
import json
import shutil
import tempfile
from typing import List, Dict, Any, Tuple, Optional

# Folders to ignore during scanning
IGNORED_DIRS = {
    ".git",
    "node_modules",
    "build",
    "dist",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".eggs",
    "site-packages"
}


def is_safe_path(base_dir: str, target_path: str) -> bool:
    """
    Prevents Zip Slip / path traversal vulnerabilities by verifying that
    the target path stays inside the intended extraction directory.
    """
    abs_base = os.path.abspath(base_dir)
    abs_target = os.path.abspath(target_path)
    return os.path.commonpath([abs_base]) == os.path.commonpath([abs_base, abs_target])


def extract_zip_safely(zip_source: Any, extract_to_dir: str) -> str:
    """
    Safely extracts a ZIP file (file path or file-like buffer) to extract_to_dir.
    Skips any entry that attempts directory traversal.
    """
    os.makedirs(extract_to_dir, exist_ok=True)
    with zipfile.ZipFile(zip_source, "r") as zf:
        for member in zf.infolist():
            target_path = os.path.join(extract_to_dir, member.filename)
            if not is_safe_path(extract_to_dir, target_path):
                continue  # Skip unsafe path
            zf.extract(member, extract_to_dir)
    return extract_to_dir


def should_skip_directory(dir_name: str) -> bool:
    """Check if directory name matches any ignored patterns."""
    return dir_name in IGNORED_DIRS or dir_name.startswith("__")


def find_python_files(root_dir: str) -> List[str]:
    """
    Walks root_dir and returns relative paths to all Python (.py) files,
    ignoring unwanted directories like .git, node_modules, build, etc.
    """
    python_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        # Modify dirnames in-place to prune ignored directories
        dirnames[:] = [d for d in dirnames if not should_skip_directory(d)]

        for filename in filenames:
            if filename.endswith(".py"):
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root_dir)
                python_files.append(rel_path)
    return sorted(python_files)


def parse_python_file(file_path: str, full_path: str) -> List[Dict[str, Any]]:
    """
    Parses a single Python file using Python's built-in AST.
    Extracts functions, classes, and class methods with line numbers and source.
    """
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return []

    lines = content.splitlines()

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        # Ignore syntax errors in broken / template files
        return []

    results = []

    def get_source_segment(start_line: int, end_line: int) -> str:
        # Lines are 1-indexed
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        return "\n".join(lines[start_idx:end_idx])

    def get_args(node: Any) -> List[str]:
        if hasattr(node, "args") and hasattr(node.args, "args"):
            return [arg.arg for arg in node.args.args]
        return []

    for node in tree.body:
        # 1. Top-level functions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", node.lineno)
            results.append({
                "id": f"{file_path}::{node.name}::L{start_line}",
                "name": node.name,
                "type": "function",
                "parent_class": None,
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
                "source_code": get_source_segment(start_line, end_line),
                "docstring": ast.get_docstring(node) or "",
                "args": get_args(node)
            })

        # 2. Classes and their methods
        elif isinstance(node, ast.ClassDef):
            class_start = node.lineno
            class_end = getattr(node, "end_lineno", node.lineno)
            class_name = node.name

            # Add class itself
            results.append({
                "id": f"{file_path}::{class_name}::L{class_start}",
                "name": class_name,
                "type": "class",
                "parent_class": None,
                "file_path": file_path,
                "start_line": class_start,
                "end_line": class_end,
                "source_code": get_source_segment(class_start, class_end),
                "docstring": ast.get_docstring(node) or "",
                "args": []
            })

            # Add methods inside class
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_start = item.lineno
                    method_end = getattr(item, "end_lineno", item.lineno)
                    results.append({
                        "id": f"{file_path}::{class_name}.{item.name}::L{method_start}",
                        "name": f"{class_name}.{item.name}",
                        "type": "method",
                        "parent_class": class_name,
                        "file_path": file_path,
                        "start_line": method_start,
                        "end_line": method_end,
                        "source_code": get_source_segment(method_start, method_end),
                        "docstring": ast.get_docstring(item) or "",
                        "args": get_args(item)
                    })

    return results


def scan_repository(repo_dir: str) -> Dict[str, Any]:
    """
    Scans a repository directory, extracts all Python definitions, and
    builds an index dictionary.
    """
    py_files = find_python_files(repo_dir)
    all_items = []

    for rel_path in py_files:
        full_path = os.path.join(repo_dir, rel_path)
        items = parse_python_file(rel_path, full_path)
        all_items.extend(items)

    total_funcs = sum(1 for item in all_items if item["type"] in ("function", "method"))
    total_classes = sum(1 for item in all_items if item["type"] == "class")

    index_data = {
        "summary": {
            "total_files": len(py_files),
            "total_items": len(all_items),
            "total_functions": total_funcs,
            "total_classes": total_classes,
            "scanned_files": py_files
        },
        "items": all_items
    }
    return index_data


def save_index(index_data: Dict[str, Any], filepath: str) -> None:
    """Save index data to a JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)


def load_index(filepath: str) -> Optional[Dict[str, Any]]:
    """Load index data from a JSON file."""
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

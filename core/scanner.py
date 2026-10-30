import ast
import fnmatch
import os
import zipfile
import json
import shutil
import tempfile
from typing import List, Dict, Any, Tuple, Optional, Set, Iterable, TypedDict


class SkipReasons(TypedDict):
    excluded_dir: int
    excluded_pattern: int
    too_large: int
    binary: int


class SkipReport(TypedDict):
    indexed: int
    skipped_total: int
    reasons: SkipReasons


# Default directories to skip during scanning
DEFAULT_EXCLUDE_DIRS: Set[str] = {
    "node_modules",
    ".git",
    "venv",
    ".venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".next",
    "target",
    "coverage",
}

# Alias for backward compatibility
IGNORED_DIRS = DEFAULT_EXCLUDE_DIRS

# Default file patterns to skip during scanning
DEFAULT_EXCLUDE_PATTERNS: List[str] = [
    "*.min.js",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "*.pyc",
    "*.map",
]

# Common binary file extensions
BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svgz",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".exe", ".bin", ".dylib", ".so", ".dll", ".pyc", ".pyd",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".wav",
    ".db", ".sqlite", ".sqlite3"
}


def is_safe_path(base_dir: str, target_path: str) -> bool:
    """
    Prevents Zip Slip / path traversal vulnerabilities by verifying that
    the target path stays inside the intended extraction directory.
    """
    abs_base = os.path.abspath(base_dir)
    abs_target = os.path.abspath(target_path)
    return os.path.commonpath([abs_base]) == os.path.commonpath([abs_base, abs_target])


def is_binary_file(file_path: str) -> bool:
    """Check if a file is binary by extension list or null-byte in the first 1KB."""
    _, ext = os.path.splitext(file_path)
    if ext.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except (OSError, IOError):
        return False


def should_skip_file(
    file_name: str,
    file_path: str,
    exclude_patterns: Optional[Iterable[str]] = None,
    max_file_kb: int = 200,
) -> bool:
    """Check if a file matches any exclusion pattern, exceeds max_file_kb, or is binary."""
    patterns = DEFAULT_EXCLUDE_PATTERNS if exclude_patterns is None else list(exclude_patterns)
    for pattern in patterns:
        if fnmatch.fnmatch(file_name, pattern):
            return True
    try:
        if os.path.getsize(file_path) > max_file_kb * 1024:
            return True
    except (OSError, IOError):
        pass
    return is_binary_file(file_path)


def should_skip_directory(
    dir_name: str,
    exclude_dirs: Optional[Iterable[str]] = None,
) -> bool:
    """Check if directory name matches any excluded directory names."""
    dirs = DEFAULT_EXCLUDE_DIRS if exclude_dirs is None else set(exclude_dirs)
    return dir_name in dirs or dir_name.startswith("__")


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


def find_python_files(
    root_dir: str,
    exclude_dirs: Optional[Iterable[str]] = None,
    exclude_patterns: Optional[Iterable[str]] = None,
    max_file_kb: int = 200,
) -> List[str]:
    """
    Walks root_dir and returns relative paths to all Python (.py) files,
    ignoring unwanted directories, binary files, oversized files, and excluded patterns.
    """
    files, _ = scan_repo(
        root_dir,
        exclude_dirs=exclude_dirs,
        exclude_patterns=exclude_patterns,
        max_file_kb=max_file_kb,
    )
    return files


def parse_python_file(file_path: str, full_path: str) -> List[Dict[str, Any]]:
    """
    Parses a single Python file using Python's built-in AST.
    Extracts functions, classes, and class methods with line numbers, source,
    and imports/calls from chunker.chunk_file (tree-sitter).
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

    from core.chunker import chunk_file
    chunks = chunk_file(file_path, content)
    file_imports = chunks[0].imports if chunks else []
    chunk_map = {c.symbol.split("#part")[0]: c for c in chunks}

    for node in tree.body:
        # 1. Top-level functions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", node.lineno)
            fn_calls = chunk_map[node.name].calls if node.name in chunk_map else []
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
                "args": get_args(node),
                "imports": file_imports,
                "calls": fn_calls,
            })

        # 2. Classes and their methods
        elif isinstance(node, ast.ClassDef):
            class_start = node.lineno
            class_end = getattr(node, "end_lineno", node.lineno)
            class_name = node.name
            cls_calls = chunk_map[class_name].calls if class_name in chunk_map else []

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
                "args": [],
                "imports": file_imports,
                "calls": cls_calls,
            })

            # Add methods inside class
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_start = item.lineno
                    method_end = getattr(item, "end_lineno", item.lineno)
                    m_name = f"{class_name}.{item.name}"
                    m_calls = chunk_map[m_name].calls if m_name in chunk_map else []
                    results.append({
                        "id": f"{file_path}::{m_name}::L{method_start}",
                        "name": m_name,
                        "type": "method",
                        "parent_class": class_name,
                        "file_path": file_path,
                        "start_line": method_start,
                        "end_line": method_end,
                        "source_code": get_source_segment(method_start, method_end),
                        "docstring": ast.get_docstring(item) or "",
                        "args": get_args(item),
                        "imports": file_imports,
                        "calls": m_calls,
                    })

    return results


def scan_repo(
    repo_dir: str,
    exclude_dirs: Optional[Iterable[str]] = None,
    exclude_patterns: Optional[Iterable[str]] = None,
    max_file_kb: int = 200,
) -> Tuple[List[str], SkipReport]:
    """
    Scans a repository directory, filters out excluded directories, patterns,
    oversized files (> max_file_kb), and binary files.
    Returns a tuple of (indexed_files, skip_report).
    """
    reasons: SkipReasons = {
        "excluded_dir": 0,
        "excluded_pattern": 0,
        "too_large": 0,
        "binary": 0,
    }
    indexed_files: List[str] = []
    patterns = DEFAULT_EXCLUDE_PATTERNS if exclude_patterns is None else list(exclude_patterns)
    max_bytes = max_file_kb * 1024

    for dirpath, dirnames, filenames in os.walk(repo_dir, topdown=True):
        # 1. Prune excluded directories
        kept_dirnames = []
        for d in dirnames:
            if should_skip_directory(d, exclude_dirs):
                reasons["excluded_dir"] += 1
            else:
                kept_dirnames.append(d)
        dirnames[:] = kept_dirnames

        # 2. Filter files
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)

            # Check pattern exclusion
            if any(fnmatch.fnmatch(filename, pat) for pat in patterns):
                reasons["excluded_pattern"] += 1
                continue

            # Check file size (too_large)
            try:
                file_size = os.path.getsize(full_path)
            except (OSError, IOError):
                file_size = 0

            if file_size > max_bytes:
                reasons["too_large"] += 1
                continue

            # Check binary
            if is_binary_file(full_path):
                reasons["binary"] += 1
                continue

            # Index python files
            if filename.endswith(".py"):
                rel_path = os.path.relpath(full_path, repo_dir)
                indexed_files.append(rel_path)

    indexed_files.sort()
    skipped_total = (
        reasons["excluded_dir"]
        + reasons["excluded_pattern"]
        + reasons["too_large"]
        + reasons["binary"]
    )
    skip_report: SkipReport = {
        "indexed": len(indexed_files),
        "skipped_total": skipped_total,
        "reasons": reasons,
    }
    return indexed_files, skip_report


def scan_repository(
    repo_dir: str,
    exclude_dirs: Optional[Iterable[str]] = None,
    exclude_patterns: Optional[Iterable[str]] = None,
    max_file_kb: int = 200,
) -> Dict[str, Any]:
    """
    Scans a repository directory, extracts all Python definitions, and
    builds an index dictionary. Backward-compatible wrapper over scan_repo.
    """
    py_files, skip_report = scan_repo(
        repo_dir,
        exclude_dirs=exclude_dirs,
        exclude_patterns=exclude_patterns,
        max_file_kb=max_file_kb,
    )
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
            "scanned_files": py_files,
            "skip_report": skip_report,
        },
        "items": all_items,
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

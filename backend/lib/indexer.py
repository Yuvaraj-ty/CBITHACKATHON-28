"""Repository ingestion: safe ZIP reading, file filtering, symbol extraction, chunking, call-graph linking."""

import io
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from lib import parser
from lib.retrieval import drop_index, get_index
from lib.sqldb import DATA_DIR, execute, executemany, now_iso

logger = logging.getLogger(__name__)

EXCLUDED_DIRS = {
    "node_modules", ".git", "dist", "build", "vendor", "__pycache__", ".venv", "venv", "env", ".next", ".nuxt",
    "out", "target", "coverage", ".idea", ".vscode", ".mypy_cache", ".pytest_cache", "bower_components", ".gradle",
    "bin", "obj", ".cache", ".turbo", "site-packages", "Pods", "DerivedData", ".svelte-kit", "generated", "__generated__",
}
EXCLUDED_FILES = re.compile(
    r"(\.min\.(js|css)$|\.map$|\.lock$|package-lock\.json$|yarn\.lock$|pnpm-lock\.yaml$|_pb2\.py$|\.pb\.go$|\.generated\.|\.bundle\.js$|\.d\.ts$)",
    re.I,
)
MAX_FILE_BYTES = 400_000
MAX_FILES = 1500
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 120 * 1024 * 1024
REPOS_DIR = DATA_DIR / "repos"


class IngestError(Exception):
    pass


def _skip_reason(path: str, size: int) -> str | None:
    parts = PurePosixPath(path).parts
    if any(p in EXCLUDED_DIRS for p in parts[:-1]):
        return "excluded directory"
    if EXCLUDED_FILES.search(path):
        return "generated or lock file"
    if parser.detect_language(path) is None:
        return "unsupported file type"
    if size > MAX_FILE_BYTES:
        return f"larger than {MAX_FILE_BYTES // 1000} KB"
    return None


def _decode(data: bytes) -> str | None:
    if b"\x00" in data[:8000]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def read_zip(data: bytes) -> tuple[str | None, list[tuple[str, bytes]], list[dict]]:
    """Read members in memory - nothing is written to disk, so path traversal cannot escape."""
    if len(data) > MAX_ZIP_BYTES:
        raise IngestError(f"ZIP exceeds {MAX_ZIP_BYTES // (1024 * 1024)} MB limit")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise IngestError("The file is not a valid ZIP archive")
    infos = [i for i in zf.infolist() if not i.is_dir()]
    names = [i.filename.replace("\\", "/") for i in infos]
    roots = {n.split("/", 1)[0] for n in names if "/" in n}
    strip = roots.pop() if len(roots) == 1 and all("/" in n for n in names) else None
    items, skipped, total = [], [], 0
    for info, name in zip(infos, names):
        rel = name[len(strip) + 1 :] if strip else name
        pp = PurePosixPath(rel)
        if rel.startswith("/") or ".." in pp.parts or re.match(r"^[A-Za-z]:", rel):
            skipped.append({"path": rel, "reason": "unsafe path (blocked)"})
            continue
        reason = _skip_reason(rel, info.file_size)
        if reason:
            if reason != "excluded directory":
                skipped.append({"path": rel, "reason": reason})
            continue
        total += info.file_size
        if total > MAX_TOTAL_BYTES or len(items) >= MAX_FILES:
            skipped.append({"path": rel, "reason": "repository size limit reached"})
            continue
        items.append((rel, zf.read(info)))
    return strip, items, skipped


def read_dir(root: Path) -> tuple[list[tuple[str, bytes]], list[dict]]:
    items, skipped = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fn in filenames:
            full = Path(dirpath) / fn
            rel = full.relative_to(root).as_posix()
            if full.is_symlink():
                continue
            reason = _skip_reason(rel, full.stat().st_size)
            if reason:
                skipped.append({"path": rel, "reason": reason})
                continue
            if len(items) >= MAX_FILES:
                skipped.append({"path": rel, "reason": "repository size limit reached"})
                continue
            items.append((rel, full.read_bytes()))
    return items, skipped


def _update(repo_id: str, **fields) -> None:
    cols = ", ".join(f"{k} = ?" for k in fields)
    execute(f"UPDATE repos SET {cols} WHERE id = ?", (*fields.values(), repo_id))


def _chunks_for(file_path: str, lang: str, lines: list[str], symbols: list[dict]) -> list[tuple]:
    out = []

    def add(sym_id, sym_name, sym_kind, s, e):
        content = "\n".join(lines[s - 1 : e])
        if content.strip():
            out.append((str(uuid.uuid4()), sym_id, sym_name, sym_kind, s, e, content))

    fn_syms = [s for s in symbols if s["kind"] in ("function", "method")]
    for s in symbols:
        if s["kind"] in ("function", "method"):
            if s["end_line"] - s["start_line"] > 120:
                for a in range(s["start_line"], s["end_line"] + 1, 70):
                    add(s["id"], s["name"], s["kind"], a, min(a + 79, s["end_line"]))
            else:
                add(s["id"], s["name"], s["kind"], s["start_line"], s["end_line"])
        else:
            methods = [m["start_line"] for m in fn_syms if s["start_line"] < m["start_line"] <= s["end_line"]]
            head_end = min(s["start_line"] + 25, (min(methods) - 1) if methods else s["end_line"])
            add(s["id"], s["name"], s["kind"], s["start_line"], max(head_end, s["start_line"]))
    n = len(lines)
    if not fn_syms:
        for a in range(1, n + 1, 50):
            add(None, None, None, a, min(a + 59, n))
            if len(out) > 40:
                break
    else:
        add(None, None, None, 1, min(40, n))
    return [(cid, file_path, sid, sname, skind, s, e, lang, content) for cid, sid, sname, skind, s, e, content in out]


def index_items(repo_id: str, items: list[tuple[str, bytes]], skipped: list[dict]) -> None:
    try:
        _update(repo_id, status="indexing", stage="Reading files", progress=0.05, files_total=len(items))
        files, langs = [], {}
        for path, data in items:
            text = _decode(data)
            if text is None:
                skipped.append({"path": path, "reason": "binary or non UTF-8"})
                continue
            files.append((path, parser.detect_language(path), text))
        if not files:
            raise IngestError("No supported source files were found in this upload")
        _update(repo_id, stage="Parsing symbols with tree-sitter", progress=0.15, files_total=len(files))
        file_rows, sym_rows, chunk_rows, all_syms = [], [], [], []
        for i, (path, lang, text) in enumerate(files):
            lines = text.split("\n")
            langs[lang] = langs.get(lang, 0) + 1
            symbols, imports, parsed_ok = [], [], False
            if parser.is_parsed(lang):
                try:
                    res = parser.extract(text, lang)
                    symbols, imports, parsed_ok = res["symbols"], res["imports"], True
                except Exception as exc:  # one bad file never fails the whole repo
                    logger.warning("parse failed for %s: %s", path, exc)
            is_test = 1 if re.search(r"(^|/)(tests?|__tests__|spec)(/|$)|(^|/)test_|_test\.|\.test\.|\.spec\.", path) else 0
            for s in symbols:
                s["id"] = str(uuid.uuid4())
                s["file_path"] = path
                s["is_test"] = 1 if (is_test or s["name"].lower().startswith("test")) else 0
                all_syms.append(s)
                sym_rows.append((s["id"], repo_id, path, s["name"], s["kind"], lang, s["start_line"], s["end_line"],
                                 s["params"], s["returns"], s["parent"], s["docstring"], s["signature"],
                                 json.dumps(s["calls"]), s["is_test"]))
            chunk_rows += [(c[0], repo_id, *c[1:]) for c in _chunks_for(path, lang, lines, symbols)]
            file_rows.append((str(uuid.uuid4()), repo_id, path, lang, len(text.encode()), len(lines), text,
                              json.dumps(imports), 1 if parsed_ok else 0))
            if i % 25 == 0:
                _update(repo_id, progress=0.15 + 0.5 * (i + 1) / len(files), files_indexed=i + 1)
        _update(repo_id, stage="Linking call graph", progress=0.7, files_indexed=len(files))
        by_name: dict[str, list[dict]] = {}
        for s in all_syms:
            by_name.setdefault(s["name"], []).append(s)
        edge_rows = []
        for s in all_syms:
            if s["parent"] and s["kind"] == "method":
                parents = [p for p in by_name.get(s["parent"], []) if p["file_path"] == s["file_path"]]
                if parents:
                    edge_rows.append((repo_id, parents[0]["id"], s["id"], "contains"))
            for name in s["calls"]:
                cands = by_name.get(name, [])
                same = [c for c in cands if c["file_path"] == s["file_path"]]
                targets = same or (cands if len(cands) <= 3 else [])
                for t in targets[:3]:
                    edge_rows.append((repo_id, s["id"], t["id"], "calls"))
        _update(repo_id, stage="Building hybrid search index", progress=0.82)
        executemany("INSERT INTO files (id, repo_id, path, language, size, line_count, content, imports, parsed) VALUES (?,?,?,?,?,?,?,?,?)", file_rows)
        executemany("INSERT INTO symbols (id, repo_id, file_path, name, kind, language, start_line, end_line, params, returns, parent, docstring, signature, calls, is_test) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", sym_rows)
        executemany("INSERT INTO edges (repo_id, source_id, target_id, kind) VALUES (?,?,?,?)", edge_rows)
        executemany("INSERT INTO chunks (id, repo_id, file_path, symbol_id, symbol_name, symbol_kind, start_line, end_line, language, content) VALUES (?,?,?,?,?,?,?,?,?,?)", chunk_rows)
        drop_index(repo_id)
        get_index(repo_id)
        _update(repo_id, status="ready", stage="Ready", progress=1.0, files_indexed=len(files),
                files_skipped=len(skipped), skipped=json.dumps(skipped[:80]), languages=json.dumps(langs),
                symbol_count=len(sym_rows), chunk_count=len(chunk_rows))
    except IngestError as exc:
        _update(repo_id, status="failed", stage="Failed", error=str(exc), files_skipped=len(skipped), skipped=json.dumps(skipped[:80]))
    except Exception as exc:
        logger.exception("indexing failed")
        _update(repo_id, status="failed", stage="Failed", error=f"Indexing error: {exc}")


def create_repo(user_id: str, name: str, source: str, source_url: str | None = None, is_sample: bool = False) -> str:
    rid = str(uuid.uuid4())
    execute(
        "INSERT INTO repos (id, user_id, name, source, source_url, status, stage, progress, is_sample, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (rid, user_id, name, source, source_url, "queued", "Queued", 0, 1 if is_sample else 0, now_iso()),
    )
    return rid


def start_items(repo_id: str, items, skipped) -> None:
    threading.Thread(target=index_items, args=(repo_id, items, skipped), daemon=True).start()


def _clone_and_index(repo_id: str, url: str) -> None:
    dest = REPOS_DIR / repo_id
    try:
        _update(repo_id, status="indexing", stage="Cloning from GitHub", progress=0.02)
        REPOS_DIR.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        r = subprocess.run(["git", "clone", "--depth", "200", "--single-branch", "--no-tags", url, str(dest)],
                           capture_output=True, text=True, timeout=180, env=env)
        if r.returncode != 0:
            raise IngestError("Could not clone repository (is it public and the URL correct?) " + r.stderr[-200:])
        size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file() and not f.is_symlink())
        if size > 400 * 1024 * 1024:
            raise IngestError("Repository is larger than the 400 MB clone limit")
        items, skipped = read_dir(dest)
        _update(repo_id, has_git=1, git_path=str(dest))
        index_items(repo_id, items, skipped)
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest, ignore_errors=True)
        _update(repo_id, status="failed", stage="Failed", error="Cloning timed out (repository too large?)")
    except IngestError as exc:
        shutil.rmtree(dest, ignore_errors=True)
        _update(repo_id, status="failed", stage="Failed", error=str(exc), has_git=0, git_path=None)


def start_clone(repo_id: str, url: str) -> None:
    threading.Thread(target=_clone_and_index, args=(repo_id, url), daemon=True).start()


def delete_repo_data(repo_id: str, git_path: str | None) -> None:
    for table in ("files", "symbols", "edges", "chunks"):
        execute(f"DELETE FROM {table} WHERE repo_id = ?", (repo_id,))
    execute("DELETE FROM repos WHERE id = ?", (repo_id,))
    drop_index(repo_id)
    if git_path and Path(git_path).resolve().is_relative_to(REPOS_DIR.resolve()):
        shutil.rmtree(git_path, ignore_errors=True)


def git_history(git_path: str, file_path: str, start: int, end: int) -> list[dict]:
    r = subprocess.run(
        ["git", "-C", git_path, "log", f"-L{start},{end}:{file_path}", "--no-color", "-n", "12",
         "--date=iso", "--format=@@COMMIT@@%H|%an|%ad|%s"],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise IngestError(r.stderr.strip()[:300] or "git log failed")
    commits = []
    for block in r.stdout.split("@@COMMIT@@")[1:]:
        head, _, body = block.partition("\n")
        h, author, date, msg = (head.split("|", 3) + ["", "", "", ""])[:4]
        lines, added, removed, in_hunk = [], 0, 0, False
        for ln in body.split("\n"):
            if ln.startswith("@@"):
                in_hunk = True
                lines.append({"type": "hunk", "text": ln})
            elif not in_hunk or ln.startswith(("diff --git", "--- ", "+++ ")):
                continue
            elif ln.startswith("+"):
                added += 1
                lines.append({"type": "add", "text": ln[1:]})
            elif ln.startswith("-"):
                removed += 1
                lines.append({"type": "del", "text": ln[1:]})
            else:
                lines.append({"type": "ctx", "text": ln[1:] if ln.startswith(" ") else ln})
        while lines and lines[-1]["type"] == "ctx" and not lines[-1]["text"].strip():
            lines.pop()
        commits.append({"hash": h, "short": h[:8], "author": author, "date": date, "message": msg,
                        "added": added, "removed": removed, "lines": lines[:400]})
    return commits

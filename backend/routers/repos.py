import re
from pathlib import Path, PurePosixPath
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from lib import indexer
from lib.auth import current_user
from lib.parser import build_flow
from lib.repo_access import (code_slice, hits_to_evidence, ready_repo, repo_or_404, repo_out, summaries,
                             symbol_detail, symbol_row)
from lib.retrieval import evidence_quality, get_index
from lib.sqldb import jload, query, query_one
from models.schemas import (Confidence, FileEntry, FileOut, FlowOut, GithubIn, GraphEdge, GraphOut, HistoryOut,
                            ImpactIn, ImpactOut, RepoOut, SearchOut, SymbolDetail, SymbolSummary, TestRef)

router = APIRouter()
SAMPLE_DIR = Path(__file__).parent.parent / "sample_repo"
GITHUB_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(\.git)?/?$")


@router.get("/repos", response_model=list[RepoOut])
def list_repos(user: dict = Depends(current_user)):
    return [repo_out(r) for r in query("SELECT * FROM repos WHERE user_id = ? ORDER BY created_at DESC", (user["id"],))]


@router.get("/repos/{repo_id}", response_model=RepoOut)
def get_repo(repo_id: str, user: dict = Depends(current_user)):
    return repo_out(repo_or_404(repo_id, user))


@router.delete("/repos/{repo_id}")
def delete_repo(repo_id: str, user: dict = Depends(current_user)):
    repo = repo_or_404(repo_id, user)
    indexer.delete_repo_data(repo_id, repo["git_path"])
    return {"ok": True}


@router.post("/repos/upload", response_model=RepoOut)
async def upload(files: list[UploadFile] = File(...), name: Optional[str] = Form(None), user: dict = Depends(current_user)):
    zips = [f for f in files if (f.filename or "").lower().endswith(".zip")]
    if zips and len(files) > 1:
        raise HTTPException(status_code=422, detail="Upload a single ZIP archive, or source files - not both")
    if zips:
        data = await zips[0].read()
        try:
            root, items, skipped = indexer.read_zip(data)
        except indexer.IngestError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        repo_name = name or root or Path(zips[0].filename or "repository.zip").stem
        rid = indexer.create_repo(user["id"], repo_name, "zip")
    else:
        if len(files) > indexer.MAX_FILES:
            raise HTTPException(status_code=422, detail=f"Too many files (max {indexer.MAX_FILES})")
        items, skipped = [], []
        for f in files:
            raw = (f.filename or "file").replace("\\", "/")
            parts = [p for p in PurePosixPath(raw).parts if p not in ("..", "/", ".")]
            rel = "/".join(parts) or "file"
            data = await f.read(indexer.MAX_FILE_BYTES + 1)
            reason = indexer._skip_reason(rel, len(data))
            if reason:
                skipped.append({"path": rel, "reason": reason})
                continue
            items.append((rel, data))
        if not items:
            raise HTTPException(status_code=422, detail="None of the uploaded files are supported source files")
        first = items[0][0].split("/")[0] if "/" in items[0][0] else None
        repo_name = name or first or (items[0][0] if len(items) == 1 else f"{len(items)} uploaded files")
        rid = indexer.create_repo(user["id"], repo_name, "files")
    indexer.start_items(rid, items, skipped)
    return repo_out(repo_or_404(rid, user))


@router.post("/repos/github", response_model=RepoOut)
def import_github(body: GithubIn, user: dict = Depends(current_user)):
    url = body.url.strip()
    if not GITHUB_RE.match(url):
        raise HTTPException(status_code=422, detail="Enter a public GitHub URL like https://github.com/owner/repo")
    name = url.rstrip("/").removesuffix(".git").split("/")[-1]
    rid = indexer.create_repo(user["id"], name, "github", source_url=url)
    indexer.start_clone(rid, url)
    return repo_out(repo_or_404(rid, user))


@router.post("/repos/sample", response_model=RepoOut)
def load_sample(user: dict = Depends(current_user)):
    items, skipped = indexer.read_dir(SAMPLE_DIR)
    rid = indexer.create_repo(user["id"], "Sample project: flask-auth-demo", "sample", is_sample=True)
    indexer.start_items(rid, items, skipped)
    return repo_out(repo_or_404(rid, user))


@router.get("/repos/{repo_id}/files", response_model=list[FileEntry])
def list_files(repo_id: str, user: dict = Depends(current_user)):
    repo_or_404(repo_id, user)
    rows = query("SELECT path, language, line_count, size, parsed FROM files WHERE repo_id = ? ORDER BY path", (repo_id,))
    return [FileEntry(**{**r, "parsed": bool(r["parsed"])}) for r in rows]


@router.get("/repos/{repo_id}/file", response_model=FileOut)
def get_file(repo_id: str, path: str, user: dict = Depends(current_user)):
    repo_or_404(repo_id, user)
    f = query_one("SELECT * FROM files WHERE repo_id = ? AND path = ?", (repo_id, path))
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    syms = query("SELECT * FROM symbols WHERE repo_id = ? AND file_path = ? ORDER BY start_line", (repo_id, path))
    return FileOut(path=f["path"], language=f["language"], content=f["content"], line_count=f["line_count"],
                   parsed=bool(f["parsed"]), imports=jload(f["imports"], []), description=f["description"],
                   symbols=summaries(repo_id, syms))


@router.get("/repos/{repo_id}/symbols", response_model=list[SymbolSummary])
def list_symbols(repo_id: str, q: str = "", user: dict = Depends(current_user)):
    repo_or_404(repo_id, user)
    rows = query("SELECT * FROM symbols WHERE repo_id = ? AND name LIKE ? ORDER BY is_test, name LIMIT 300", (repo_id, f"%{q}%"))
    return summaries(repo_id, rows)


@router.get("/repos/{repo_id}/symbols/{symbol_id}", response_model=SymbolDetail)
def get_symbol(repo_id: str, symbol_id: str, user: dict = Depends(current_user)):
    repo_or_404(repo_id, user)
    return symbol_detail(repo_id, symbol_id)


@router.get("/repos/{repo_id}/search", response_model=SearchOut)
def search(repo_id: str, q: str, user: dict = Depends(current_user)):
    ready_repo(repo_id, user)
    hits = get_index(repo_id).search(q, k=8)
    return SearchOut(hits=hits_to_evidence(hits), confidence=Confidence(**evidence_quality(hits)))


def _edges_among(repo_id: str, ids: set[str]) -> list[GraphEdge]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = query(f"SELECT source_id, target_id, kind FROM edges WHERE repo_id=? AND source_id IN ({marks}) AND target_id IN ({marks})", (repo_id, *ids, *ids))
    seen, out = set(), []
    for r in rows:
        key = (r["source_id"], r["target_id"], r["kind"])
        if key not in seen:
            seen.add(key)
            out.append(GraphEdge(id=f"{r['source_id']}>{r['target_id']}>{r['kind']}", source=r["source_id"], target=r["target_id"], kind=r["kind"]))
    return out


@router.get("/repos/{repo_id}/graph", response_model=GraphOut)
def graph(repo_id: str, symbol_id: Optional[str] = None, depth: int = 2, user: dict = Depends(current_user)):
    repo_or_404(repo_id, user)
    depth = max(1, min(depth, 4))
    if symbol_id:
        symbol_row(repo_id, symbol_id)
        ids = {symbol_id}
        for col, other in (("source_id", "target_id"), ("target_id", "source_id")):
            frontier = {symbol_id}
            for _ in range(depth):
                if not frontier or len(ids) > 60:
                    break
                marks = ",".join("?" * len(frontier))
                rows = query(f"SELECT {other} o FROM edges WHERE repo_id=? AND kind='calls' AND {col} IN ({marks})", (repo_id, *frontier))
                frontier = {r["o"] for r in rows} - ids
                ids |= frontier
        parent = query("SELECT source_id FROM edges WHERE repo_id=? AND kind='contains' AND target_id=?", (repo_id, symbol_id))
        ids |= {p["source_id"] for p in parent}
    else:
        rows = query("SELECT id, (SELECT COUNT(*) FROM edges e WHERE e.repo_id=s.repo_id AND (e.source_id=s.id OR e.target_id=s.id)) deg FROM symbols s WHERE repo_id=? ORDER BY deg DESC LIMIT 45", (repo_id,))
        ids = {r["id"] for r in rows if r["deg"] > 0} or {r["id"] for r in rows[:20]}
    if not ids:
        return GraphOut(root_id=symbol_id, nodes=[], edges=[])
    marks = ",".join("?" * len(ids))
    nodes = query(f"SELECT * FROM symbols WHERE repo_id=? AND id IN ({marks})", (repo_id, *ids))
    return GraphOut(root_id=symbol_id, nodes=summaries(repo_id, nodes), edges=_edges_among(repo_id, ids))


@router.get("/repos/{repo_id}/symbols/{symbol_id}/flow", response_model=FlowOut)
def flow(repo_id: str, symbol_id: str, user: dict = Depends(current_user)):
    repo_or_404(repo_id, user)
    s = symbol_row(repo_id, symbol_id)
    if s["kind"] not in ("function", "method"):
        raise HTTPException(status_code=422, detail="Execution flowcharts are available for functions and methods only")
    content = query_one("SELECT content FROM files WHERE repo_id=? AND path=?", (repo_id, s["file_path"]))["content"]
    res = build_flow(content, s["language"], s["start_line"], s["name"])
    return FlowOut(symbol=summaries(repo_id, [s])[0], **res)


@router.get("/repos/{repo_id}/symbols/{symbol_id}/history", response_model=HistoryOut)
def history(repo_id: str, symbol_id: str, user: dict = Depends(current_user)):
    repo = repo_or_404(repo_id, user)
    s = symbol_row(repo_id, symbol_id)
    if not repo["has_git"] or not repo["git_path"] or not Path(repo["git_path"]).exists():
        return HistoryOut(available=False, reason=(
            "This repository was uploaded without Git history (ZIP downloads and file uploads do not include the .git folder). "
            "Import it with a public GitHub URL to inspect how this function evolved."))
    try:
        commits = indexer.git_history(repo["git_path"], s["file_path"], s["start_line"], s["end_line"])
    except indexer.IngestError as exc:
        return HistoryOut(available=False, reason=f"Git could not trace this function: {exc}")
    if not commits:
        return HistoryOut(available=False, reason="No commits touching these lines were found in the cloned history.")
    return HistoryOut(available=True, commits=commits)


def compute_impact(repo_id: str, removed: list[str]) -> ImpactOut:
    rset = set(removed)
    marks = ",".join("?" * len(rset))
    rows = query(f"SELECT * FROM symbols WHERE repo_id=? AND id IN ({marks})", (repo_id, *rset))
    if not rows:
        raise HTTPException(status_code=404, detail="Symbols not found")
    broken = query(f"SELECT source_id, target_id, kind FROM edges WHERE repo_id=? AND kind='calls' AND (source_id IN ({marks}) OR target_id IN ({marks}))", (repo_id, *rset, *rset))
    direct = {e["source_id"] for e in broken if e["target_id"] in rset} - rset
    transitive, frontier = set(), set(direct)
    for _ in range(4):
        if not frontier:
            break
        fm = ",".join("?" * len(frontier))
        up = {r["source_id"] for r in query(f"SELECT source_id FROM edges WHERE repo_id=? AND kind='calls' AND target_id IN ({fm})", (repo_id, *frontier))}
        frontier = up - rset - direct - transitive
        transitive |= frontier
    callees = {e["target_id"] for e in broken if e["source_id"] in rset} - rset
    orphaned = set()
    for c in callees:
        callers = {r["source_id"] for r in query("SELECT source_id FROM edges WHERE repo_id=? AND kind='calls' AND target_id=?", (repo_id, c))}
        if callers and callers <= rset:
            orphaned.add(c)

    def fetch(ids):
        if not ids:
            return []
        m = ",".join("?" * len(ids))
        return query(f"SELECT * FROM symbols WHERE repo_id=? AND id IN ({m})", (repo_id, *ids))

    d_rows, t_rows, o_rows = fetch(direct), fetch(transitive), fetch(orphaned)
    tests: dict[str, TestRef] = {}
    for r in d_rows + t_rows:
        if r["is_test"]:
            tests[r["id"]] = TestRef(name=r["name"], file_path=r["file_path"], start_line=r["start_line"], end_line=r["end_line"])
    for r in rows:
        for c in query("SELECT * FROM chunks WHERE repo_id=? AND content LIKE ? LIMIT 40", (repo_id, f"%{r['name']}%")):
            sym = query_one("SELECT * FROM symbols WHERE id=?", (c["symbol_id"],)) if c["symbol_id"] else None
            if sym and sym["is_test"] and re.search(rf"\b{re.escape(r['name'])}\b", c["content"]):
                tests[sym["id"]] = TestRef(name=sym["name"], file_path=sym["file_path"], start_line=sym["start_line"], end_line=sym["end_line"])
    files = sorted({r["file_path"] for r in d_rows + t_rows})
    names = ", ".join(f"{r['name']}()" for r in rows)
    cons = []
    if d_rows:
        cons.append(f"{len(d_rows)} function(s) call {names} directly and would fail (NameError / unresolved reference) or need rewriting: " + ", ".join(r["name"] for r in d_rows[:8]) + ".")
    else:
        cons.append(f"No static callers of {names} were found - it may be an entry point, unused, or called dynamically.")
    if t_rows:
        cons.append(f"{len(t_rows)} more function(s) depend on it indirectly through the call chain and could break at runtime.")
    if o_rows:
        cons.append(f"{len(o_rows)} helper(s) would become unreachable (only called by the removed code): " + ", ".join(r["name"] for r in o_rows[:8]) + ".")
    if tests:
        cons.append(f"{len(tests)} test(s) reference this code and would likely fail.")
    if files:
        cons.append(f"Affected files: {', '.join(files[:6])}{'...' if len(files) > 6 else ''}.")
    return ImpactOut(
        removed=summaries(repo_id, rows), direct_dependents=summaries(repo_id, d_rows),
        transitive_dependents=summaries(repo_id, t_rows), orphaned=summaries(repo_id, o_rows), affected_files=files,
        related_tests=list(tests.values()),
        broken_edges=[GraphEdge(id=f"{e['source_id']}>{e['target_id']}>calls", source=e["source_id"], target=e["target_id"], kind="calls") for e in broken],
        consequences=cons,
        caveat="Simulation only - your repository is never modified. Based on static call references; dynamic dispatch, reflection, callbacks and runtime behaviour may not be fully captured.",
    )


@router.post("/repos/{repo_id}/impact", response_model=ImpactOut)
def impact(repo_id: str, body: ImpactIn, user: dict = Depends(current_user)):
    repo_or_404(repo_id, user)
    return compute_impact(repo_id, body.removed)

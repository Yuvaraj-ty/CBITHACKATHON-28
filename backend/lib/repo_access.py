"""Shared repo/symbol lookups used by several routers."""

from fastapi import HTTPException

from lib.retrieval import reason_for
from lib.sqldb import jload, query, query_one
from models.schemas import Evidence, RepoOut, SymbolDetail, SymbolSummary


def repo_or_404(repo_id: str, user: dict) -> dict:
    repo = query_one("SELECT * FROM repos WHERE id = ? AND user_id = ?", (repo_id, user["id"]))
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


def ready_repo(repo_id: str, user: dict) -> dict:
    repo = repo_or_404(repo_id, user)
    if repo["status"] != "ready":
        raise HTTPException(status_code=409, detail=f"Repository is not ready (status: {repo['status']})")
    return repo


def repo_out(r: dict) -> RepoOut:
    return RepoOut(
        **{k: r[k] for k in ("id", "name", "source", "source_url", "status", "stage", "progress", "files_total",
                             "files_indexed", "files_skipped", "symbol_count", "chunk_count", "error", "created_at")},
        skipped=jload(r["skipped"], []), languages=jload(r["languages"], {}),
        has_git=bool(r["has_git"]), is_sample=bool(r["is_sample"]),
    )


def summaries(repo_id: str, rows: list[dict]) -> list[SymbolSummary]:
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids))
    out_c = {r["source_id"]: r["n"] for r in query(f"SELECT source_id, COUNT(*) n FROM edges WHERE repo_id=? AND kind='calls' AND source_id IN ({marks}) GROUP BY source_id", (repo_id, *ids))}
    in_c = {r["target_id"]: r["n"] for r in query(f"SELECT target_id, COUNT(*) n FROM edges WHERE repo_id=? AND kind='calls' AND target_id IN ({marks}) GROUP BY target_id", (repo_id, *ids))}
    return [
        SymbolSummary(id=r["id"], name=r["name"], kind=r["kind"], file_path=r["file_path"], start_line=r["start_line"],
                      end_line=r["end_line"], language=r["language"], parent=r["parent"], is_test=bool(r["is_test"]),
                      params=r["params"] or "", callers_count=in_c.get(r["id"], 0), callees_count=out_c.get(r["id"], 0))
        for r in rows
    ]


def symbol_row(repo_id: str, symbol_id: str) -> dict:
    s = query_one("SELECT * FROM symbols WHERE repo_id = ? AND id = ?", (repo_id, symbol_id))
    if not s:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return s


def file_lines(repo_id: str, path: str) -> list[str]:
    f = query_one("SELECT content FROM files WHERE repo_id = ? AND path = ?", (repo_id, path))
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return f["content"].split("\n")


def code_slice(repo_id: str, path: str, start: int, end: int) -> str:
    return "\n".join(file_lines(repo_id, path)[start - 1 : end])


def numbered(code: str, start: int) -> str:
    return "\n".join(f"{start + i:>4}| {ln}" for i, ln in enumerate(code.split("\n")))


def hits_to_evidence(hits: list[dict]) -> list[Evidence]:
    return [
        Evidence(id=f"E{i + 1}", file_path=h["file_path"], start_line=h["start_line"], end_line=h["end_line"],
                 language=h["language"], symbol_id=h["symbol_id"], symbol_name=h["symbol_name"],
                 symbol_kind=h["symbol_kind"], code=h["content"], reason=reason_for(h), score=h["score"],
                 lexical=h["lexical"], semantic=h["semantic"], symbol_match=h["symbol_match"],
                 matched_terms=h["matched_terms"])
        for i, h in enumerate(hits)
    ]


def symbol_detail(repo_id: str, symbol_id: str) -> SymbolDetail:
    s = symbol_row(repo_id, symbol_id)
    base = summaries(repo_id, [s])[0]
    callers = query("SELECT s.* FROM edges e JOIN symbols s ON s.id = e.source_id WHERE e.repo_id=? AND e.kind='calls' AND e.target_id=?", (repo_id, symbol_id))
    callees = query("SELECT s.* FROM edges e JOIN symbols s ON s.id = e.target_id WHERE e.repo_id=? AND e.kind='calls' AND e.source_id=?", (repo_id, symbol_id))
    related = []
    if s["parent"]:
        related = query("SELECT * FROM symbols WHERE repo_id=? AND file_path=? AND (name=? OR parent=?) AND id != ? LIMIT 20", (repo_id, s["file_path"], s["parent"], s["parent"], symbol_id))
    elif s["kind"] in ("class", "interface", "struct"):
        related = query("SELECT * FROM symbols WHERE repo_id=? AND file_path=? AND parent=? LIMIT 20", (repo_id, s["file_path"], s["name"]))
    resolved = {c["name"] for c in callees}
    external = [c for c in jload(s["calls"], []) if c not in resolved][:15]
    return SymbolDetail(
        **base.model_dump(), signature=s["signature"] or "", returns=s["returns"] or "", docstring=s["docstring"] or "",
        code=code_slice(repo_id, s["file_path"], s["start_line"], s["end_line"]),
        callers=summaries(repo_id, callers), callees=summaries(repo_id, callees), related=summaries(repo_id, related),
        external_calls=external,
    )

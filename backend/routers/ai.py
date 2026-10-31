import json
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import current_user
from lib.indexer import IngestError, git_history
from lib.llm import LLMError, complete, complete_json, mode_style
from lib.repo_access import (file_lines, hits_to_evidence, numbered, ready_repo, repo_or_404, summaries,
                             symbol_detail, symbol_row)
from lib.retrieval import evidence_quality, get_index
from lib.sqldb import execute, jload, now_iso, query, query_one
from models.schemas import (Alternative, AlternativesIn, AlternativesOut, ChatIn, ChatOut, CompareIn, CompareOut,
                            CompareRow, Confidence, ConversationOut, DescribeIn, DescribeOut, Evidence,
                            HistoryExplainOut, ImpactExplainOut, ImpactIn, MessageOut, NamedNote, Selection,
                            SymbolAiIn, WalkStep, WalkthroughOut)
from routers.repos import compute_impact

router = APIRouter()

RULES = (
    "STRICT RULES: Never invent file paths, line numbers, function names, dependencies or Git commits. "
    "Only refer to repository code that appears in the EVIDENCE block and cite it inline as [E1], [E2]. "
    "If the evidence does not contain enough information to answer, say so explicitly instead of guessing."
)
REPO_HINT = re.compile(
    r"\b(this|the|our|my)\s+(repo|repository|codebase|project|code|app|application|system)\b|\bwhere\s+(is|are|do|does)\b"
    r"|\bwhich\s+(file|files|function|functions|class|classes|module)\b|\bimplemented\b|\bhandles?\b|\bin (this|the) code\b",
    re.I,
)


def _llm_http(exc: LLMError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _msg_out(r: dict) -> MessageOut:
    return MessageOut(id=r["id"], role=r["role"], content=r["content"], mode=r["mode"], scope=r["scope"],
                      evidence=jload(r["evidence"], []), confidence=jload(r["confidence"], None),
                      selection=jload(r["selection"], None), created_at=r["created_at"])


def _save_msg(conv_id: str, role: str, content: str, mode: str, scope: Optional[str], evidence: list[Evidence],
              confidence: Optional[Confidence], selection: Optional[Selection]) -> MessageOut:
    mid = str(uuid.uuid4())
    row = {"id": mid, "role": role, "content": content, "mode": mode, "scope": scope,
           "evidence": json.dumps([e.model_dump() for e in evidence]),
           "confidence": json.dumps(confidence.model_dump()) if confidence else None,
           "selection": json.dumps(selection.model_dump()) if selection else None, "created_at": now_iso()}
    execute("INSERT INTO messages (id, conversation_id, role, content, mode, scope, evidence, confidence, selection, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (mid, conv_id, role, content, mode, scope, row["evidence"], row["confidence"], row["selection"], row["created_at"]))
    return _msg_out(row)


def _evidence_block(evidence: list[Evidence], marks: Optional[tuple[int, int]] = None) -> str:
    out = []
    for e in evidence:
        lines = []
        for i, ln in enumerate(e.code.split("\n")):
            no = e.start_line + i
            flag = ">>" if marks and marks[0] <= no <= marks[1] else "  "
            lines.append(f"{flag}{no:>4}| {ln}")
        sym = f" - {e.symbol_kind} `{e.symbol_name}`" if e.symbol_name else ""
        out.append(f"[{e.id}] {e.file_path} lines {e.start_line}-{e.end_line}{sym}\n```{e.language or ''}\n" + "\n".join(lines) + "\n```")
    return "\n\n".join(out)


def _history_text(conv_id: str) -> str:
    rows = query("SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT 6", (conv_id,))
    if not rows:
        return ""
    return "CONVERSATION SO FAR:\n" + "\n".join(f"{r['role'].title()}: {r['content'][:700]}" for r in reversed(rows)) + "\n\n"


def _split_notes(text: str) -> tuple[str, dict]:
    if "---NOTES---" not in text:
        return text.strip(), {}
    answer, _, notes = text.partition("---NOTES---")
    try:
        m = re.search(r"\{.*\}", notes, re.S)
        return answer.strip(), json.loads(m.group(0)) if m else {}
    except (ValueError, AttributeError):
        return answer.strip(), {}


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, user: dict = Depends(current_user)):
    repo = repo_or_404(body.repo_id, user) if body.repo_id else None
    if repo and repo["status"] != "ready":
        raise HTTPException(status_code=409, detail="Repository is still indexing - try again when it is ready")
    conv_id = body.conversation_id
    if conv_id and not query_one("SELECT id FROM conversations WHERE id=? AND user_id=?", (conv_id, user["id"])):
        raise HTTPException(status_code=404, detail="Conversation not found")
    if not conv_id:
        conv_id = str(uuid.uuid4())
        execute("INSERT INTO conversations (id, user_id, repo_id, title, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (conv_id, user["id"], body.repo_id, body.message[:70], now_iso(), now_iso()))
    history = _history_text(conv_id)
    evidence: list[Evidence] = []
    confidence: Optional[Confidence] = None
    marks = None
    if repo and body.selection:
        scope = "selection"
        sel = body.selection
        lines = file_lines(repo["id"], sel.file_path)
        s, e = max(1, min(sel.start_line, sel.end_line)), min(len(lines), max(sel.start_line, sel.end_line))
        cs, ce = max(1, s - 8), min(len(lines), e + 8)
        lang = (query_one("SELECT language FROM files WHERE repo_id=? AND path=?", (repo["id"], sel.file_path)) or {}).get("language")
        evidence.append(Evidence(id="E1", file_path=sel.file_path, start_line=cs, end_line=ce, language=lang,
                                 code="\n".join(lines[cs - 1 : ce]), reason=f"You selected lines {s}-{e}; 8 surrounding lines are included as context.",
                                 score=1, symbol_match=True))
        sel_text = "\n".join(lines[s - 1 : e])
        called = set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", sel_text))
        for d in query("SELECT * FROM symbols WHERE repo_id=? AND kind IN ('function','method') ORDER BY is_test", (repo["id"],)):
            if len(evidence) >= 3:
                break
            if d["name"] in called and not (d["file_path"] == sel.file_path and d["start_line"] <= s <= d["end_line"]):
                code = "\n".join(file_lines(repo["id"], d["file_path"])[d["start_line"] - 1 : min(d["end_line"], d["start_line"] + 50)])
                evidence.append(Evidence(id=f"E{len(evidence) + 1}", file_path=d["file_path"], start_line=d["start_line"],
                                         end_line=min(d["end_line"], d["start_line"] + 50), language=d["language"], symbol_id=d["id"],
                                         symbol_name=d["name"], symbol_kind=d["kind"], code=code,
                                         reason=f"Definition of `{d['name']}`, which is called inside your selection."))
        marks = (s, e)
        confidence = Confidence(score=1, level="selected", insufficient=False, factors={},
                                note="Answer is scoped to the code you selected - the wider repository was not searched.")
        instruction = "Focus on the SELECTED lines (prefixed with >> in E1). Other lines are context only."
    elif repo and body.file_path:
        scope = "file"
        lines = file_lines(repo["id"], body.file_path)
        end = min(len(lines), 300)
        lang = (query_one("SELECT language FROM files WHERE repo_id=? AND path=?", (repo["id"], body.file_path)) or {}).get("language")
        evidence.append(Evidence(id="E1", file_path=body.file_path, start_line=1, end_line=end, language=lang,
                                 code="\n".join(lines[:end]), reason="The file you asked about.", score=1))
        confidence = Confidence(score=1, level="file", insufficient=False,
                                note="Answer is scoped to the selected file." + (" Only the first 300 lines were provided." if len(lines) > 300 else ""))
        instruction = "Answer about this file."
    else:
        hits = get_index(repo["id"]).search(body.message, k=6) if repo and body.scope != "general" else []
        quality = evidence_quality(hits)
        if not repo or body.scope == "general":
            scope = "general"
        elif body.scope == "repo" or REPO_HINT.search(body.message) or any(h["symbol_match"] for h in hits[:3]) or quality["score"] >= 0.6:
            scope = "repo"
        else:
            scope = "general"
        if scope == "repo":
            evidence = hits_to_evidence(hits)
            confidence = Confidence(**quality)
        instruction = ""
        if scope == "repo" and quality["insufficient"]:
            instruction = ("EVIDENCE IS INSUFFICIENT: the retrieved snippets barely match. Start by telling the user you could not find "
                           "enough evidence in the repository, then suggest specific terms or files to look for. Do not invent an answer.")
    if scope == "general":
        system = f"You are CodeAtlas, a programming tutor. {mode_style(body.mode)}\nThis is a GENERAL programming question. You have NOT searched any repository - never claim or imply that you did. Use Markdown with fenced code blocks."
        prompt = f"{history}QUESTION: {body.message}"
    else:
        system = f"You are CodeAtlas, a code-explanation assistant analysing the repository '{repo['name']}'. {mode_style(body.mode)}\n{RULES}"
        prompt = (f"{history}EVIDENCE (retrieved from the repository; the only code you may cite):\n{_evidence_block(evidence, marks)}\n\n"
                  f"{instruction}\nQUESTION: {body.message}\n\nWrite the answer in Markdown and cite evidence inline like [E1]. "
                  "Then on a new line write exactly ---NOTES--- followed by a JSON object mapping each evidence id you relied on to ONE sentence "
                  'explaining why that code is relevant, e.g. {"E1": "..."}.')
    try:
        text = await complete(system, prompt, max_tokens=2200)
    except LLMError as exc:
        raise _llm_http(exc)
    answer, notes = _split_notes(text)
    for e in evidence:
        e.ai_note = str(notes.get(e.id, ""))[:400]
    user_msg = _save_msg(conv_id, "user", body.message, body.mode, scope, [], None, body.selection)
    reply = _save_msg(conv_id, "assistant", answer or "(empty response)", body.mode, scope, evidence, confidence, body.selection)
    execute("UPDATE conversations SET updated_at=? WHERE id=?", (now_iso(), conv_id))
    return ChatOut(conversation_id=conv_id, user_message=user_msg, reply=reply)


@router.get("/conversations", response_model=list[ConversationOut])
def conversations(repo_id: Optional[str] = None, user: dict = Depends(current_user)):
    sql = "SELECT * FROM conversations WHERE user_id=?" + (" AND repo_id=?" if repo_id else "") + " ORDER BY updated_at DESC LIMIT 30"
    rows = query(sql, (user["id"], repo_id) if repo_id else (user["id"],))
    return [ConversationOut(id=r["id"], title=r["title"] or "Conversation", repo_id=r["repo_id"], updated_at=r["updated_at"]) for r in rows]


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def conversation_messages(conv_id: str, user: dict = Depends(current_user)):
    if not query_one("SELECT id FROM conversations WHERE id=? AND user_id=?", (conv_id, user["id"])):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [_msg_out(r) for r in query("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (conv_id,))]


@router.post("/ai/describe-file", response_model=DescribeOut)
async def describe_file(body: DescribeIn, user: dict = Depends(current_user)):
    ready_repo(body.repo_id, user)
    f = query_one("SELECT * FROM files WHERE repo_id=? AND path=?", (body.repo_id, body.path))
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if f["description"] and not body.refresh:
        return DescribeOut(description=f["description"])
    syms = query("SELECT name, kind, start_line, end_line FROM symbols WHERE repo_id=? AND file_path=? ORDER BY start_line LIMIT 60", (body.repo_id, body.path))
    other = [r["path"] for r in query("SELECT path FROM files WHERE repo_id=? LIMIT 200", (body.repo_id,))]
    code = "\n".join(f["content"].split("\n")[:250])
    prompt = (f"FILE: {body.path} ({f['language']}, {f['line_count']} lines)\nPARSED SYMBOLS: "
              + (", ".join(f"{s['kind']} {s['name']} (L{s['start_line']}-{s['end_line']})" for s in syms) or "none")
              + f"\nIMPORTS: {'; '.join(jload(f['imports'], [])[:20]) or 'none'}\nOTHER FILES IN REPO: {', '.join(other[:80])}\n\nCODE:\n```\n{numbered(code, 1)}\n```\n\n"
              "Write a brief description (max 140 words) in Markdown with these bold labels: **What it does**, **Main functions & classes**, "
              "**Role in the repository**, **Dependencies & related files**. Only mention symbols and files listed above.")
    try:
        text = await complete(f"You describe source files accurately. {mode_style(body.mode)}\n{RULES}", prompt, max_tokens=600)
    except LLMError as exc:
        raise _llm_http(exc)
    execute("UPDATE files SET description=? WHERE repo_id=? AND path=?", (text.strip(), body.repo_id, body.path))
    return DescribeOut(description=text.strip())


@router.post("/ai/walkthrough", response_model=WalkthroughOut)
async def walkthrough(body: SymbolAiIn, user: dict = Depends(current_user)):
    ready_repo(body.repo_id, user)
    d = symbol_detail(body.repo_id, body.symbol_id)
    prompt = (f"FUNCTION `{d.name}` in {d.file_path} (lines {d.start_line}-{d.end_line}). Calls: {', '.join(c.name for c in d.callees) or 'none in repo'}.\n"
              f"```{d.language}\n{numbered(d.code, d.start_line)}\n```\n\nProduce a step-by-step walkthrough as JSON: "
              '{"purpose": str, "parameters": [{"name": str, "description": str}], "variables": [{"name": str, "description": str}], '
              '"returns": str, "steps": [{"title": str, "kind": "setup|condition|loop|call|assignment|return|error|other", '
              f'"explanation": str, "start_line": int, "end_line": int}}]}}. Use 3-10 steps in execution order. Every start_line/end_line MUST be '
              f"real line numbers between {d.start_line} and {d.end_line} taken from the numbered code.")
    try:
        data = await complete_json(f"You explain code execution precisely. {mode_style(body.mode)}", prompt, max_tokens=2500)
    except LLMError as exc:
        raise _llm_http(exc)
    steps = []
    for st in data.get("steps", []):
        try:
            s = max(d.start_line, min(d.end_line, int(st.get("start_line", d.start_line))))
            e = max(s, min(d.end_line, int(st.get("end_line", s))))
        except (TypeError, ValueError):
            continue
        steps.append(WalkStep(title=str(st.get("title", "Step"))[:120], kind=str(st.get("kind", "other")), explanation=str(st.get("explanation", "")), start_line=s, end_line=e))
    if not steps:
        raise HTTPException(status_code=502, detail="The AI could not produce a walkthrough for this function. Try again.")

    def notes(key):
        return [NamedNote(name=str(n.get("name", ""))[:80], description=str(n.get("description", ""))) for n in data.get(key, []) if isinstance(n, dict)]

    return WalkthroughOut(symbol=d, purpose=str(data.get("purpose", "")), parameters=notes("parameters"), variables=notes("variables"),
                          returns=str(data.get("returns", "")), steps=steps)


@router.post("/ai/alternatives", response_model=AlternativesOut)
async def alternatives(body: AlternativesIn, user: dict = Depends(current_user)):
    source = None
    if body.symbol_id and body.repo_id:
        ready_repo(body.repo_id, user)
        d = symbol_detail(body.repo_id, body.symbol_id)
        source = Evidence(id="SRC", file_path=d.file_path, start_line=d.start_line, end_line=d.end_line, language=d.language,
                          symbol_id=d.id, symbol_name=d.name, symbol_kind=d.kind, code=d.code, reason="Original implementation from the repository.")
        subject = f"this function from the repository ({d.file_path} L{d.start_line}-{d.end_line}):\n```{d.language}\n{d.code[:6000]}\n```"
    elif body.concept:
        subject = f"this programming concept or code:\n{body.concept}"
    else:
        raise HTTPException(status_code=422, detail="Provide a symbol or a concept")
    prompt = (f"Generate 2-3 genuinely different alternative implementations of {subject}\n\nReturn JSON: "
              '{"alternatives": [{"title": str, "language": str, "code": str, "differences": str, "pros": [str], "cons": [str], "when_to_use": str}]}. '
              "Keep the same language as the original unless a concept was given.")
    try:
        data = await complete_json(f"You are a senior engineer suggesting alternative implementations. {mode_style(body.mode)}", prompt, max_tokens=3500)
    except LLMError as exc:
        raise _llm_http(exc)
    alts = []
    for a in data.get("alternatives", []):
        if isinstance(a, dict) and a.get("code"):
            alts.append(Alternative(title=str(a.get("title", "Alternative")), language=str(a.get("language", source.language if source else "text")),
                                    code=str(a["code"]), differences=str(a.get("differences", "")), pros=[str(x) for x in a.get("pros", [])],
                                    cons=[str(x) for x in a.get("cons", [])], when_to_use=str(a.get("when_to_use", ""))))
    if not alts:
        raise HTTPException(status_code=502, detail="The AI did not return any alternatives. Try again.")
    return AlternativesOut(source=source, alternatives=alts)


@router.post("/ai/compare", response_model=CompareOut)
async def compare(body: CompareIn, user: dict = Depends(current_user)):
    ready_repo(body.repo_id, user)
    a, b = symbol_detail(body.repo_id, body.a), symbol_detail(body.repo_id, body.b)

    def facts(d, tag):
        return (f"[{tag}] {d.kind} `{d.name}` in {d.file_path} lines {d.start_line}-{d.end_line}\nparams: {d.params or '-'}; returns annotation: {d.returns or '-'}\n"
                f"calls (in repo): {', '.join(c.name for c in d.callees) or 'none'}; called by: {', '.join(c.name for c in d.callers) or 'none'}; "
                f"external calls: {', '.join(d.external_calls) or 'none'}\n```{d.language}\n{numbered(d.code[:5000], d.start_line)}\n```")

    prompt = (f"{facts(a, 'A')}\n\n{facts(b, 'B')}\n\nCompare A and B. Return JSON: "
              '{"rows": [{"aspect": str, "a": str, "b": str}], "similarities": [str], "differences": [str], "summary": str}. '
              "rows MUST cover these aspects in order: Purpose, Inputs & parameters, Outputs, Internal logic, Dependencies, Function calls, Possible use cases. "
              "Reference line numbers only from the numbered code above.")
    try:
        data = await complete_json(f"You compare code components accurately. {mode_style(body.mode)}\n{RULES}", prompt, max_tokens=2500)
    except LLMError as exc:
        raise _llm_http(exc)
    rows = [CompareRow(aspect=str(r.get("aspect", "")), a=str(r.get("a", "")), b=str(r.get("b", ""))) for r in data.get("rows", []) if isinstance(r, dict)]
    return CompareOut(a=a, b=b, rows=rows, similarities=[str(x) for x in data.get("similarities", [])],
                      differences=[str(x) for x in data.get("differences", [])], summary=str(data.get("summary", "")))


@router.post("/ai/history-explain", response_model=HistoryExplainOut)
async def history_explain(body: SymbolAiIn, user: dict = Depends(current_user)):
    repo = ready_repo(body.repo_id, user)
    s = symbol_row(body.repo_id, body.symbol_id)
    if not repo["has_git"] or not repo["git_path"]:
        raise HTTPException(status_code=409, detail="Git history is not available for this repository")
    try:
        commits = git_history(repo["git_path"], s["file_path"], s["start_line"], s["end_line"])
    except IngestError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not commits:
        raise HTTPException(status_code=409, detail="No commits found for this function")
    diffs = "\n\n".join(
        f"COMMIT {c['short']} by {c['author']} on {c['date']}: {c['message']}\n"
        + "\n".join(("+" if ln["type"] == "add" else "-" if ln["type"] == "del" else " ") + ln["text"] for ln in c["lines"][:120] if ln["type"] != "hunk")
        for c in commits[:5]
    )
    try:
        text = await complete(f"You explain how code evolved using ONLY the real git diffs provided. {mode_style(body.mode)}\n{RULES}",
                              f"Function `{s['name']}` in {s['file_path']}. Real git history (newest first):\n{diffs}\n\nExplain in Markdown how this function changed over time and why the changes matter. Refer to commits by their short hash.", max_tokens=1200)
    except LLMError as exc:
        raise _llm_http(exc)
    return HistoryExplainOut(explanation=text.strip())


@router.post("/repos/{repo_id}/impact/explain", response_model=ImpactExplainOut)
async def impact_explain(repo_id: str, body: ImpactIn, mode: str = "student", user: dict = Depends(current_user)):
    ready_repo(repo_id, user)
    imp = compute_impact(repo_id, body.removed)
    prompt = (f"A user is SIMULATING the removal of: {', '.join(f'{r.name} ({r.file_path} L{r.start_line}-{r.end_line})' for r in imp.removed)}.\n"
              f"Static analysis found: direct callers: {', '.join(f'{r.name} ({r.file_path})' for r in imp.direct_dependents) or 'none'}; "
              f"indirect dependents: {', '.join(r.name for r in imp.transitive_dependents) or 'none'}; orphaned helpers: {', '.join(r.name for r in imp.orphaned) or 'none'}; "
              f"related tests: {', '.join(t.name for t in imp.related_tests) or 'none'}.\nExplain the likely consequences in <=150 words of Markdown. "
              "Mention that dynamic calls may not be captured. Do not mention any function not listed.")
    try:
        text = await complete(f"You explain change impact. {mode_style(mode)}\n{RULES}", prompt, max_tokens=600)
    except LLMError as exc:
        raise _llm_http(exc)
    return ImpactExplainOut(explanation=text.strip())

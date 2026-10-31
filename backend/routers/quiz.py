import json
import random
import uuid

from fastapi import APIRouter, Depends, HTTPException

from lib.auth import current_user
from lib.llm import LLMError, complete_json
from lib.repo_access import ready_repo
from lib.retrieval import get_index
from lib.sqldb import execute, jload, now_iso, query, query_one
from models.schemas import AnswerIn, AnswerOut, CodeRef, QuizIn, QuizOut, QuizQuestionPublic, QuizResult, TopicScore

router = APIRouter()
TYPES = ["multiple_choice", "true_false", "predict_output", "identify_function", "code_understanding", "order_steps"]
DIFF = {"easy": "introductory, single concept, friendly wording", "medium": "requires applying concepts and reading short code",
        "hard": "tricky edge cases, multi-step reasoning, subtle behaviour"}


def _repo_context(repo_id: str, focus: str | None) -> list[dict]:
    idx = get_index(repo_id)
    if focus:
        hits = idx.search(focus, k=8)
        if hits:
            return hits
    rows = query(
        "SELECT s.id, (SELECT COUNT(*) FROM edges e WHERE e.repo_id=s.repo_id AND (e.source_id=s.id OR e.target_id=s.id)) deg "
        "FROM symbols s WHERE s.repo_id=? AND s.kind IN ('function','method') AND s.is_test=0 ORDER BY deg DESC LIMIT 24", (repo_id,))
    ids = [r["id"] for r in rows]
    random.shuffle(ids)
    chosen = set(ids[:8])
    picked = [c for c in idx.chunks if c["symbol_id"] in chosen]
    seen, out = set(), []
    for c in picked:
        if c["symbol_id"] not in seen:
            seen.add(c["symbol_id"])
            out.append(c)
    return out or idx.chunks[:8]


def _valid(q: dict, refs: dict) -> dict | None:
    t = q.get("type")
    opts = [str(o) for o in q.get("options", []) if str(o).strip()]
    if t not in TYPES or not q.get("question") or len(opts) < 2:
        return None
    out = {"type": t, "topic": str(q.get("topic") or "General")[:60], "question": str(q["question"]), "code": q.get("code") or None,
           "language": q.get("language") or None, "options": opts[:6], "explanation": str(q.get("explanation", "")),
           "why_others_wrong": str(q.get("why_others_wrong", "")), "evidence": q.get("evidence") if q.get("evidence") in refs else None}
    if t == "order_steps":
        order = q.get("correct_order")
        if not isinstance(order, list) or sorted(int(x) for x in order) != list(range(len(out["options"]))):
            return None
        out["correct_order"] = [int(x) for x in order]
    else:
        try:
            ans = int(q.get("answer"))
        except (TypeError, ValueError):
            return None
        if not 0 <= ans < len(out["options"]):
            return None
        out["answer"] = ans
    return out


def _public(qid: str, row: dict) -> QuizOut:
    qs = jload(row["questions"], [])
    return QuizOut(id=qid, kind=row["kind"], topic=row["topic"], difficulty=row["difficulty"], repo_name=row["repo_name"],
                   questions=[QuizQuestionPublic(index=i, type=q["type"], topic=q["topic"], question=q["question"], code=q["code"],
                                                 language=q.get("language"), options=q["options"]) for i, q in enumerate(qs)],
                   answered={k: v["correct"] for k, v in jload(row["answers"], {}).items()}, status=row["status"])


@router.post("/quiz/generate", response_model=QuizOut)
async def generate(body: QuizIn, user: dict = Depends(current_user)):
    refs: dict[str, dict] = {}
    repo_name = None
    mix = ", ".join(TYPES)
    if body.kind == "repo":
        if not body.repo_id:
            raise HTTPException(status_code=422, detail="Load a repository first to take a repository quiz")
        repo = ready_repo(body.repo_id, user)
        repo_name = repo["name"]
        ctx = _repo_context(body.repo_id, body.focus)
        if not ctx:
            raise HTTPException(status_code=422, detail="This repository has no indexed code to quiz on")
        blocks = []
        for i, c in enumerate(ctx):
            rid = f"E{i + 1}"
            refs[rid] = {"file_path": c["file_path"], "start_line": c["start_line"], "end_line": c["end_line"], "code": c["content"][:3000], "language": c["language"]}
            sym = f" `{c['symbol_name']}`" if c["symbol_name"] else ""
            blocks.append(f"[{rid}] {c['file_path']} lines {c['start_line']}-{c['end_line']}{sym}\n```{c['language']}\n{c['content'][:2500]}\n```")
        files = [r["path"] for r in query("SELECT path FROM files WHERE repo_id=? LIMIT 120", (body.repo_id,))]
        names = [r["name"] for r in query("SELECT DISTINCT name FROM symbols WHERE repo_id=? AND kind IN ('function','method') LIMIT 150", (body.repo_id,))]
        subject = (f"the repository '{repo_name}'" + (f", focusing on {body.focus}" if body.focus else "") +
                   f".\nFILES: {', '.join(files)}\nFUNCTION NAMES IN REPO: {', '.join(names)}\nCODE EVIDENCE:\n" + "\n\n".join(blocks) +
                   "\n\nEvery question MUST be answerable from the evidence above and set \"evidence\" to the id it is based on (e.g. \"E2\"). "
                   "For identify_function questions, every option must be a real function name from the list above. Topic tags should name the "
                   "area of the repo (e.g. 'Authentication', 'Database layer').")
        topic = body.focus or "Repository architecture"
    else:
        subject = f"the programming topic: {body.topic}. Topic tags should be precise sub-topics."
        topic = body.topic
    prompt = (f"Create {body.count} quiz questions about {subject}\nDifficulty: {body.difficulty} ({DIFF[body.difficulty]}).\n"
              f"Use a varied mix of question types from: {mix}. Return JSON: "
              '{"questions": [{"type": str, "topic": str, "question": str, "code": str|null, "language": str|null, "options": [str], '
              '"answer": int (index of correct option; omit for order_steps), "correct_order": [int] (only for order_steps: option indices in the correct sequence; list options SHUFFLED), '
              '"explanation": str, "why_others_wrong": str, "evidence": str|null}]}. '
              "true_false questions must have options [\"True\", \"False\"]. predict_output questions must include the code. Explanations must be encouraging and teach.")
    try:
        data = await complete_json("You are an expert programming teacher writing accurate quizzes.", prompt, max_tokens=5000)
    except LLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    qs = [v for v in (_valid(q, refs) for q in data.get("questions", []) if isinstance(q, dict)) if v][: body.count]
    if not qs:
        raise HTTPException(status_code=502, detail="The AI did not return valid questions. Please try again.")
    for q in qs:
        q["reference"] = refs.get(q["evidence"]) if q["evidence"] else None
    qid = str(uuid.uuid4())
    row = {"kind": body.kind, "topic": topic, "difficulty": body.difficulty, "repo_name": repo_name, "questions": json.dumps(qs), "answers": "{}", "status": "active"}
    execute("INSERT INTO quizzes (id, user_id, repo_id, repo_name, kind, topic, difficulty, questions, answers, status, total, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (qid, user["id"], body.repo_id if body.kind == "repo" else None, repo_name, body.kind, topic, body.difficulty, row["questions"], "{}", "active", len(qs), now_iso()))
    return _public(qid, row)


def _quiz(qid: str, user: dict) -> dict:
    row = query_one("SELECT * FROM quizzes WHERE id=? AND user_id=?", (qid, user["id"]))
    if not row:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return row


@router.get("/quiz/{qid}", response_model=QuizOut)
def get_quiz(qid: str, user: dict = Depends(current_user)):
    return _public(qid, _quiz(qid, user))


@router.post("/quiz/{qid}/answer", response_model=AnswerOut)
def answer(qid: str, body: AnswerIn, user: dict = Depends(current_user)):
    row = _quiz(qid, user)
    qs = jload(row["questions"], [])
    if body.index >= len(qs):
        raise HTTPException(status_code=422, detail="Question index out of range")
    answers = jload(row["answers"], {})
    q = qs[body.index]
    if q["type"] == "order_steps":
        if body.order is None:
            raise HTTPException(status_code=422, detail="Provide the order of steps")
        correct = list(body.order) == q["correct_order"]
        correct_answer = " -> ".join(q["options"][i] for i in q["correct_order"])
    else:
        if body.choice is None or not 0 <= body.choice < len(q["options"]):
            raise HTTPException(status_code=422, detail="Choose an answer")
        correct = body.choice == q["answer"]
        correct_answer = q["options"][q["answer"]]
    if str(body.index) not in answers:  # first submission counts
        answers[str(body.index)] = {"correct": correct, "topic": q["topic"]}
        execute("UPDATE quizzes SET answers=? WHERE id=?", (json.dumps(answers), qid))
    ref = q.get("reference")
    return AnswerOut(correct=correct, correct_answer=correct_answer, explanation=q["explanation"], why_others_wrong=q["why_others_wrong"],
                     reference=CodeRef(**ref) if ref else None)


def _result(row: dict) -> QuizResult:
    qs = jload(row["questions"], [])
    answers = jload(row["answers"], {})
    topics: dict[str, list[int]] = {}
    for i, q in enumerate(qs):
        t = topics.setdefault(q["topic"], [0, 0])
        t[1] += 1
        if answers.get(str(i), {}).get("correct"):
            t[0] += 1
    score = sum(1 for a in answers.values() if a["correct"])
    total = len(qs) or 1
    pct = round(100 * score / total)
    strong = [t for t, (c, n) in topics.items() if c / n >= 0.75]
    weak = [t for t, (c, n) in topics.items() if c / n < 0.5]
    recs = []
    for i, q in enumerate(qs):
        if not answers.get(str(i), {}).get("correct") and q.get("reference"):
            r = q["reference"]
            recs.append(f"Explore {r['file_path']} lines {r['start_line']}-{r['end_line']} ({q['topic']})")
    recs += [f"Review {t} with a Beginner-mode explanation in the AI Workspace" for t in weak]
    if not recs:
        recs = ["Great work - try the next difficulty level" if row["difficulty"] != "hard" else "Excellent - try a repository quiz with a new focus"]
    msg = ("Outstanding - you really understand this!" if pct >= 90 else "Great job - solid understanding with a few gaps to polish." if pct >= 70
           else "Good effort - review the highlighted topics and try again." if pct >= 40 else "Every expert started here - review the explanations and give it another go.")
    return QuizResult(id=row["id"], kind=row["kind"], topic=row["topic"], difficulty=row["difficulty"], repo_name=row["repo_name"], score=score, total=len(qs),
                      percentage=pct, topics=[TopicScore(topic=t, correct=c, total=n) for t, (c, n) in topics.items()], strong=strong, weak=weak,
                      recommendations=list(dict.fromkeys(recs))[:6], message=msg, created_at=row["created_at"], completed_at=row["completed_at"])


@router.post("/quiz/{qid}/finish", response_model=QuizResult)
def finish(qid: str, user: dict = Depends(current_user)):
    row = _quiz(qid, user)
    if row["status"] != "completed":
        res = _result(row)
        execute("UPDATE quizzes SET status='completed', score=?, completed_at=? WHERE id=?", (res.score, now_iso(), qid))
        row = _quiz(qid, user)
    return _result(row)


@router.get("/quiz-history", response_model=list[QuizResult])
def quiz_history(user: dict = Depends(current_user)):
    rows = query("SELECT * FROM quizzes WHERE user_id=? AND status='completed' ORDER BY completed_at DESC LIMIT 50", (user["id"],))
    return [_result(r) for r in rows]

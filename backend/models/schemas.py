"""Pydantic v2 request/response models. Mirrored by hand in frontend/src/lib/types.ts - keep in sync."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Mode = Literal["beginner", "student", "expert"]


# ---- auth
class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: str


class SystemStatus(BaseModel):
    provider: str
    model: str
    configured: bool
    parsed_languages: list[str]
    embedding: str


# ---- repos
class SkippedFile(BaseModel):
    path: str
    reason: str


class RepoOut(BaseModel):
    id: str
    name: str
    source: str
    source_url: Optional[str] = None
    status: str
    stage: Optional[str] = None
    progress: float = 0
    files_total: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    skipped: list[SkippedFile] = []
    languages: dict[str, int] = {}
    symbol_count: int = 0
    chunk_count: int = 0
    error: Optional[str] = None
    has_git: bool = False
    is_sample: bool = False
    created_at: str


class GithubIn(BaseModel):
    url: str


class FileEntry(BaseModel):
    path: str
    language: Optional[str] = None
    line_count: int
    size: int
    parsed: bool


class SymbolSummary(BaseModel):
    id: str
    name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    language: Optional[str] = None
    parent: Optional[str] = None
    is_test: bool = False
    params: str = ""
    callers_count: int = 0
    callees_count: int = 0


class FileOut(BaseModel):
    path: str
    language: Optional[str] = None
    content: str
    line_count: int
    parsed: bool
    imports: list[str]
    description: Optional[str] = None
    symbols: list[SymbolSummary]


class SymbolDetail(SymbolSummary):
    signature: str = ""
    returns: str = ""
    docstring: str = ""
    code: str = ""
    callers: list[SymbolSummary] = []
    callees: list[SymbolSummary] = []
    related: list[SymbolSummary] = []
    external_calls: list[str] = []


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: str


class GraphOut(BaseModel):
    root_id: Optional[str] = None
    nodes: list[SymbolSummary]
    edges: list[GraphEdge]


class FlowNode(BaseModel):
    id: str
    kind: str
    label: str
    start_line: int
    end_line: int


class FlowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str = ""


class FlowOut(BaseModel):
    symbol: SymbolSummary
    nodes: list[FlowNode]
    edges: list[FlowEdge]


class ImpactIn(BaseModel):
    removed: list[str] = Field(min_length=1, max_length=20)


class TestRef(BaseModel):
    name: str
    file_path: str
    start_line: int
    end_line: int


class ImpactOut(BaseModel):
    removed: list[SymbolSummary]
    direct_dependents: list[SymbolSummary]
    transitive_dependents: list[SymbolSummary]
    orphaned: list[SymbolSummary]
    affected_files: list[str]
    related_tests: list[TestRef]
    broken_edges: list[GraphEdge]
    consequences: list[str]
    caveat: str


class DiffLine(BaseModel):
    type: str
    text: str


class Commit(BaseModel):
    hash: str
    short: str
    author: str
    date: str
    message: str
    added: int
    removed: int
    lines: list[DiffLine]


class HistoryOut(BaseModel):
    available: bool
    reason: str = ""
    commits: list[Commit] = []


# ---- evidence + chat
class Evidence(BaseModel):
    id: str
    file_path: str
    start_line: int
    end_line: int
    language: Optional[str] = None
    symbol_id: Optional[str] = None
    symbol_name: Optional[str] = None
    symbol_kind: Optional[str] = None
    code: str
    reason: str
    ai_note: str = ""
    score: float = 0
    lexical: float = 0
    semantic: float = 0
    symbol_match: bool = False
    matched_terms: list[str] = []


class Confidence(BaseModel):
    score: float
    level: str
    insufficient: bool
    factors: dict[str, float] = {}
    note: str = ""


class Selection(BaseModel):
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    symbol_id: Optional[str] = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    mode: Mode = "student"
    scope: Literal["auto", "general", "repo"] = "auto"
    conversation_id: Optional[str] = None
    repo_id: Optional[str] = None
    selection: Optional[Selection] = None
    file_path: Optional[str] = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    mode: Optional[str] = None
    scope: Optional[str] = None
    evidence: list[Evidence] = []
    confidence: Optional[Confidence] = None
    selection: Optional[Selection] = None
    created_at: str


class ChatOut(BaseModel):
    conversation_id: str
    user_message: MessageOut
    reply: MessageOut


class ConversationOut(BaseModel):
    id: str
    title: str
    repo_id: Optional[str] = None
    updated_at: str


class SearchOut(BaseModel):
    hits: list[Evidence]
    confidence: Confidence


# ---- AI tools
class DescribeIn(BaseModel):
    repo_id: str
    path: str
    mode: Mode = "student"
    refresh: bool = False


class DescribeOut(BaseModel):
    description: str


class SymbolAiIn(BaseModel):
    repo_id: str
    symbol_id: str
    mode: Mode = "student"


class WalkStep(BaseModel):
    title: str
    kind: str
    explanation: str
    start_line: int
    end_line: int


class NamedNote(BaseModel):
    name: str
    description: str


class WalkthroughOut(BaseModel):
    symbol: SymbolSummary
    purpose: str
    parameters: list[NamedNote]
    variables: list[NamedNote]
    returns: str
    steps: list[WalkStep]


class AlternativesIn(BaseModel):
    mode: Mode = "student"
    repo_id: Optional[str] = None
    symbol_id: Optional[str] = None
    concept: Optional[str] = Field(default=None, max_length=2000)


class Alternative(BaseModel):
    title: str
    language: str
    code: str
    differences: str
    pros: list[str]
    cons: list[str]
    when_to_use: str


class AlternativesOut(BaseModel):
    source: Optional[Evidence] = None
    alternatives: list[Alternative]


class CompareIn(BaseModel):
    repo_id: str
    a: str
    b: str
    mode: Mode = "student"


class CompareRow(BaseModel):
    aspect: str
    a: str
    b: str


class CompareOut(BaseModel):
    a: SymbolDetail
    b: SymbolDetail
    rows: list[CompareRow]
    similarities: list[str]
    differences: list[str]
    summary: str


class HistoryExplainOut(BaseModel):
    explanation: str


class ImpactExplainOut(BaseModel):
    explanation: str


# ---- quiz
class QuizIn(BaseModel):
    kind: Literal["general", "repo"]
    topic: str = Field(default="Programming fundamentals", max_length=120)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    count: int = Field(default=5, ge=3, le=10)
    repo_id: Optional[str] = None
    focus: Optional[str] = Field(default=None, max_length=200)


class QuizQuestionPublic(BaseModel):
    index: int
    type: str
    topic: str
    question: str
    code: Optional[str] = None
    language: Optional[str] = None
    options: list[str]


class QuizOut(BaseModel):
    id: str
    kind: str
    topic: str
    difficulty: str
    repo_name: Optional[str] = None
    questions: list[QuizQuestionPublic]
    answered: dict[str, bool] = {}
    status: str


class AnswerIn(BaseModel):
    index: int = Field(ge=0)
    choice: Optional[int] = None
    order: Optional[list[int]] = None


class CodeRef(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    code: str
    language: Optional[str] = None


class AnswerOut(BaseModel):
    correct: bool
    correct_answer: str
    explanation: str
    why_others_wrong: str
    reference: Optional[CodeRef] = None


class TopicScore(BaseModel):
    topic: str
    correct: int
    total: int


class QuizResult(BaseModel):
    id: str
    kind: str
    topic: str
    difficulty: str
    repo_name: Optional[str] = None
    score: int
    total: int
    percentage: int
    topics: list[TopicScore]
    strong: list[str]
    weak: list[str]
    recommendations: list[str]
    message: str
    created_at: str
    completed_at: Optional[str] = None

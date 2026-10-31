// Hand-written mirrors of backend/models/schemas.py — keep in sync.
export type Mode = "beginner" | "student" | "expert";

export interface UserOut {
  id: string;
  email: string;
  name: string;
  created_at: string;
}
export interface SystemStatus {
  provider: string;
  model: string;
  configured: boolean;
  parsed_languages: string[];
  embedding: string;
}

export interface SkippedFile {
  path: string;
  reason: string;
}
export interface RepoOut {
  id: string;
  name: string;
  source: string;
  source_url: string | null;
  status: string;
  stage: string | null;
  progress: number;
  files_total: number;
  files_indexed: number;
  files_skipped: number;
  skipped: SkippedFile[];
  languages: Record<string, number>;
  symbol_count: number;
  chunk_count: number;
  error: string | null;
  has_git: boolean;
  is_sample: boolean;
  created_at: string;
}
export interface FileEntry {
  path: string;
  language: string | null;
  line_count: number;
  size: number;
  parsed: boolean;
}
export interface SymbolSummary {
  id: string;
  name: string;
  kind: string;
  file_path: string;
  start_line: number;
  end_line: number;
  language: string | null;
  parent: string | null;
  is_test: boolean;
  params: string;
  callers_count: number;
  callees_count: number;
}
export interface FileOut {
  path: string;
  language: string | null;
  content: string;
  line_count: number;
  parsed: boolean;
  imports: string[];
  description: string | null;
  symbols: SymbolSummary[];
}
export interface SymbolDetail extends SymbolSummary {
  signature: string;
  returns: string;
  docstring: string;
  code: string;
  callers: SymbolSummary[];
  callees: SymbolSummary[];
  related: SymbolSummary[];
  external_calls: string[];
}
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: string;
}
export interface GraphOut {
  root_id: string | null;
  nodes: SymbolSummary[];
  edges: GraphEdge[];
}
export interface FlowNode {
  id: string;
  kind: string;
  label: string;
  start_line: number;
  end_line: number;
}
export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  label: string;
}
export interface FlowOut {
  symbol: SymbolSummary;
  nodes: FlowNode[];
  edges: FlowEdge[];
}
export interface TestRef {
  name: string;
  file_path: string;
  start_line: number;
  end_line: number;
}
export interface ImpactOut {
  removed: SymbolSummary[];
  direct_dependents: SymbolSummary[];
  transitive_dependents: SymbolSummary[];
  orphaned: SymbolSummary[];
  affected_files: string[];
  related_tests: TestRef[];
  broken_edges: GraphEdge[];
  consequences: string[];
  caveat: string;
}
export interface DiffLine {
  type: string;
  text: string;
}
export interface Commit {
  hash: string;
  short: string;
  author: string;
  date: string;
  message: string;
  added: number;
  removed: number;
  lines: DiffLine[];
}
export interface HistoryOut {
  available: boolean;
  reason: string;
  commits: Commit[];
}

export interface Evidence {
  id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  language: string | null;
  symbol_id: string | null;
  symbol_name: string | null;
  symbol_kind: string | null;
  code: string;
  reason: string;
  ai_note: string;
  score: number;
  lexical: number;
  semantic: number;
  symbol_match: boolean;
  matched_terms: string[];
}
export interface Confidence {
  score: number;
  level: string;
  insufficient: boolean;
  factors: Record<string, number>;
  note: string;
}
export interface Selection {
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_id?: string | null;
}
export interface MessageOut {
  id: string;
  role: string;
  content: string;
  mode: string | null;
  scope: string | null;
  evidence: Evidence[];
  confidence: Confidence | null;
  selection: Selection | null;
  created_at: string;
}
export interface ChatOut {
  conversation_id: string;
  user_message: MessageOut;
  reply: MessageOut;
}
export interface ConversationOut {
  id: string;
  title: string;
  repo_id: string | null;
  updated_at: string;
}
export interface SearchOut {
  hits: Evidence[];
  confidence: Confidence;
}

export interface DescribeOut {
  description: string;
}
export interface WalkStep {
  title: string;
  kind: string;
  explanation: string;
  start_line: number;
  end_line: number;
}
export interface NamedNote {
  name: string;
  description: string;
}
export interface WalkthroughOut {
  symbol: SymbolSummary;
  purpose: string;
  parameters: NamedNote[];
  variables: NamedNote[];
  returns: string;
  steps: WalkStep[];
}
export interface Alternative {
  title: string;
  language: string;
  code: string;
  differences: string;
  pros: string[];
  cons: string[];
  when_to_use: string;
}
export interface AlternativesOut {
  source: Evidence | null;
  alternatives: Alternative[];
}
export interface CompareRow {
  aspect: string;
  a: string;
  b: string;
}
export interface CompareOut {
  a: SymbolDetail;
  b: SymbolDetail;
  rows: CompareRow[];
  similarities: string[];
  differences: string[];
  summary: string;
}
export interface HistoryExplainOut {
  explanation: string;
}
export interface ImpactExplainOut {
  explanation: string;
}

export interface QuizQuestionPublic {
  index: number;
  type: string;
  topic: string;
  question: string;
  code: string | null;
  language: string | null;
  options: string[];
}
export interface QuizOut {
  id: string;
  kind: string;
  topic: string;
  difficulty: string;
  repo_name: string | null;
  questions: QuizQuestionPublic[];
  answered: Record<string, boolean>;
  status: string;
}
export interface CodeRef {
  file_path: string;
  start_line: number;
  end_line: number;
  code: string;
  language: string | null;
}
export interface AnswerOut {
  correct: boolean;
  correct_answer: string;
  explanation: string;
  why_others_wrong: string;
  reference: CodeRef | null;
}
export interface TopicScore {
  topic: string;
  correct: number;
  total: number;
}
export interface QuizResult {
  id: string;
  kind: string;
  topic: string;
  difficulty: string;
  repo_name: string | null;
  score: number;
  total: number;
  percentage: number;
  topics: TopicScore[];
  strong: string[];
  weak: string[];
  recommendations: string[];
  message: string;
  created_at: string;
  completed_at: string | null;
}

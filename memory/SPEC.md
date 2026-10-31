# CodeAtlas — living spec

AI-powered code exploration & learning platform. FastAPI + SQLite backend (`backend/data/codeatlas.db`), Vite/React/TS frontend.

## Auth

Email/password (`/api/auth/register|login|logout|me`), bcrypt hashes, httpOnly JWT cookie `codeatlas_session` (7 days).
All app routes require login; `/login` is public. Every repo/conversation/quiz is scoped to the user.

## AI provider

`lib/llm.py`: Featherless AI (OpenAI-compatible, `FEATHERLESS_API_KEY`, `FEATHERLESS_MODEL`, `FEATHERLESS_BASE_URL`) when the key is set,
otherwise the Emergent universal key fallback (`FALLBACK_LLM_PROVIDER/MODEL`, default anthropic/claude-sonnet-4-6). None → 503 with a clear message.
`GET /api/system/status` reports the active provider (shown in Settings).

## Pipeline

- Ingest: ZIP (read in memory, path traversal blocked, top folder stripped), loose files, public GitHub URL (`git clone --depth 200` into `data/repos/<id>` → enables history), or bundled sample (`backend/sample_repo`, labelled "Sample project").
- Skips node_modules/.git/dist/build/vendor/etc, lock/minified/generated files, binaries, files >400KB. Limits: 50MB zip, 1500 files.
- Background thread: tree-sitter (python, js, ts, tsx, java, c, cpp, go) → symbols (name/kind/lines/params/returns/docstring/calls), imports, call edges (name resolution, same-file preferred), chunks.
- Retrieval (`lib/retrieval.py`): BM25 + TF-IDF→LSA (TruncatedSVD) cosine + symbol-name boost, fused 0.45/0.40/0.15. Evidence quality = lexical coverage, semantic, symbol match, agreement, context (not LLM confidence).

## Data model (SQLite tables)

users, repos (status queued|indexing|ready|failed, progress, stage, languages, skipped, has_git), files (content, imports, description cache),
symbols, edges (calls|contains), chunks, conversations, messages (evidence/confidence JSON), quizzes (questions w/ answers server-side, answers, results).

## Key endpoints (all under /api)

repos: GET/DELETE /repos/{id}, POST /repos/upload (multipart `files`), /repos/github, /repos/sample, /repos/{id}/files, /file?path=, /symbols?q=, /symbols/{sid}, /graph?symbol_id=&depth=, /symbols/{sid}/flow, /symbols/{sid}/history, /search?q=, POST /impact, /impact/explain
ai: POST /chat (scope auto|general|repo; selection; file_path), GET /conversations, /conversations/{id}/messages, POST /ai/describe-file, /ai/walkthrough, /ai/alternatives, /ai/compare, /ai/history-explain
quiz: POST /quiz/generate, GET /quiz/{id}, POST /quiz/{id}/answer, /quiz/{id}/finish, GET /quiz-history

## Frontend

Shared state (`lib/appState.tsx`, localStorage): repoId, mode, selectedFile, selectedSymbolId, selection, conversationId, focus.
Pages: `/` AI Workspace (file tree | chat | Evidence/Source tabs), `/explorer` (React Flow call graph + execution flowchart, details panel, compare, impact simulation), `/learn` (quiz dashboard/runner/results/history), `/login`.

## Seed facts

- Demo user: see memory/test_credentials.md.
- Sample project (load via Upload dialog → "Load the sample project"): files app.py, auth/login.py (validate_credentials L9-18, create_session L21-25, login L28-39), auth/register.py, db/database.py, utils/security.py, tests/test_auth.py, static/login_form.js. No git history (history dialog shows the unavailable explanation).

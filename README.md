# CodeAtlas — Codebase Intelligence & Learning Platform

> Understand, navigate, and master complex codebases with AST-first analysis, grounded Hybrid RAG, and AI-powered learning.

[![Vite](https://img.shields.io/badge/Frontend-Vite%20%2B%20React%2019-646CFF?logo=vite)](https://vitejs.dev/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite)](https://www.sqlite.org/)
[![Tree-sitter](https://img.shields.io/badge/Parser-Tree--sitter-1e88e5)](https://tree-sitter.github.io/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4?logo=google)](https://ai.google.dev/)

---

## Table of Contents
1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Quick Start (One Command)](#quick-start-one-command)
4. [Manual Step-by-Step Setup](#manual-step-by-step-setup)
   - [Backend Setup](#1-backend-setup)
   - [Frontend Setup](#2-frontend-setup)
5. [Environment Variables Reference](#environment-variables-reference)
6. [Detailed Feature Guide](#detailed-feature-guide)
   - [1. Repository Ingestion & Parsing](#1-repository-ingestion--parsing)
   - [2. Code Explorer & AST Flow Diagrams](#2-code-explorer--ast-flow-diagrams)
   - [3. Grounded RAG Chat with Citations](#3-grounded-rag-chat-with-citations)
   - [4. Blast Radius & Impact Analysis](#4-blast-radius--impact-analysis)
   - [5. Active-Recall Quiz Generator](#5-active-recall-quiz-generator)
   - [6. Adaptive Audience Modes](#6-adaptive-audience-modes)
7. [Troubleshooting & FAQ](#troubleshooting--faq)

---

## Overview

**CodeAtlas** solves the cognitive overhead of reading unfamiliar code. Instead of naively sending thousands of lines of text into an LLM context window, CodeAtlas parses code into structural **Abstract Syntax Tree (AST)** symbols using **Tree-sitter**, indexes code chunks using a **Hybrid BM25 + Dense LSA (Latent Semantic Analysis)** engine, and queries **Google Gemini** to return answers with verified line-level citations.

---

## Key Features

* **Instant Repository Ingestion**: Upload a `.zip` archive, clone any public GitHub repository, or explore the built-in demo project with a single click.
* **AST-Aware Symbol Extraction**: Identifies classes, functions, methods, calls, and imports across 7+ programming languages (Python, JavaScript, TypeScript, Java, C, C++, Go).
* **Interactive Function Execution Flows**: Generates visual flowcharts mapping branches, loops, function calls, and return paths inside any function.
* **Grounded Hybrid RAG Chat**: Ask questions in natural language. Every answer cites exact file paths and line ranges (`[filepath:line]`), backed by an automated confidence score.
* **Blast-Radius Impact Analysis**: Graph-based dependency tracing that tells you which files and callers will break if you modify or delete a function.
* **Active-Recall Quiz System**: Generates self-assessment quizzes directly from repository code to accelerate onboarding and test architectural knowledge.
* **Adaptive Persona Modes**: Toggle explanations between **Beginner** (analogies & definitions), **Student** (CS concepts & execution order), and **Expert** (concurrency, trade-offs, and architecture).

---

## Quick Start (One Command)

The easiest way to start both the backend API and frontend dev server together is using the root runner script:

```bash
# Make sure the script is executable
chmod +x run.sh

# Start both servers
./run.sh
```

Once running:
* **Frontend App**: Open [http://localhost:3000](http://localhost:3000) in your browser.
* **Backend API**: Running on [http://localhost:8001](http://localhost:8001) (automatically proxied via `/api` from port 3000).

*(Press `Ctrl+C` in your terminal to cleanly stop both services).*

---

## Manual Step-by-Step Setup

If you prefer running the backend and frontend in separate terminal windows:

### 1. Backend Setup

Open a terminal and navigate to the `backend/` directory:

```bash
cd backend

# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
# macOS / Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### Configure `.env`
Create a `.env` file in the `backend/` directory:

```env
# Database & Network
DB_NAME=codeatlas
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
JWT_SECRET=dev-secret-codeatlas-key-2026

# AI Provider (Google Gemini)
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
GEMINI_MODEL=gemini-3.5-flash-lite

# Optional Alternative Providers:
# ANTHROPIC_API_KEY=your_claude_key_here
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
# FEATHERLESS_API_KEY=your_featherless_key_here
```

#### Start Backend Server
```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```
The API is now running at `http://localhost:8001`. You can test it in another tab:
```bash
curl http://localhost:8001/api/
# {"message":"CodeAtlas API"}
```

---

### 2. Frontend Setup

Open a second terminal window and navigate to `frontend/`:

```bash
cd frontend

# Install node dependencies
yarn install
# (or: npm install)

# Start Vite development server
yarn dev
# (or: npm run dev)
```

The frontend will start at **http://localhost:3000**. Vite automatically proxies any relative request from `/api/*` to `http://localhost:8001/api/*`.

---

## Environment Variables Reference

All backend configurations live in `backend/.env`:

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API key from Google AI Studio | `AQ.Ab8RN6...` |
| `GEMINI_MODEL` | Gemini model to use for completion & JSON | `gemini-3.5-flash-lite` |
| `ANTHROPIC_API_KEY` | (Optional) Anthropic API key for Claude | `sk-ant-...` |
| `ANTHROPIC_MODEL` | (Optional) Claude model variant | `claude-3-5-sonnet-20241022` |
| `FEATHERLESS_API_KEY`| (Optional) Featherless AI API key | `rc_...` |
| `JWT_SECRET` | Secret key used to sign HTTP-only session cookies | `dev-secret-key-change-me` |
| `CORS_ORIGINS` | Allowed origins for cross-origin browser requests | `http://localhost:3000,http://127.0.0.1:3000` |
| `SQLITE_PATH` | File path for SQLite database file | `backend/data/codeatlas.db` |

---

## Detailed Feature Guide

### 1. Repository Ingestion & Parsing
* **Where to find it**: The **Workspace** dashboard (`/`).
* **How it works**:
  * **Upload ZIP**: Click **Upload Repo** to upload any project archive. Non-code files (images, binaries, `.git`, `node_modules`) are automatically ignored.
  * **GitHub Clone**: Provide a public repository URL to clone and index automatically.
  * **Sample Project**: Click **Load Sample Project** to instantly load the bundled `flask-auth-demo` application.
* **Under the hood**: As files are saved, `backend/lib/parser.py` runs **Tree-sitter** parsers on every source file, extracting function signatures, docstrings, classes, and cross-file dependencies into SQLite.

### 2. Code Explorer & AST Flow Diagrams
* **Where to find it**: The **Explorer** tab (`/explorer`).
* **How it works**:
  * **File Tree**: Browse directories and files on the left sidebar.
  * **Symbol Outline**: Click on any file to inspect all classes, methods, and functions with start/end lines.
  * **Execution Flow Diagram**: Click the **Flow** button on any function to view an auto-generated flowchart visualizing loops, conditionals, branches, and return statements.

### 3. Grounded RAG Chat with Citations
* **Where to find it**: The chat panel on the right side of the **Explorer**.
* **How it works**:
  * Ask natural language questions like: *"How does session generation work?"* or *"Where is the database initialized?"*
  * The response provides a conversational explanation with **bracketed citations** like `[app.py:10-25]`.
  * Click on any citation pill to jump straight to that file and highlight the exact code lines.
  * Expand the **Evidence** dropdown to inspect the raw code snippets and lexical/semantic similarity scores retrieved for your prompt.
  * View the **Confidence Score** meter (High, Medium, Low) verifying how closely the retrieved code matches your query.

### 4. Blast Radius & Impact Analysis
* **Where to find it**: The **Impact** tab in the Explorer central viewer.
* **How it works**:
  * Select a function or class to simulate: *"What happens if I change or remove this function?"*
  * The backend performs a Breadth-First Search (BFS) over the dependency graph in SQLite.
  * Displays:
    * **Direct Callers**: Immediate functions that invoke this symbol.
    * **Transitive Callers**: Upstream components that depend on it indirectly.
    * **Affected Files & Tests**: Modules that will break and need refactoring.

### 5. Active-Recall Quiz Generator
* **Where to find it**: The **Learning** tab (`/learn`).
* **How it works**:
  * Click **Generate Quiz** and select question count.
  * Google Gemini inspects AST symbols and code snippets from the active repository in JSON mode to build an active-recall quiz.
  * Includes:
    * **Multiple Choice**: Conceptual and syntax questions.
    * **Code Comprehension**: Reading a code block and predicting return values or security risks.
    * **True / False**: Architectural invariants.
  * Submit answers to receive immediate grading, explanation of mistakes, and score history.

### 6. Adaptive Audience Modes
* **Where to find it**: Toggle in the header or in **Settings** (`⚙️`).
* **Modes**:
  * 🟢 **Beginner**: Uses simple analogies, step-by-step numbered points, and defines technical jargon.
  * 🟡 **Student**: Focuses on computer science fundamentals, algorithm logic, function parameters, and execution order.
  * 🔴 **Expert**: Concisely explains design patterns, cyclomatic complexity, concurrency risks, and architectural trade-offs.

---

## Troubleshooting & FAQ

### 1. `Cannot reach Google Gemini API: [Errno 8] nodename nor servname provided`
* **Cause**: The backend process was executed in an environment or sandbox without outbound internet access.
* **Fix**: Ensure your shell has active internet access and can reach `https://generativelanguage.googleapis.com`. Run `./run.sh` directly from your local terminal.

### 2. `This model models/gemini-2.5-flash is no longer available`
* **Cause**: Older Google Gemini model IDs may be deprecated by Google AI Studio.
* **Fix**: Make sure `GEMINI_MODEL=gemini-3.5-flash-lite` in `backend/.env`.

### 3. Port 8001 or Port 3000 is already in use
* **Cause**: A previous server process is still running in the background.
* **Fix**:
  ```bash
  # Find and kill process on port 8001
  lsof -ti:8001 | xargs kill -9
  # Find and kill process on port 3000
  lsof -ti:3000 | xargs kill -9
  ```

### 4. Where is the database stored?
* All data (users, repositories, symbols, graphs, chat conversations, and quizzes) is stored locally in:
  ```
  backend/data/codeatlas.db
  ```
  To start with a fresh slate, delete `codeatlas.db` and restart the backend.

---

## Technology Stack

* **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, Lucide Icons, Sonner.
* **Backend**: FastAPI, Uvicorn, Python 3.10+, Pydantic v2.
* **Code Parsing**: Tree-sitter, `tree-sitter-language-pack`.
* **RAG & Search**: Scikit-learn (TF-IDF, TruncatedSVD LSA), NumPy, Okapi BM25.
* **Storage**: SQLite 3 with foreign key cascading and B-tree indexes.
* **AI Provider**: Google Gemini (`gemini-3.5-flash-lite`) with JSON schema mode.

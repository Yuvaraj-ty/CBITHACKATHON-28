#!/usr/bin/env bash
set -e

# Resolve repository root
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting CodeAtlas..."

# Trap Ctrl+C (SIGINT/SIGTERM) to kill both child processes
cleanup() {
  echo ""
  echo "🛑 Stopping CodeAtlas servers..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  wait $BACKEND_PID 2>/dev/null || true
  wait $FRONTEND_PID 2>/dev/null || true
  echo "✅ Stopped."
}
trap cleanup INT TERM

# 1. Start backend server
echo "📦 Starting FastAPI backend on http://localhost:8001..."
cd "$ROOT_DIR/backend"
"$ROOT_DIR/backend/.venv/bin/uvicorn" server:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!

# 2. Start frontend dev server
echo "💻 Starting Vite frontend on http://localhost:3000..."
cd "$ROOT_DIR/frontend"
yarn dev &
FRONTEND_PID=$!

echo ""
echo "✨ CodeAtlas is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8001"
echo "Press Ctrl+C to stop both servers."
echo ""

wait

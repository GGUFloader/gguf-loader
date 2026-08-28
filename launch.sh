#!/bin/bash
echo "================================"
echo "   GGUF Loader - Starting..."
echo "================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Please install Python 3.10+."
    exit 1
fi

# Detect mode
if command -v node &> /dev/null && [ -f "frontend/dist/index.html" ]; then
    MODE="dev"
else
    MODE="prod"
fi

if [ "$MODE" = "dev" ]; then
    echo "[DEV] Starting in development mode..."
    echo ""

    # Start FastAPI backend
    echo "[1/3] Starting backend server..."
    cd "$(dirname "$0")"
    python3 -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --reload &
    BACKEND_PID=$!

    # Wait for backend
    echo "[2/3] Waiting for backend..."
    sleep 3

    # Start Vite dev server
    echo "[3/3] Starting frontend dev server..."
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..

    echo ""
    echo "================================"
    echo " Backend:  http://localhost:8000"
    echo " Frontend: http://localhost:5173"
    echo "================================"
    echo ""
    echo "Press Ctrl+C to stop."

    # Trap to cleanup
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
    wait
else
    echo "[PROD] Starting in production mode..."
    echo ""

    # Build frontend if needed
    if [ ! -f "frontend/dist/index.html" ]; then
        echo "Building frontend..."
        cd frontend
        npm install
        npm run build
        cd ..
    fi

    # Start FastAPI backend (serves built frontend)
    echo "Starting server..."
    cd "$(dirname "$0")"
    python3 -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --host 0.0.0.0

    echo ""
    echo "Server stopped."
fi

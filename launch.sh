#!/bin/bash
echo "==============================================="
echo "   GGUF Loader - Local AI Workstation"
echo "==============================================="
echo ""

# ============================================
#  Check Python
# ============================================
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "[ERROR] Python not found."
    echo "        Install Python 3.10+ and add to PATH."
    exit 1
fi

PYTHON="python3"
command -v python3 &> /dev/null || PYTHON="python"
PYVER=$($PYTHON --version 2>&1 | awk '{print $2}')
echo "[OK] Python $PYVER"

# ============================================
#  Check/Install Python dependencies
# ============================================
if [ -f "requirements.txt" ]; then
    $PYTHON -c "import uvicorn" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "[SETUP] Installing Python dependencies..."
        $PYTHON -m pip install -r requirements.txt -q
        echo "[OK] Python dependencies installed."
    else
        echo "[OK] Python dependencies ready."
    fi
fi

# ============================================
#  Check Node.js
# ============================================
if ! command -v node &> /dev/null; then
    echo "[INFO] Node.js not found. Starting in production mode..."
    MODE="prod"
else
    NODEVER=$(node --version)
    echo "[OK] Node.js $NODEVER"
    MODE="dev"
fi

# ============================================
#  Check/Install frontend dependencies
# ============================================
if [ "$MODE" = "dev" ] && [ ! -d "frontend/node_modules" ]; then
    echo "[SETUP] Installing frontend dependencies..."
    cd frontend && npm install && cd ..
    echo "[OK] Frontend dependencies installed."
fi

# ============================================
#  Start servers
# ============================================
if [ "$MODE" = "dev" ]; then
    echo ""
    echo "[DEV] Starting in development mode..."
    echo ""

    # Start backend
    echo "[1/3] Starting backend (FastAPI on :8000)..."
    $PYTHON -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --reload &
    BACKEND_PID=$!

    # Wait for backend
    echo "[2/3] Waiting for backend..."
    sleep 3

    # Start frontend
    echo "[3/3] Starting frontend (Vite on :5173)..."
    cd frontend && npm run dev &
    FRONTEND_PID=$!
    cd ..

    echo ""
    echo "==============================================="
    echo "  GGUF Loader is running!"
    echo ""
    echo "  Frontend:  http://localhost:5173"
    echo "  Backend:   http://localhost:8000"
    echo "  API Docs:  http://localhost:8000/docs"
    echo "==============================================="
    echo ""
    echo "  Press Ctrl+C to stop both servers."
    echo ""

    # Cleanup on exit
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Servers stopped.'; exit" INT TERM
    wait
else
    echo ""
    echo "[PROD] Starting in production mode..."
    echo ""

    # Build frontend if needed
    if [ ! -f "frontend/dist/index.html" ]; then
        echo "[BUILD] Building frontend..."
        if [ ! -d "frontend/node_modules" ]; then
            cd frontend && npm install && cd ..
        fi
        cd frontend && npm run build && cd ..
        echo "[OK] Frontend built."
    fi

    echo "[START] Starting server..."
    echo ""
    echo "==============================================="
    echo "  GGUF Loader is running!"
    echo ""
    echo "  App:  http://localhost:8000"
    echo "  API:  http://localhost:8000/docs"
    echo "==============================================="
    echo ""
    $PYTHON -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --host 0.0.0.0
    echo ""
    echo "Server stopped."
fi

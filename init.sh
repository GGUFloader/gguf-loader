#!/bin/bash
set -e

echo "=== GGUF Loader Harness Initialization ==="

# Activate virtualenv if present
if [ -d ".venv" ]; then
  echo "=== Activating .venv ==="
  source .venv/bin/activate 2>/dev/null || .venv\Scripts\activate 2>/dev/null || true
fi

# Install dependencies
if [ -f "requirements.txt" ]; then
  echo "=== Installing dependencies ==="
  pip install -r requirements.txt -q
fi

# Install dev dependencies
echo "=== Installing dev dependencies ==="
pip install -e ".[dev]" -q 2>/dev/null || pip install pytest -q

# Run tests
echo "=== Running tests ==="
python -m pytest tests/unit -x -q

# Syntax check all Python files
echo "=== Syntax check ==="
python -m compileall -q -x '(^|/)(\.?venv|env|node_modules|build|dist|__pycache__)(/|$)' ggufloader/

echo ""
echo "=== Verification Complete ==="
echo ""
echo "Next steps:"
echo "1. Read feature_list.json to see current feature state"
echo "2. Pick ONE unfinished feature to work on"
echo "3. Implement only that feature"
echo "4. Re-run: python -m pytest tests/unit -x -q"
echo "5. Update progress.md with evidence before claiming done"

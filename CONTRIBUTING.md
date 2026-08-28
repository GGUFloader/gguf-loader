# Contributing to GGUF Loader

Thank you for your interest in contributing! This guide covers both the Python backend and React frontend.

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git

### Clone & Install

```bash
git clone https://github.com/GGUFloader/gguf-loader.git
cd gguf-loader

# Python backend
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# React frontend
cd frontend
npm install
cd ..
```

### Run in Development

```bash
# Option 1: Launch script (starts both)
launch.bat  # or ./launch.sh

# Option 2: Manual
# Terminal 1: Backend
python -m uvicorn ggufloader.api.app:create_app --factory --port 8000 --reload

# Terminal 2: Frontend (hot reload)
cd frontend && npm run dev
```

Open http://localhost:5173 (Vite dev server with API proxy).

## Project Structure

```
ggufloader/
├── api/              # FastAPI backend (Python)
├── core/             # Business logic (Python)
├── services/         # Application services (Python)
├── ui/               # PySide6 UI (legacy, kept for --qt)
├── widgets/          # PySide6 widgets (legacy)
frontend/
├── src/
│   ├── api/          # REST client (TypeScript)
│   ├── stores/       # Zustand state (TypeScript)
│   ├── hooks/        # Custom hooks (TypeScript)
│   └── components/   # React components (TSX)
electron/             # Electron packaging (TypeScript)
tests/                # Python tests (pytest)
```

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for full details.

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Run `pytest` before committing

### TypeScript/React

- Use functional components with hooks
- Prefer Zustand stores over prop drilling
- Use Tailwind CSS for styling (no CSS modules)
- Run `npm run lint` and `npm run typecheck` before committing

```bash
cd frontend
npm run lint          # Check for issues
npm run lint:fix      # Auto-fix
npm run typecheck     # TypeScript check
npm run format        # Format with Prettier
```

## Making Changes

### Python Backend

1. Edit files in `ggufloader/api/`, `ggufloader/core/`, or `ggufloader/services/`
2. Add tests in `tests/`
3. Run `python -m pytest tests/ -x`

### React Frontend

1. Edit files in `frontend/src/`
2. Components go in `frontend/src/components/<category>/`
3. State stores go in `frontend/src/stores/`
4. API client functions go in `frontend/src/api/client.ts`
5. Run `npm run build` to verify

### Adding a New API Endpoint

1. Create route in `ggufloader/api/routes/<name>.py`
2. Register in `ggufloader/api/app.py`
3. Add client function in `frontend/src/api/client.ts`
4. Add integration test in `tests/test_api_integration.py`

### Adding a New React Component

1. Create in `frontend/src/components/<category>/<Name>.tsx`
2. Use existing patterns (see `ChatBubble.tsx` or `ToolCallCard.tsx`)
3. Import icons from `lucide-react`
4. Use Tailwind classes for styling

## Testing

### Python Tests

```bash
python -m pytest tests/ -x              # All tests
python -m pytest tests/test_api_integration.py -v  # Integration tests
```

### Frontend Build

```bash
cd frontend
npm run build          # TypeScript + Vite build
npm run typecheck      # TypeScript only
npm run lint           # Lint check
```

## Commit Guidelines

- Use descriptive commit messages
- Reference issue numbers when applicable
- Keep commits focused (one feature/fix per commit)
- Run tests before committing

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`python -m pytest tests/ -x && cd frontend && npm run build`)
5. Commit your changes
6. Push to your fork
7. Open a Pull Request

## Architecture Decisions

- **React over PySide6**: React gives us a modern, web-standard UI that can be packaged as Electron for desktop
- **FastAPI over Flask**: Async support, automatic API docs, WebSocket support
- **Zustand over Redux**: Lightweight, no boilerplate, TypeScript-first
- **Tailwind over CSS modules**: Utility-first, consistent design, faster development
- **Vite over Webpack**: Faster builds, better DX, native ESM

## Questions?

Open a [Discussion](https://github.com/GGUFloader/gguf-loader/discussions) or email hussainnazary475@gmail.com.

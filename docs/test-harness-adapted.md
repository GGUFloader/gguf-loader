# Test Harness Adapted for GGUFLoader

> **📜 Historical document** — describes GGUF Loader at an earlier stage of the
> project and is kept for reference. The current build is a **single-model
> (Gemma 4 12B Q4_K_M)** agent app with a **React/TypeScript frontend and
> FastAPI backend**, running a strictly **plan-driven LangGraph agent** (no
> reactive loop, no multi-model family tuning). UI and architecture details
> below may be outdated.

## Tiers

1. **Unit** (free) - Pure logic: path sandbox, approval, JSON extraction
2. **Integration** (free) - Agent loop with mock LLM
3. **Eval** (paid) - Real model quality

## Current Coverage

- Tier 1: 34 tests in tests/safety_gates/ (all passing)
- Tier 2: Planned (agent loop tests)
- Tier 3: Planned (model quality eval)

## Rule

Start at cheapest tier. Climb only when it cant answer the question.

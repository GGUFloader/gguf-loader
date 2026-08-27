# Test Harness Adapted for GGUFLoader

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

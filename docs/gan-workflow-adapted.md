# GAN-Style Generator-Evaluator Workflow (Adapted for GGUFLoader)

> **📜 Historical document** — describes GGUF Loader at an earlier stage of the
> project and is kept for reference. The current build is a **single-model
> (Gemma 4 12B Q4_K_M)** agent app with a **React/TypeScript frontend and
> FastAPI backend**, running a strictly **plan-driven LangGraph agent** (no
> reactive loop, no multi-model family tuning). UI and architecture details
> below may be outdated.

> Based on Anthropic's GAN-style harness design, adapted for Python desktop apps.

## Core Insight (preserved)

> When asked to evaluate their own work, agents are pathological optimists.
> A separate evaluator that is ruthlessly strict drives quality higher than
> self-critique ever can.

## Adaptation for GGUFLoader

The original GAN harness assumes:
- Web apps with Playwright browser testing
- Cloud APIs (Claude Sonnet) at $125-200 per run
- 5-15 full rebuild iterations

GGUFLoader needs:
- Python code quality evaluation (tests, lint, type check)
- Local model inference (free but slower)
- Incremental improvements (not full rebuilds)

## adapted Architecture

```
┌─────────────────────────────────────────────┐
│              PLANNER (optional)              │
│  Expands feature request into spec with:    │
│  - Acceptance criteria                      │
│  - Evaluation rubric                        │
│  - Edge cases to test                       │
└──────────────────┬──────────────────────────┘
                   │ Feature Spec
                   ▼
┌─────────────────────────────────────────────┐
│         GENERATOR-EVALUATOR LOOP            │
│                                             │
│  ┌──────────┐     ┌──────────┐             │
│  │GENERATOR │────>│EVALUATOR │             │
│  │          │     │          │             │
│  │ Implements│     │ Tests:   │             │
│  │ feature   │     │ - pytest │             │
│  │ code      │     │ - compile│             │
│  └────▲─────┘     │ - review │             │
│       │           └────┬─────┘             │
│       │                │                    │
│       └── feedback ────┘                    │
│                                             │
│   2-5 iterations (not 15)                   │
└─────────────────────────────────────────────┘
```

## The Two Agents

### Generator

**Role:** Implements the feature according to the spec.

**Behaviors:**
- Reads the feature spec and acceptance criteria
- Writes code following project conventions (AGENTS.md)
- Runs `python -m pytest tests/unit -x -q` after each change
- Reads evaluator feedback and iterates

### Evaluator

**Role:** Ruthlessly critiques the generated code.

**Behaviors:**
- Does NOT praise mediocre work
- Tests the code (runs pytest, compile check)
- Reviews for:
  1. **Correctness** — Does it work? Edge cases?
  2. **Convention** — Follows AGENTS.md rules?
  3. **Testability** — Are there tests? Do they pass?
  4. **Safety** — No path escapes, no unguarded imports?
  5. **Clarity** — Is the code readable and documented?
- Returns structured feedback with scores and specific issues
- NEVER suggests fixes (that's the generator's job)

## Evaluation Rubric (adapted for Python)

### Correctness (weight: 0.3)
- 1-3: Core logic broken, exceptions unhandled
- 4-6: Happy path works, edge cases fail
- 7-8: All paths work, good error messages
- 9-10: Bulletproof, handles every edge case

### Convention Compliance (weight: 0.2)
- 1-3: Violates AGENTS.md rules (wrong module, blocks UI thread)
- 4-6: Mostly follows conventions, minor deviations
- 7-8: Fully compliant, clean imports
- 9-10: Exemplary, could be a reference

### Test Coverage (weight: 0.2)
- 1-3: No tests or tests don't pass
- 4-6: Basic happy-path tests exist
- 7-8: Good coverage, edge cases tested
- 9-10: Comprehensive, mutation-tested

### Code Safety (weight: 0.2)
- 1-3: Path escapes, unguarded imports, blocking calls
- 4-6: Basic sandboxing, some guards missing
- 7-8: Full path validation, lazy imports, async-safe
- 9-10: Defense in depth, audit-ready

### Code Clarity (weight: 0.1)
- 1-3: Unreadable, no docs, magic numbers
- 4-6: Somewhat clear, minimal docs
- 7-8: Well-documented, clear naming
- 9-10: Exemplary, self-documenting

## Scoring

- **Weighted score** = sum of (criterion_score * weight)
- **Pass threshold** = 7.0
- **Max iterations** = 5 (typically 2-3 sufficient for incremental work)

## Usage

### For a new feature (e.g., feat-011 Self-Verification)

```
1. PLANNER: Write spec.md with acceptance criteria
2. GENERATOR: Implement the feature
3. EVALUATOR: Score against rubric, write feedback-001.md
4. GENERATOR: Read feedback, fix issues
5. EVALUATOR: Re-score, write feedback-002.md
6. Repeat until score >= 7.0
```

### Quick iteration (single-agent mode)

When running locally with one agent, simulate the loop:

```
1. Write the code (generator role)
2. Run tests yourself (evaluator role)
3. Score against rubric honestly
4. If score < 7.0, fix issues and re-test
5. Repeat until passing
```

## Anti-Patterns (preserved from original)

1. **Evaluator too lenient** — If everything passes on iteration 1, tighten the rubric
2. **Generator ignoring feedback** — Always pass feedback as a file, not inline
3. **Infinite loops** — Set max iterations; stop after 3 iterations without improvement
4. **Evaluator suggesting fixes** — Evaluator only critiques; generator fixes
5. **Skipping evaluation** — Never claim "done" without evaluator sign-off

## Key Difference from Original

The original GAN harness runs 3 separate Claude instances at $125-200.
This adapted version runs with a single local model, using the same
adversarial principle but in a lighter-weight form.

The tradeoff: lower cost (~$0) but requires the agent to honestly
switch between generator and evaluator roles. The harness-creator's
"definition of done" and "completion gate" help enforce this.

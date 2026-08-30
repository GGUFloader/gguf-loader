# Fuzzing Harnesses for GGUFLoader

Coverage-guided fuzzing using [atheris](https://github.com/google/atheris) (Google's Python fuzzer).

## Setup

```bash
pip install atheris
```

## Targets

| Harness | Target | Risk | What it tests |
|---------|--------|------|---------------|
| `fuzz_text_extract.py` | PDF/DOCX parsing | HIGH | `_docx_text`, `_minimal_pdf_text`, `_extract_text_operators`, `_unescape_pdf_string` |
| `fuzz_json_extract.py` | Model output parsing | MEDIUM | `extract_json` — malformed JSON from weak local models |
| `fuzz_template.py` | Chat template detection | LOW | `_template_supports_system` — template string matching |
| `fuzz_all.py` | All targets (interleaved) | ALL | Shared corpus across all entry points |

## Running

```bash
# Fuzz a single target (run for 60 seconds)
python fuzz/fuzz_text_extract.py -atheris_args=-max_total_time=60

# Fuzz all targets with shared corpus
python fuzz/fuzz_all.py -atheris_args=-max_total_time=120

# Fuzz with a seed corpus directory
python fuzz/fuzz_text_extract.py -atheris_args=-atheris_in=seeds/

# Fuzz with timeout per input (default: 5 seconds)
python fuzz/fuzz_text_extract.py -atheris_args=-timeout=10
```

## Understanding Output

atheris reports:
- **Total runs**: Number of inputs tested
- **Total coverage**: Edge coverage achieved
- **Crashes**: Inputs that caused exceptions (saved to `crash-*` files)
- **Slowest unit**: Input that took the longest to process

## Reproducing Crashes

When atheris saves a crash file:

```bash
# Replay a specific crash
python fuzz/fuzz_text_extract.py crash-<hash>

# Or read the crash input
cat crash-<hash> | python -c "
import sys
from ggufloader.core.agent.text_extract import _docx_text
data = sys.stdin.buffer.read()
_docx_text(data)
"
```

## Harness Design (following harness-writing skill)

### Pattern: Interleaved Fuzzing

`fuzz_all.py` uses interleaved fuzzing — the first byte selects which
target to exercise. This gives the fuzzer a shared corpus where
interesting inputs for one target may be interesting for others.

### Pattern: Input Validation

All harnesses reject inputs that are too small:
```python
if len(data) < 1:
    return
```

### Pattern: Exception Isolation

All harnesses wrap target calls in try/except to prevent harness crashes:
```python
try:
    _docx_text(payload)
except Exception:
    pass
```

Crashes in the SUT (unhandled exceptions) are what we're looking for.
Crashes in the harness itself are bugs in the harness.

### Pattern: Type Coercion

Bytes are decoded to strings before string-target functions:
```python
text = payload.decode("latin-1", errors="replace")
_extract_text_operators(text)
```

This ensures every byte sequence produces a valid string input.

## Coverage Goals

| Module | Target Coverage |
|--------|----------------|
| `text_extract.py` | All PDF operators, DOCX XML paths, edge cases in unescaping |
| `agent_engine.py` | All JSON repair attempts, balanced-brace detection |
| `model_profiles.py` | All template detection branches |

## Anti-Patterns Avoided

- **No global state**: Each iteration is independent
- **No I/O**: All targets operate on in-memory data
- **No logging**: Harnesses are fast (1000s exec/sec)
- **No `exit()`**: Only exceptions, which atheris catches
- **Deterministic**: Same input always produces same behavior

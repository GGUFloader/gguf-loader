# Enhancement Backlog: Ideas from GPT4All for GGUF Loader

> **📜 Historical document** — describes GGUF Loader at an earlier stage of the
> project and is kept for reference. The current build is a **single-model
> (Gemma 4 12B Q4_K_M)** agent app with a **React/TypeScript frontend and
> FastAPI backend**, running a strictly **plan-driven LangGraph agent** (no
> reactive loop, no multi-model family tuning). UI and architecture details
> below may be outdated.

Companion to `docs/comparison-ggufloader-vs-gpt4all.md`. Every item here was
found by auditing GPT4All v3.10 source (`gpt4all-chat/src/`,
`gpt4all-backend/src/`) and evaluated against our codebase.

Legend: **P0** = do next · **P1** = high value, plan it · **P2** = nice-to-have.
Effort: **S** ≤ half day · **M** ≤ 2 days · **L** = multi-day project.

---

## A. Generation Robustness

### A1. Stop-string partial-match holdback — P0, S
GPT4Aall withholds the buffer tail while it *prefix-matches* any stop
sequence, so a stop string split across token chunks can never leak into the
visible answer (`gpt4all-chat` backend `llmodel_shared.cpp:123-140`).
**Ours:** extend `ModelBackend.chat_stream` consumers (`ChatService`,
`AgentService`) or better `chat_stream` itself: keep a rolling tail of
`len(longest_stop)-1` chars, release text only when it can no longer start a
stop. Our current parser `_HOLD=20` covers think-tags but not `CHAT_STOP_TOKENS`.

### A2. Graceful context overflow — P0, M
When KV nears `n_ctx`, GPT4All evicts the oldest 50% (after BOS) mid-stream
and keeps generating ("infinite chat"); oversized single inputs are pre-trimmed
to `n_ctx*(1-erase)` (`llmodel_shared.cpp:69-88,167-171`). We currently let
llama.cpp fail/degrade silently.
**Ours:** in `ChatService`/prompt build, count tokens (via
`backend.llama.tokenize` equivalent) and drop oldest history turns until the
rendered prompt fits `n_ctx - max_tokens - margin`; surface a one-time system
note "older messages were trimmed". The per-message guard ("message too long"
error before sending, `chatllm.cpp:1037-1051`) is a cheap P0 subset.

### A3. KV prefix caching between turns — P1, M
They reuse the longest-common-token-prefix with the previous turn so turn 2+
doesn't re-evaluate the whole history (`computeModelInputPosition`,
`llamamodel.cpp:677-687`). This is why Ollama/GPT4All feel instant on
follow-ups. **Ours:** keep last rendered prompt's token list +
`Llama.save_state()`/`load_state()` snapshots in `ChatPanel`'s service;
on new send, find LCP and `n_prompt` only the suffix. Needs care with our
lock-per-stream model but is contained inside `ModelBackend`.

### A4. min_p sampling + greedy mode — P2, S
Their sampler chain supports `min_p` and an explicit greedy branch at temp 0
(`llamamodel.cpp:556-596`). llama-cpp-python passes both through — just expose
`min_p` in profile params (`model_profiles.py::_p`) and skip temperature
sampling when 0.

---

## B. Model Loading & GPU UX

### B1. Honest GPU status + fallback reasons — P0, S→M
After load, GPT4All reports exactly why a model is on CPU: "no GPU support" /
"GPU loading failed (out of VRAM?)" / "model or quant has no GPU support"
(`chatllm.cpp:638-665`). We silently ignore offload failures (the two-
environment incident!).
**Ours:** after `Llama(...)` in `model_backend.py`, query offload state
(`llama_cpp.llama_cpp.llama_n_gpu_layers`-style probe or timing heuristic),
and render one of those three strings in `sidebar.set_model_info`. Also show
VRAM/RAM required vs available if obtainable.

### B2. Per-layer GPU control — P1, M
`gpuLayers` setting (default all) with retry ladder: full → fewer layers →
CPU (`chatllm.cpp:627-658`). **Ours:** add a spinbox next to the GPU toggle;
pass through `n_gpu_layers`; on CUDA OOM error at load, auto-retry at 50%,
then CPU, reporting what worked.

### B3. Read max context from GGUF — P1, S
They read `{arch}.context_length` to cap the context spinner, fallback 4096
(`modellist.cpp:291-302`); we already parse GGUF headers in
`model_profiles.read_gguf_general_metadata` — extend wanted keys with
`{arch}.context_length`, `{arch}.block_count`, `general.quantization_version`
and clamp `DEFAULT_CONTEXT_SIZES` choices + warn beyond trained length
(we already warn via `n_ctx_train`; note llama-cpp-python 0.3.34 exposes it
as method-or-nothing — our defensive property handles both).

### B4. Memory estimate before load — P2, M
`requiredMem(path,n_ctx,ngl)` shown before committing (`llmodel.h:153`).
Hard to replicate precisely via llama-cpp-python; approximate from
quant-bytes-per-param × params + KV formula. Low priority given B1 honesty.

---

## C. Sampling & Profiles

### C1. Per-model settings UI — P0, M
Every sampling knob persisted per model id (`mysettings.cpp:332-353`,
keys `temperature/topP/minP/topK/maxLength/promptBatchSize/contextLength/
gpuLayers/repeatPenalty/repeatPenaltyTokens`).
**Ours:** promote `model_params.json` (already implemented) into the UI:
a "⚙ Model Params" dialog editing the same JSON, live-bound to the loaded
model, plus "Reset to family defaults". The router (`model_profiles.py`)
already merges user > family > generic.

### C2. More family profiles — P1, ongoing
Add Mistral (0.7/…), Phi-4 (0.7/0.95), Granite, OLMoE, Hermes, Yi, InternLM
to `FAMILY_PROFILES`. Each is a data entry + optional template quirk note.

### C3. Editable per-model system prompt — P1, S
`systemMessage` per model (`mysettings.cpp:355-412`). **Ours:** plumb through
`resolve_chat_config()["system_prompt"]` → already consumed by
`build_messages(system_prompt=...)`. Add textarea in the C1 dialog.

---

## D. Chat Sessions & Transcript UX

### D1. Schema v2 — richer items — P1, M
Their chat format stores recursive sub-items: Think (with ms duration),
ToolCall (params/result/error), ToolResponse, isError flag, thumbs feedback
(`chatmodel.cpp:72-148`). **Ours:** bump sessions to v2: store
`{"role":"assistant","content","ts","thinking_ms":N}` and full approval
outcome on tool entries; loader tolerates v1. Enables replaying collapsed
thought cards *with* real durations (today we lose timing).

### D2. LLM-generated chat titles — P1, S
After the first reply, a tiny auxiliary call names the chat (≤3 words prompt,
think-content discarded, `chatllm.cpp:1175-1233`). We derive titles from the
first user message. **Ours:** keep derivation as instant title, then upgrade
async via a 40-token `max_tokens` call using the same backend; rename only if
user hasn't manually renamed (add `title_locked` flag on rename).

### D3. Suggested follow-up questions — P2, S
Post-answer auxiliary generation rendering clickable suggestion chips
(`generateQuestions`, `chatllm.cpp:1306-1342`).
**Ours:** one extra non-streaming call with strict JSON output
`{"questions":[...]}`; render as buttons above the input box.

### D4. Date-grouped sidebar — P2, S
Sections Today / This Week / This Month / Older (`chatlistmodel.h:88-107`).
**Ours:** group in `sidebar_panel.set_sessions` by `updated`.

### D5. Message actions — P2, M
Copy-message button, delete-pair, and regenerate-last-response (reset state
and re-run). Regenerate needs `conversation_history` pop + re-send plumbing in
`main_window._send_message` — moderate.

---

## E. LocalDocs-classic (RAG) — P1, L (the big one)

Full design exists in their v3 stack; every piece is replicable in Python:

| Piece | Their implementation | Our port |
|---|---|---|
| Store | SQLite `localdocs_v3.db`: chunks + FTS5(porter) + float32 BLOB embeddings | identical via stdlib `sqlite3`; embeddings as `numpy.frombuffer` |
| Retrieval | exact KNN (usearch inner product) fused with BM25 by weighted RRF k=60; BM25 weight 0.9 phrase / 0.25–0.75 else | brute-force IP over numpy (fine ≤1M chunks) + sqlite FTS5 `bm25()`; same RRF math |
| Embeddings | nomic-embed-text-v1.5 f16 GGUF bundled; batches 100→4; `search_document:`/`search_query:` prefixes; L2 norm | run through our own `ModelBackend` (embeddings supported by llama.cpp) in a worker thread; ship/download the small (~170MB) embed GGUF once |
| Ingestion | PDFium PDF, duckx DOCX, binary-sniffing text reader | reuse `core/agent/text_extract.py` (pypdf/zip-xml) initially; upgrade later |
| Chunking | 512 chars, whitespace words, last-space split, **no overlap** (their weakness — do 512 chars + 15% overlap) | paragraph-aware splitter already exists in `core/search/paragraph_search.py` — reuse |
| Freshness | mtime compare + QFileSystemWatcher rescan; crash-recovery re-embed queue | `watchdog` package or QFileSystemWatcher; mtime column |
| Injection | `### Context:` baked into user turn; sources[] exposed to Jinja; citation pills opening `file://` | append context block in `build_messages`; render collapsible "N sources" card in `agent_panel.add_tool_card` style |

Settings to expose: allowed extensions, chunk size, top_k (default 3), show
sources toggle, embed device. **Deliberately skip:** their global-chunk-size
wipes-everything behavior — version the DB instead.

---

## F. Local API Server — P1, M

Wrap `ModelBackend.chat_stream` in an OpenAI-compatible server addon:

- Endpoints `/v1/models`, `/v1/chat/completions`, `/v1/completions`.
- **Do better than GPT4All:** support `"stream": true` SSE (they reject it),
  accept `stop`, reject `tools` politely until agents speak OpenAI schema.
- Port default 8080, localhost-only, optional bearer key; implement as
  `ggufloader/addons/api_server/` registered like floating_chat.
- FastAPI + uvicorn added as optional extras (`pip install ggufloader[server]`).

---

## G. Model Acquisition — P2, L

Catalog-driven downloads: `models.json` catalog + HF URL import, HTTP Range
resume from `incomplete-<name>`, N retries, streaming sha256/md5 verify on a
side thread, atomic rename (`download.cpp:185-222,534-611`).
**Ours:** requests-based downloader in a service thread; verify with
`hashlib.file_digest`; resume via `Range` header; catalog can initially point
to a curated static JSON in the repo.

---

## H. Tools / Code Interpreter — P2, M

Their only tool is a sandboxed **QJSEngine** JS interpreter (no FS/net,
console capture ≤1024 chars, interruptible, errors fed back for
self-correction). **Ours:** add a restricted-Python tool to
`tool_registry.py` using `RestrictedPython`-style execution or a
`subprocess` python -c with no-network job object, output cap 8000 (match
existing tools), and mark it approval-free (safe by construction) — gives
non-workspace chats a calculator/data tool without shell exposure.

---

## I. Deliberately NOT Adopted

- **Telemetry/datalake contribution** (`network.cpp`) — privacy is a stated
  differentiator; also their TLS `VerifyNone` pattern must never be copied.
- **Quit-time-only chat saving** — our per-exchange atomic saves are safer.
- **Global chunk-size wipe on change** — version the RAG DB instead.
- **Server without auth/streaming** — we'd launch with both from day one.

---

## Suggested Sequence

| Sprint | Items |
|---|---|
| 1 | A1 holdback · A2 overflow guard (+too-long message error) · B1 GPU honesty · B3 GGUF max-context |
| 2 | C1 params dialog · C3 system prompt · D2 LLM titles · D4 date groups |
| 3 | A3 KV prefix cache · D1 schema v2 · A4 min_p/greedy |
| 4+ | E RAG (split: store → ingest → retrieval UI) · F API server · G downloads · H python tool · D3/D5 |

*Each item cites its GPT4All origin so future audits can diff behavior.*

---

# Addendum — Second-Pass Audit (new findings)

A deeper sweep of `chatviewtextprocessor.cpp`, `ChatView.qml`,
`ChatItemView.qml`, `ChatDrawer.qml`, `ModelsView/AddHFModelView.qml`,
`modellist.cpp`, `download.cpp`, `logger.cpp` surfaced significant items the
first pass missed.

## J. Message Rendering Pipeline — P0, M→L (biggest visual gap)

Their `chatviewtextprocessor.cpp` is why GPT4All answers *look* good:

| Feature | Their impl | Port sketch |
|---|---|---|
| GitHub-dialect markdown per message | `QTextDocument::insertMarkdown(MarkdownDialectGitHub \| MarkdownNoHTML)` over non-code regions (`:1066-1125`) | Our `_BubbleText` is plain-text only. Add an opt-in rich mode: split message into code-fence / prose segments; render prose via `insertMarkdown`; keep fences as styled blocks |
| Code blocks → framed card | language header row + monospace cell, themed bg (`handleCodeBlocks :906-1064`) | QTextTable with header ("python ⧉ copy") + mono body; QSS from tokens |
| Syntax highlighting, 11 languages | per-block `QSyntaxHighlighter`s keyed by fence word (`:717-767`) | start with py/js/cpp/json/bash; ship others later |
| Click header → copy raw code | `tryCopyAtPosition :802-812` | clipboard setText(original fence text) |
| Per-message "disable markdown" | right-click toggle `shouldProcessText` | context-menu checkbox storing per-message flag |
| Re-render on theme/font change | document rebuilt (`ChatTextItem.qml:96-134`) | hook our `apply_theme/apply_font_size` |

## K. Message Action Row — P0/P1

Hover-revealed per-message actions (`ChatItemView.qml:476-598`):

- **K1 Regenerate (P0,S)**: Redo button → pop last reply, re-run. Instant for
  final message; confirm-dialog ("erases following messages") when invoked on
  older ones (`chat.cpp:169`). Ours: pop `conversation_history` reply +
  re-`generate` with identical messages.
- **K2 Edit user prompt (P0,S)**: pencil pops the prompt text back into the
  composer and truncates everything after it (`popPrompt`). Same confirm.
- **K3 Copy single message (P0,S)** + **copy whole conversation** tray
  action (`chatmodel.copyToClipboard`).
- **K4 Stop button replaces Send while generating (P0,S!)** — `ChatView.qml:1316`.
  We currently have NO visible stop control for normal chat despite
  `ChatService.stop()` existing. Highest ratio-of-effort-to-value item here.
- **K5 Thumbs up/down + optional better-response editor (P2,M)**: skip their
  datalake upload; persist rating + edited alt-response in session v2 for
  local review.
- **K6 Status line vocabulary (P2,S)**: "processing…", "generating…",
  "stopped…" under each pending reply; spinning logo while busy.

## L. Composer & Input — mixed

- **L1 File attachments on prompts (P2,M)**: paperclip picker
  (.txt/.md/.rst/.xlsx); xlsx converted to markdown tables
  (`xlsxtomd.cpp`); chips above composer; content inlined into prompt
  (`prompt_attachments`).
- **L2 Links open only after generation completes + hovered-link status echo (P2,S)** — prevents clicking half-streamed URLs.
- **L3 Legacy-token validation on system prompt/template editors (P1,S)**:
  live warning when users type `<|im_start|>`-style control tokens into the
  C3 editors (`ModelSettings.qml:258-260`) — complements our artifact scrubber.

## M. Model Management specifics (upgrades earlier items)

- **M1 HF discovery API details (upgrades G)**: search endpoint
  `https://huggingface.co/api/models?filter=gguf&search=…&full=true&config=true`
  with sort=likes/downloads/lastModified & limit; download URL shape
  `https://huggingface.co/<repo>/resolve/main/<file>`; file size from HEAD
  `X-Linked-Size`; **hash for free** from `X-Linked-Etag` (= sha256, quotes
  stripped); quant auto-pick order q4_0 > q4_1 > f16 > f32
  (`modellist.cpp:2146-2336`). One request gives us verified resume-ready
  metadata — no separate hash lookup.
- **M2 Catalog schema extras (upgrades G/C1)**: entries may carry per-model
  sampling defaults + `chatTemplate` + `systemMessage`, plus app-version
  gating (`requires`/`removedIn`) and `isDefault`. If we ever ship a catalog,
  mirror this so profiles and catalog share one source.
- **M3 Embedding-model flagging (pairs E)**: detect embedding models by GGUF
  arch (nomic-bert…) and exclude them from chat-selectable lists +
  warn if sideloaded as chat (`isEmbeddingModel`, `modellist.cpp:1096-1103`).
- **M4 Clone-model feature (P2,M)**: duplicate an installed model entry into
  an editable clone (`~N` naming) with independent params/template — cheap
  multi-persona support once C1 lands.
- **M5 Fast-path model handoff (pairs A3)**: switching back to a just-used
  model acquires it from a process-global store without reload
  (`LLModelStore`, `chatllm.cpp:168-218,322-360`). Natural fit with our
  planned KV-prefix work: keep {model_path → backend} LRU of 1-2 entries.
- **M6 Model switch wipes conversation BY DESIGN** (confirm dialog,
  `chat.cpp:92-106`). Opposite of ours (we keep history). Decision point:
  keep ours, but offer a per-switch "start fresh?" checkbox.

## N. Exact auxiliary prompt strings (implementations for D2/D3)

- Chat naming (verbatim):
  `Describe the above conversation. Your entire response must be three words or less.`
  Post-process: keep ≤3 whitespace words, drop think-content
  (`NameResponseHandler`, `chatllm.cpp:1211-1232`).
- Follow-ups (verbatim):
  `Suggest three very short factual follow-up questions that have not been answered yet or cannot be found inspired by the previous conversation and excerpts.`
  Extractor regex: `\b(?:What|Where|How|Why|When|Who|Which|Whose|Whom)\b[^?]*\?`
  (`chatllm.cpp:1298-1303`); gate modes Always/LocalDocsOnly/Never; skipped
  after any tool call.
- Tool-loop cap nuance: counter resets on success — chains continue
  indefinitely while error-free (`chat.cpp:299`). Contrast our hard
  `max_steps=8` + stale-repeat suppression (ours safer; keep).

## O. Infrastructure niceties

- **O1 Two-step delete with 3s auto-dismiss (P2,S)**: trash → inline ✓/✕
  popover that times out (`ChatDrawer.qml:233-313`) instead of modal box.
- **O2 Logger with previous-run retention (P2,S)**: `log.txt` renamed to
  `log-prev.txt` on startup, mutex-guarded dual write to stderr+file
  (`logger.cpp:28-76`). Drop-in for our empty `logs/` dir.
- **O3 System tray (restore/quit) + persisted window geometry (P2,S)**.
- **O4 Check-for-updates via release JSON (P2,S)**.
- **O5 RAM-vs-model-size warning on model cards (P2,S)** (pairs B4).

## P. Where GPT4All has NOTHING — differentiation opportunities for us

Verified absent in their codebase:

1. Search/filter across saved chats · 2. Export chat to file/markdown ·
3. Edit assistant replies · 4. Delete individual messages ·
5. Streaming OpenAI-compatible server · 6. Agent filesystem/shell tools with
human approval · 7. Thinking-format breadth beyond `<think>` (no harmony,
no missing-opener recovery) · 8. Auto per-family sampling routing (their
defaults are static per catalog entry).

Items 1–2 are trivial wins for our sessions layer; 7–8 we already lead.

## Updated priority inserts

- Move **K4 (Stop button)** into Sprint 1 retroactively — trivial and critical.
- Sprint 2 additions: K1/K2/K3 action row, L3 token-validation, M3 embedding flag.
- Sprint 4 RAG unchanged; J markdown pipeline becomes its own track between
  sprints 2–3 given its visibility payoff.


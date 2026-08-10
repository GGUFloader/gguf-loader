"""Unit tests for the chunked-LLM paragraph search (no RAG)."""

from pathlib import Path

import pytest

from ggufloader.core.agent.tool_registry import ToolRegistry
from ggufloader.core.search.paragraph_search import Hit, ParagraphSearcher, extract_keywords, read_text_file
from ggufloader.core.search.planner import SearchPlanner

MARKER = "@@TARGET@@"


class FakeGenerate:
    """Pretends to be a model: quotes the target passage when the chunk
    contains the marker, otherwise answers NO."""

    def __init__(self, marker: str = MARKER, quote: str = None) -> None:
        self.marker = marker
        self.quote = quote or f"The target passage: {marker}"
        self.calls: list[str] = []

    def __call__(self, prompt: str, **kwargs):
        self.calls.append(prompt)
        if self.marker in prompt:
            return self.quote
        return "NO"


def para_text(count: int, per: int = 3) -> str:
    """Build *count* paragraphs, each ~64 chars, blank-line separated."""
    paras = []
    for i in range(count):
        paras.append(f"Para {i:02d} " * per)
    return "\n\n".join(paras)


# ----------------------------------------------------------------------
# Chunking
# ----------------------------------------------------------------------
def test_split_respects_budget_and_overlap():
    searcher = ParagraphSearcher(lambda prompt, **kw: "NO", chunk_tokens=50, overlap_tokens=20)
    chunks = searcher.split(para_text(30, per=8))
    # ~64 chars/paragraph, 200-char budget -> 3 paragraphs per chunk.
    assert len(chunks) >= 8
    # The second chunk re-includes the first chunk's tail paragraph.
    assert chunks[0].endswith("Para 02")
    assert chunks[1].startswith("Para 02")
    assert chunks[1].endswith("Para 04")


def test_split_normalizes_crlf():
    searcher = ParagraphSearcher(lambda prompt, **kw: "NO")
    chunks = searcher.split("one\r\n\r\ntwo\r\n\r\nthree")
    assert len(chunks) == 1
    assert "one" in chunks[0] and "two" in chunks[0]


def test_split_oversized_paragraph_by_words():
    searcher = ParagraphSearcher(lambda prompt, **kw: "NO", chunk_tokens=50)  # 200-char budget
    text = ("word " * 60).strip()  # ~360 chars, no blank lines
    chunks = searcher.split(text)
    assert len(chunks) >= 2
    assert all(len(c) <= 200 for c in chunks)


def test_split_empty_text():
    searcher = ParagraphSearcher(lambda prompt, **kw: "NO")
    assert searcher.split("") == []
    assert searcher.split("   \n\n  ") == []


# ----------------------------------------------------------------------
# Search
# ----------------------------------------------------------------------
def test_search_finds_passage():
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50)
    text = f"Para 00 {MARKER} here.\n\n" + para_text(20, 2)
    hits = searcher.search("the target", text)
    assert len(hits) == 1
    assert fake.quote in hits[0].text
    assert hits[0].chunk_index == 0


def test_search_no_hits():
    fake = FakeGenerate()  # never finds the marker
    searcher = ParagraphSearcher(fake)
    hits = searcher.search("the target", para_text(10))
    assert hits == []


def test_search_accepts_no_variants():
    class NoVariants:
        def __call__(self, prompt, **kwargs):
            return "No."

    searcher = ParagraphSearcher(NoVariants())
    assert searcher.search("anything", para_text(3)) == []

    class NoPassage:
        def __call__(self, prompt, **kwargs):
            return "No passage found in this section."

    searcher = ParagraphSearcher(NoPassage())
    assert searcher.search("anything", para_text(3)) == []


def test_search_strips_surrounding_quotes():
    class Quoted:
        def __call__(self, prompt, **kwargs):
            return f'"exactly {MARKER} verbatim"'

    searcher = ParagraphSearcher(Quoted())
    hits = searcher.search("q", f"text {MARKER}")
    assert hits[0].text == f"exactly {MARKER} verbatim"


def test_search_dedupes_overlapping_chunks():
    # The marker sits at a chunk boundary, so it lands in two chunks and
    # the model quotes it twice; dedup must collapse to one hit.
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50, overlap_tokens=1000)
    text = para_text(6) + f"\n\n{MARKER} mid\n\n" + para_text(6)
    hits = searcher.search("q", text)
    assert len(hits) == 1


def test_search_dedup_keeps_longest_quote():
    class Growing:
        def __init__(self):
            self.n = 0

        def __call__(self, prompt, **kwargs):
            self.n += 1
            if self.n == 1:
                return "short quote"
            if self.n == 2:
                return "a much longer quote that contains the short quote"
            return "NO"

    searcher = ParagraphSearcher(Growing(), chunk_tokens=50)
    hits = searcher.search("q", para_text(20))
    assert len(hits) == 1
    assert "much longer" in hits[0].text


def test_search_progress_and_total():
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50)  # ~10 chunks
    progress: list[tuple[int, int]] = []
    searcher.search("q", para_text(30), on_progress=lambda d, t: progress.append((d, t)))
    assert progress
    total = progress[0][1]
    # done counts up monotonically and ends at the total chunk count.
    assert [d for d, _ in progress] == list(range(1, total + 1))
    assert progress[-1] == (total, total)
    assert total == len(searcher.split(para_text(30)))


def test_search_cancel_stops_between_chunks():
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50)
    scanned = 0
    progress: list[tuple[int, int]] = []

    def should_cancel() -> bool:
        return scanned >= 1

    def on_progress(done, total):
        nonlocal scanned
        scanned = done
        progress.append((done, total))

    hits = searcher.search("q", para_text(30), on_progress=on_progress,
                           should_cancel=should_cancel)
    assert scanned == 1
    assert progress[-1][0] == 1
    assert len(hits) <= 1


def test_search_max_chunks():
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50, max_chunks=2)
    progress: list[tuple[int, int]] = []
    searcher.search("q", para_text(30), on_progress=lambda d, t: progress.append((d, t)))
    assert progress[-1] == (2, 2)


def test_hit_to_dict():
    assert Hit("text", 3).to_dict() == {"text": "text", "chunk_index": 3, "source": ""}
    assert Hit("text", 3, "a.py").to_dict() == {"text": "text", "chunk_index": 3, "source": "a.py"}


# ----------------------------------------------------------------------
# Folder search
# ----------------------------------------------------------------------
def make_workspace(root) -> None:
    (root / "readme.md").write_text("Docs paragraph about usage.\n\n" * 3, encoding="utf-8")
    (root / "main.py").write_text("Code paragraph.\n\n" * 3, encoding="utf-8")
    (root / "data.bin").write_bytes(b"\x00\x01\x02 binary content")
    (root / "nested").mkdir()
    (root / "nested" / "notes.txt").write_text("Notes paragraph.\n\n" * 3, encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config.md").write_text("should be skipped", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "c.py").write_text("should be skipped", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "pkg.js").write_text("should be skipped", encoding="utf-8")


def test_glob_files_finds_matching_skips_dirs_and_binary(tmp_path):
    make_workspace(tmp_path)
    searcher = ParagraphSearcher(lambda prompt, **kw: "NO")
    paths = searcher.glob_files(tmp_path)
    names = {p.name for p in paths}
    assert {"readme.md", "main.py", "notes.txt"} <= names
    assert "data.bin" not in names
    assert not any(".git" in p.parts or "__pycache__" in p.parts or "node_modules" in p.parts for p in paths)


def test_glob_files_patterns(tmp_path):
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "b.py").write_text("y", encoding="utf-8")
    searcher = ParagraphSearcher(lambda prompt, **kw: "NO")
    assert [p.name for p in searcher.glob_files(tmp_path, "*.md")] == ["a.md"]
    assert [p.name for p in searcher.glob_files(tmp_path, "*.py *.md")] == ["a.md", "b.py"]


def test_read_text_file_guards(tmp_path):
    bin_file = tmp_path / "b.bin"
    bin_file.write_bytes(b"\x00\x01")
    assert read_text_file(bin_file) == ""
    big = tmp_path / "big.txt"
    big.write_text("x" * 5000, encoding="utf-8")
    assert read_text_file(big, max_bytes=1000) == ""
    bom = tmp_path / "bom.txt"
    bom.write_bytes(b"\xef\xbb\xbfhello")
    assert read_text_file(bom) == "hello"


def test_search_folder_tags_source_and_progress(tmp_path):
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50)
    (tmp_path / "a.md").write_text("Alpha paragraph.\n\n" * 4, encoding="utf-8")
    (tmp_path / "b.md").write_text(
        f"Beta intro.\n\nThe GPU paragraph {MARKER} lives here.\n\n" * 2, encoding="utf-8"
    )
    progress: list[tuple[int, int]] = []
    hits = searcher.search_folder(
        "gpu", tmp_path, patterns="*.md",
        on_progress=lambda d, t: progress.append((d, t)),
    )
    assert hits, "expected a hit from b.md"
    assert all(h.source.endswith("b.md") for h in hits)
    assert progress
    assert progress[-1][1] == progress[-1][0]  # finished all chunks


def test_search_folder_cross_file_dedup(tmp_path):
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50)
    passage = f"The shared GPU paragraph {MARKER}."
    (tmp_path / "one.md").write_text(f"{passage}\n\n" + "x.\n\n" * 4, encoding="utf-8")
    (tmp_path / "two.md").write_text(f"{passage}\n\n" + "y.\n\n" * 4, encoding="utf-8")
    hits = searcher.search_folder("gpu", tmp_path, patterns="*.md")
    assert len(hits) == 1  # identical quote found in both files merges to one


def test_search_folder_reports_files_and_per_file_progress(tmp_path):
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50, overlap_tokens=5)
    (tmp_path / "a.md").write_text((f"GPU a {MARKER}.\n\n" * 12), encoding="utf-8")
    (tmp_path / "b.md").write_text((f"GPU b content.\n\n" * 12), encoding="utf-8")
    started: list[tuple[str, int, int]] = []
    progress: list[tuple[int, int]] = []
    searcher.search_folder(
        "gpu", tmp_path, patterns="*.md",
        on_file_started=lambda p, i, n: started.append((Path(p).name, i, n)),
        on_progress=lambda d, t: progress.append((d, t)),
    )
    assert [s[0] for s in started] == ["a.md", "b.md"]
    assert [s[1:] for s in started] == [(1, 2), (2, 2)]
    # Per-file progress: each file's counts restart from 1.
    first_file_chunks = len(searcher.split(f"GPU a {MARKER}.\n\n" * 12))
    assert progress[0] == (1, first_file_chunks)
    last_file_chunks = len(searcher.split("GPU b content.\n\n" * 12))
    assert progress[-1] == (last_file_chunks, last_file_chunks)  # b.md restarts


def test_search_folder_max_files(tmp_path):
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50)
    for i in range(3):
        (tmp_path / f"f{i}.md").write_text("para.\n\n" * 3, encoding="utf-8")
    progress: list[tuple[int, int]] = []
    searcher.search_folder("q", tmp_path, patterns="*.md", max_files=1,
                           on_progress=lambda d, t: progress.append((d, t)))
    assert progress[-1][1] == 1  # only one file scanned


# ----------------------------------------------------------------------
# Light (keyword-prefiltered) folder search
# ----------------------------------------------------------------------
def test_extract_keywords():
    assert extract_keywords("find the passage about GPU offloading") == ["gpu", "offloading"]
    assert extract_keywords("q") == []          # too short -> fall back to exhaustive
    assert extract_keywords("git") == ["git"]
    assert extract_keywords("gpu gpu GPU") == ["gpu"]  # deduped
    assert len(extract_keywords("one two three four five six", max_keywords=3)) == 3
    kws = extract_keywords("\u067e\u0627\u0631\u0627\u06af\u0631\u0627\u0641 \u062f\u0631\u0628\u0627\u0631\u0647 \u067e\u0631\u062f\u0627\u0632\u0646\u062f\u0647 \u06af\u0631\u0627\u0641\u06cc\u06a9\u06cc")  # Persian
    assert kws and all(not t.isascii() for t in kws)


class PlanFake:
    """Returns a JSON plan; records whether the plan prompt was seen."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls = 0
        self.prompts: list[str] = []

    def __call__(self, prompt: str, **kwargs):
        self.calls += 1
        self.prompts.append(prompt)
        return self.answer


def test_planner_one_shot_without_tools():
    fake = PlanFake(
        '{"reasoning": "ok", "tool_calls": [], "done": true, '
        '"query": "GPU offloading and VRAM usage", "keywords": ["GPU", "vram"], '
        '"files": ["notes.txt"], "steps": ["1. scan", "2. quote"]}'
    )
    plan = SearchPlanner(fake).plan("explain the whole gpu thing")
    assert plan.query == "GPU offloading and VRAM usage"
    assert plan.keywords == ["gpu", "vram"]  # lowercased
    assert plan.files == ["notes.txt"]
    assert plan.steps == ["1. scan", "2. quote"]
    assert "search planner" in fake.prompts[0]


def test_planner_calls_tools_then_plans(tmp_path):
    calls: list[str] = []

    def fake(prompt: str, **kwargs):
        calls.append(prompt)
        if len(calls) >= 2:  # second round: the tool result was fed back
            return ('{"reasoning": "got the list", "tool_calls": [], "done": true, '
                    '"query": "gpu offload", "keywords": ["gpu"], '
                    '"files": ["notes.txt"], "steps": ["1. scan notes.txt"]}')
        return ('{"reasoning": "inspect", "tool_calls": '
                '[{"tool": "list_directory", "parameters": {"path": "."}}]}')

    tools = ToolRegistry(tmp_path)
    plan = SearchPlanner(fake, tools=tools).plan("gpu offload")
    assert plan.files == ["notes.txt"]
    assert len(calls) == 2
    assert "list_directory \u2192" in calls[1]  # the tool result reached the model


def test_planner_repairs_bad_json():
    calls: list[str] = []

    def fake(prompt: str, **kwargs):
        calls.append(prompt)
        if "not valid JSON" in prompt:
            return ('{"reasoning": "fixed", "tool_calls": [], "done": true, '
                    '"query": "gpu", "keywords": ["gpu"], "files": [], "steps": []}')
        return "this is not json at all"

    plan = SearchPlanner(fake).plan("gpu")
    assert plan.query == "gpu"
    assert len(calls) == 2  # bad reply, then repair reply


def test_planner_falls_back_on_garbage():
    plan = SearchPlanner(PlanFake("I cannot help with that.")).plan("gpu offloading")
    assert plan.query == "gpu offloading"
    assert plan.keywords == ["gpu", "offloading"]


def test_tool_registry_only_subset(tmp_path):
    reg = ToolRegistry(tmp_path, only=["list_directory"])
    assert reg.names() == ["list_directory"]
    result = reg.execute("read_file", {"path": "x.txt"})
    assert result["status"] == "error" and "Unknown tool" in result["error"]


def test_planner_refuses_write_tools(tmp_path):
    calls: list[str] = []

    def fake(prompt: str, **kwargs):
        calls.append(prompt)
        if len(calls) >= 2:
            return ('{"reasoning": "ok", "tool_calls": [], "done": true, '
                    '"query": "q", "keywords": [], "files": [], "steps": []}')
        return ('{"reasoning": "write", "tool_calls": '
                '[{"tool": "write_file", "parameters": '
                '{"path": "evil.txt", "content": "x"}}]}')

    tools = ToolRegistry(tmp_path)  # full registry - the planner must still refuse
    plan = SearchPlanner(fake, tools=tools).plan("q")
    assert plan.query == "q"
    assert not (tmp_path / "evil.txt").exists(), "write_file must not execute"
    assert "not available in read-only planning" in calls[1]


def test_planner_trace_records_read_only_calls(tmp_path):
    calls: list[str] = []

    def fake(prompt: str, **kwargs):
        calls.append(prompt)
        if len(calls) == 3:
            return ('{"reasoning": "done", "tool_calls": [], "done": true, '
                    '"query": "q", "keywords": [], "files": [], "steps": []}')
        if len(calls) == 2:
            return ('{"reasoning": "read it", "tool_calls": '
                    '[{"tool": "read_file", "parameters": {"path": "notes.txt"}}]}')
        return ('{"reasoning": "list first", "tool_calls": '
                '[{"tool": "list_directory", "parameters": {"path": "."}}]}')

    tools = ToolRegistry(tmp_path)
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    plan = SearchPlanner(fake, tools=tools).plan("q")
    assert plan.trace == [
        {"tool": "list_directory", "target": "."},
        {"tool": "read_file", "target": "notes.txt"},
    ]
    assert plan.to_dict()["trace"] == plan.trace


def test_planner_on_tool_call_streams(tmp_path):
    calls: list[str] = []

    def fake(prompt: str, **kwargs):
        calls.append(prompt)
        if len(calls) >= 3:
            return ('{"reasoning": "done", "tool_calls": [], "done": true, '
                    '"query": "q", "keywords": [], "files": [], "steps": []}')
        if len(calls) == 2:
            return ('{"reasoning": "read", "tool_calls": '
                    '[{"tool": "read_file", "parameters": {"path": "notes.txt"}}]}')
        return ('{"reasoning": "list", "tool_calls": '
                '[{"tool": "list_directory", "parameters": {"path": "."}}]}')

    tools = ToolRegistry(tmp_path)
    (tmp_path / "notes.txt").write_text("hi", encoding="utf-8")
    streamed: list[dict] = []
    SearchPlanner(fake, tools=tools).plan("q", on_tool_call=streamed.append)
    assert streamed == [
        {"tool": "list_directory", "target": "."},
        {"tool": "read_file", "target": "notes.txt"},
    ]


def test_planner_prompt_only_advertises_read_only(tmp_path):
    captured: dict = {}

    def fake(prompt: str, **kwargs):
        captured["prompt"] = prompt
        return ('{"reasoning": "done", "tool_calls": [], "done": true, '
                '"query": "q", "keywords": [], "files": [], "steps": []}')

    SearchPlanner(fake, tools=ToolRegistry(tmp_path)).plan("q")
    prompt = captured["prompt"]
    assert "list_directory" in prompt and "read_file" in prompt and "search_files" in prompt
    assert "write_file" not in prompt and "edit_file" not in prompt
    assert "run_command" not in prompt and "git" not in prompt


def test_planner_step_budget_falls_back():
    def fake(prompt: str, **kwargs):
        return ('{"reasoning": "more", "tool_calls": '
                '[{"tool": "list_directory", "parameters": {"path": "."}}]}')

    plan = SearchPlanner(fake, max_steps=2).plan("gpu offloading")  # no tools -> stuck
    assert plan.query == "gpu offloading"  # fallback keeps the raw prompt
    assert plan.keywords == ["gpu", "offloading"]


def test_search_folder_uses_provided_keywords(tmp_path):
    # The planner keyword "vram" finds the file even though the crude
    # extraction from "graphics memory" would never match it.
    fake = CountingFake(keyword="vram")
    searcher = ParagraphSearcher(fake, chunk_tokens=50)
    (tmp_path / "a.md").write_text("VRAM holds layer weights.\n\n" * 6, encoding="utf-8")
    hits = searcher.search_folder(
        "graphics memory", tmp_path, patterns="*.md", keywords=["vram"]
    )
    assert fake.calls >= 1
    assert hits and hits[0].source.endswith("a.md")


def test_search_folder_target_files(tmp_path):
    fake = FakeGenerate()
    searcher = ParagraphSearcher(fake, chunk_tokens=50)
    (tmp_path / "a.md").write_text(f"GPU a {MARKER}.\n\n" * 4, encoding="utf-8")
    (tmp_path / "b.md").write_text(f"GPU b {MARKER}.\n\n" * 4, encoding="utf-8")
    hits = searcher.search_folder("gpu", tmp_path, patterns="*.md", files=["a.md", "../evil.md"])
    assert hits and all(h.source.endswith("a.md") for h in hits)
    assert not any(h.source.endswith("b.md") for h in hits)  # not in the plan


def test_search_folder_falls_back_when_plan_keywords_miss(tmp_path):
    fake = CountingFake()
    searcher = ParagraphSearcher(fake, chunk_tokens=50)
    (tmp_path / "a.md").write_text("GPU moves layers to VRAM.\n\n" * 6, encoding="utf-8")
    hits = searcher.search_folder(
        "gpu offloading", tmp_path, patterns="*.md", keywords=["zzz", "qqq"]
    )
    assert fake.calls >= 1  # planner keywords missed -> query's own words used
    assert hits


class CountingFake:
    """Counts model calls; quotes passages containing a keyword or marker."""

    def __init__(self, keyword: str = "gpu") -> None:
        self.keyword = keyword
        self.calls = 0
        self.seen: list[str] = []

    def __call__(self, prompt: str, **kwargs):
        self.calls += 1
        self.seen.append(prompt)
        if self.keyword in prompt.lower() or MARKER in prompt:
            return f"The {self.keyword} paragraph: {MARKER}"
        return "NO"


def test_search_folder_light_skips_keywordless_files(tmp_path):
    fake = CountingFake()
    searcher = ParagraphSearcher(fake, chunk_tokens=50)
    (tmp_path / "a.md").write_text("GPU moves layers to VRAM.\n\n" * 6, encoding="utf-8")
    (tmp_path / "b.md").write_text("Nothing relevant here.\n\n" * 12, encoding="utf-8")
    hits = searcher.search_folder("gpu offloading", tmp_path, patterns="*.md")
    assert fake.calls == 1  # only a.md's chunk(s) scanned; b.md never reaches the model
    assert hits and all(h.source.endswith("a.md") for h in hits)


def test_search_folder_light_scans_only_keyword_chunks(tmp_path):
    fake = CountingFake()
    searcher = ParagraphSearcher(fake, chunk_tokens=50, overlap_tokens=5)
    paras = [f"plain para {i:02d} here\n\n" for i in range(30)]
    paras[15] = "the GPU keyword lives in this paragraph\n\n"
    (tmp_path / "a.md").write_text("".join(paras), encoding="utf-8")
    searcher.search_folder("gpu", tmp_path, patterns="*.md")
    assert fake.calls == 1, f"expected 1 call, got {fake.calls}"
    assert "GPU" in fake.seen[0]


def test_search_folder_light_scans_small_files_fully(tmp_path):
    fake = CountingFake()
    searcher = ParagraphSearcher(fake, chunk_tokens=50, overlap_tokens=5)
    text = "GPU in chunk zero.\n\n" + ("plain filler\n\n" * 20)
    (tmp_path / "a.md").write_text(text, encoding="utf-8")
    searcher.search_folder("gpu", tmp_path, patterns="*.md")
    assert fake.calls == 2  # 2 chunks, file is small -> both scanned


def test_search_folder_exhaustive_scans_every_chunk(tmp_path):
    fake = CountingFake()
    searcher = ParagraphSearcher(fake, chunk_tokens=50, overlap_tokens=5)
    paras = [f"plain para {i:02d} here\n\n" for i in range(30)]
    (tmp_path / "a.md").write_text("".join(paras), encoding="utf-8")
    expected = len(searcher.split("".join(paras)))
    searcher.search_folder("gpu", tmp_path, patterns="*.md", exhaustive=True)
    assert fake.calls == expected  # every chunk scanned despite no keyword match

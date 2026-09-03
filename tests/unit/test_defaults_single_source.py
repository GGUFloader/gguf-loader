"""Single-source invariants: one llama-cpp owner, one version, one probe."""


def test_single_llama_owner_and_probe():
    import subprocess
    out = subprocess.run(
        ["grep", "-rn", "from llama_cpp", "ggufloader", "--include=*.py"],
        capture_output=True, text=True,
    ).stdout
    files = {l.split(":")[0] for l in out.strip().splitlines() if l.strip()}
    assert files <= {
        "ggufloader/core/llm/model_backend.py",
        "ggufloader/core/system_probe.py",
    }, files


def test_version_single_source():
    import tomllib
    from ggufloader import __version__
    with open("pyproject.toml", "rb") as f:
        py = tomllib.load(f)["project"]["version"]
    assert __version__ == py
    assert "2.2.0" not in open("ggufloader/main.py").read()

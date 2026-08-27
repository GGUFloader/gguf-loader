"""CRITICAL Gate: Data Integrity"""
import json
import pytest
from ggufloader.core.agent.agent_engine import extract_json, _balanced_objects
from ggufloader.core.agent.tool_registry import ToolRegistry


class TestJsonProtocol:
    def test_valid_json(self):
        data = {"tool_calls": []}
        assert extract_json(json.dumps(data)) == data

    def test_empty_input(self):
        assert extract_json("") is None
        assert extract_json(None) is None

    def test_balanced_objects(self):
        assert len(list(_balanced_objects("{} and {}"))) == 2
        assert len(list(_balanced_objects("no braces"))) == 0


class TestToolIntegrity:
    def test_write_read_roundtrip(self, tmp_path):
        reg = ToolRegistry(tmp_path)
        content = "Hello World"
        reg.execute("write_file", {"path": "t.txt", "content": content})
        r = reg.execute("read_file", {"path": "t.txt"})
        assert r["status"] == "success"
        assert r["result"] == content

    def test_concurrent_writes(self, tmp_path):
        reg = ToolRegistry(tmp_path)
        for i in range(10):
            reg.execute("write_file", {"path": f"f{i}.txt", "content": f"c{i}"})
        for i in range(10):
            r = reg.execute("read_file", {"path": f"f{i}.txt"})
            assert r["result"] == f"c{i}"

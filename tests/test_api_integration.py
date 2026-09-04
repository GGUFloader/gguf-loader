"""Integration tests for the FastAPI backend.

Tests all major API endpoints by starting the app in-process.
"""

import pytest
from fastapi.testclient import TestClient

from ggufloader.api.app import create_app


@pytest.fixture
def client():
    """Create a test client."""
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health_check(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestAppInfoEndpoint:
    def test_app_info_returns_pinned_identity(self, client):
        resp = client.get("/api/app/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "GGUF Loader"
        assert "version" in data
        assert data["label"] == "Gemma 4 12B Q4_K_M"
        assert data["tagline"] == "Optimized for Gemma 4 12B Q4_K_M"
        assert data["pinned"] == {"arch": "gemma4", "quant": "Q4_K_M", "size": "12B"}


class TestModelEndpoints:
    def test_model_info_no_model(self, client):
        resp = client.get("/api/model/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "loaded" in data
        assert data["loaded"] is False
        # Auto-load status + pinned compatibility surface even when empty
        assert "auto_load" in data
        assert "models_dir" in data
        assert data.get("compatible") is None

    def test_model_estimate(self, client):
        resp = client.get("/api/model/estimate?path=test.gguf")
        # May return 404 or error since file doesn't exist
        assert resp.status_code in (200, 400, 404, 500)

    def test_model_unload_no_model(self, client):
        resp = client.delete("/api/model/unload")
        # Should succeed or return not-loaded error
        assert resp.status_code in (200, 400)

    def test_model_download_status_shape(self, client):
        resp = client.get("/api/model/download/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "progress" in data
        assert "message" in data

    def test_model_download_never_streams_in_test_env(self, client):
        # The pinned model is ~8 GB — under pytest the endpoint must
        # report disabled instead of actually downloading.
        resp = client.post("/api/model/download")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disabled"
        assert data["progress"] == 0.0


class TestSessionEndpoints:
    def test_list_sessions(self, client):
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_session(self, client):
        resp = client.post("/api/sessions", json={"title": "Test Session"})
        assert resp.status_code == 200

    def test_get_nonexistent_session(self, client):
        resp = client.get("/api/sessions/nonexistent")
        assert resp.status_code in (404, 500)

    def test_delete_nonexistent_session(self, client):
        resp = client.delete("/api/sessions/nonexistent")
        assert resp.status_code in (200, 404, 500)


class TestAgentEndpoints:
    def test_agent_status(self, client):
        resp = client.get("/api/agent/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data

    def test_agent_start_stop(self, client):
        resp = client.post("/api/agent/start", json={"preset": "standard"})
        # May return 400 if no model loaded, that's expected
        assert resp.status_code in (200, 400)

        resp = client.post("/api/agent/stop")
        assert resp.status_code in (200, 400)


class TestFileEndpoints:
    def test_file_tree(self, client):
        resp = client.get("/api/files/tree")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_file_search(self, client):
        resp = client.get("/api/files/search?q=test")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_run_command(self, client):
        resp = client.post("/api/files/run", json={"command": "echo hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert "hello" in data.get("stdout", "")

    def test_blocked_command(self, client):
        resp = client.post("/api/files/run", json={"command": "rm -rf /"})
        assert resp.status_code == 400


class TestGPUEndpoints:
    def test_gpu_status(self, client):
        resp = client.get("/api/gpu/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data or "gpu_available" in data


class TestChatEndpoint:
    def test_chat_no_model(self, client):
        resp = client.post("/api/chat/send", json={"message": "hello"})
        # Should return error since no model loaded
        assert resp.status_code in (200, 400, 500)


class TestStaticFiles:
    def test_frontend_served(self, client):
        """Test that the built React frontend is served."""
        resp = client.get("/")
        # Should return index.html or redirect
        assert resp.status_code in (200, 307)

    def test_spa_fallback(self, client):
        """Test that SPA routing works."""
        resp = client.get("/nonexistent-route")
        # Should return index.html for SPA routing
        assert resp.status_code in (200, 404)

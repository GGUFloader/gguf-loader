from ggufloader.core.agent.model_profiles import get_profile
from ggufloader.services.agent_service import AgentService


class _FakeBackend:
    model_path = "gemma-4-12b-q4km.gguf"
    n_ctx = 8192
    n_ctx_train = 8192

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def chat_stream(self, messages, **kwargs):
        yield ""


def test_create_engine_uses_model_profile():
    from PySide6.QtCore import QCoreApplication
    import sys
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    svc = AgentService()
    backend = _FakeBackend()
    eng = svc.create_engine(backend, "/tmp/ws")
    profile = get_profile(backend.model_path, n_ctx_train=backend.n_ctx_train)
    assert eng.max_tokens == profile.max_tokens
    assert eng.max_steps == profile.max_steps
    assert eng.json_retries >= 2
    assert eng._context_budget.total_budget == 8192
    assert eng._context_budget._tokenizer is not None
    assert eng._context_budget._tokenizer("hello world") == backend.count_tokens("hello world")
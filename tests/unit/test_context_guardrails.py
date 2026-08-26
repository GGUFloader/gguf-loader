"""Context guardrails + template-artifact sanitization."""

from ggufloader.core.llm.model_backend import ModelBackend
from ggufloader.core.llm.prompt_builder import PromptBuilder, _has_template_artifacts


def test_artifact_detector():
    assert _has_template_artifacts("<<SYS>> junk [INST] x [/INST]")
    assert _has_template_artifacts("<|im_start|>user")
    assert not _has_template_artifacts("A perfectly clean reply with 454,708 numbers.")


def test_build_messages_drops_polluted_history():
    pb = PromptBuilder()
    history = [
        {"role": "assistant", "content": "<<SYS>>[INST] soup [/INST] >> garbage"},
        {"role": "assistant", "content": "clean answer"},
    ]
    msgs = pb.build_messages(history, "next question")
    contents = [m["content"] for m in msgs]
    assert "clean answer" in contents
    assert not any("SYS" in c for c in contents)


class FakeLlama:
    def n_ctx_train(self):
        return 8192

    def create_chat_completion(self, **k):  # pragma: no cover
        return iter([])


def test_n_ctx_train_exposed():
    b = ModelBackend("fake.gguf")
    assert b.n_ctx_train is None          # nothing loaded
    b._llama = FakeLlama()
    assert b.n_ctx_train == 8192

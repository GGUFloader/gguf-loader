from ggufloader.core.llm.model_backend import ModelBackend


def test_model_backend_accepts_tuning_params():
    backend = ModelBackend(
        model_path="dummy.gguf",
        n_ctx=8192,
        n_batch=512,
        n_threads=8,
        n_keep=512,
        flash_attn=True,
    )
    assert backend._n_ctx == 8192
    assert backend._n_batch == 512
    assert backend._n_threads == 8
    assert backend._n_keep == 512
    assert backend._flash_attn is True


def test_model_backend_defaults_are_safe_for_8gb_vram():
    backend = ModelBackend(model_path="dummy.gguf")
    assert backend._n_ctx == 8192
    assert backend._n_batch in (256, 512)
    assert backend._n_keep >= 128
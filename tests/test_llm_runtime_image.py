from __future__ import annotations

from typing import Any, Dict


def test_llm_runtime_forwards_image_to_client() -> None:
    from core.service.runtime import IstinaRuntime

    captured: Dict[str, Any] = {}

    class FakeClient:
        def chat(self, prompt: str, **kwargs: Any) -> str:
            captured["prompt"] = prompt
            captured["kwargs"] = kwargs
            return "done"

    runtime = IstinaRuntime()
    runtime._llm_client = FakeClient()
    # _llm_runtime is now lazily initialized; provide a fake for the readiness check.
    runtime._llm_runtime = type("obj", (object,), {"ready": True})()

    result = runtime.execute(
        "llm.chat",
        {
            "prompt": "describe",
            "image": "AAAABBBB",
            "temperature": 0.2,
            "max_tokens": 32,
        },
    )

    assert result["status"] == "success"
    assert result["output"] == "done"
    assert captured["prompt"] == "describe"
    assert captured["kwargs"]["image"] == "AAAABBBB"
    assert captured["kwargs"]["temperature"] == 0.2
    assert captured["kwargs"]["max_tokens"] == 32

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict


def test_llama_runtime_builds_mmproj_argument_from_llm_config() -> None:
    from core.capability.llm.runtime import LlamaServerRuntime

    runtime = LlamaServerRuntime(
        {
            "llm": {
                "model_path": "models/LLM/Qwen3.5-4B-UD-Q4_K_XL.gguf",
                "mmproj_path": "models/LLM/mmproj-F16.gguf",
                "parallel": 2,
                "context_size": 2048,
            }
        }
    )
    args = runtime._build_args(
        Path("llama-server.exe"),
        "models/LLM/Qwen3.5-4B-UD-Q4_K_XL.gguf",
        runtime._get_llm_config(),
        force_cpu=False,
    )

    assert "--mmproj" in args
    mmproj_idx = args.index("--mmproj")
    assert args[mmproj_idx + 1].endswith("mmproj-F16.gguf")
    assert "-np" in args
    assert args[args.index("-np") + 1] == "2"


def test_llm_client_embeds_image_as_data_uri(monkeypatch) -> None:
    from core.capability.llm.client import LlmClient

    captured: Dict[str, Any] = {}

    def fake_post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        captured["path"] = path
        captured["payload"] = payload
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(LlmClient, "_post", fake_post)

    client = LlmClient()
    image_b64 = base64.b64encode(b"fake-image").decode("ascii")
    result = client.chat("look", image=image_b64)

    assert result == "ok"
    assert captured["path"] == "/chat/completions"
    content = captured["payload"]["messages"][-1]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")

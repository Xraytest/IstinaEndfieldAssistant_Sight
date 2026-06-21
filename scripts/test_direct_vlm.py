"""Cherryin.ai API 直连 — 绕过本地网关直接调用大模型"""

import requests, base64, json, time, sys, os, subprocess, re
from typing import Optional, Dict, Any

API_KEY = "sk-SHYG0HNKhAEPXbEHOdlLcggKXYlyEGJyolvGjh0T2r5FQOst"
BASE_URL = "https://open.cherryin.ai"

SYSTEM_PROMPT = """你是《明日方舟：终末地》精确UI分析器。
分析游戏截图中的所有UI元素，逐一列出每个可见的按钮和交互元素。
输出严格JSON格式，不要额外文字。"""


def call_vlm_direct(
    image_base64: str,
    instruction: str,
    model_id: str = "qwen/qwen3.6-plus",
    system_prompt: str = SYSTEM_PROMPT,
    timeout: int = 120,
) -> Optional[Dict[str, Any]]:
    """直接调用 cherryin.ai 的 chat/completions API（多模态）"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": instruction},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}", "detail": "high"}},
        ],
    })
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model_id, "messages": messages, "max_tokens": 4096, "temperature": 0.1}
    try:
        resp = requests.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:300]}
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        m = re.search(r"\{[\s\S]*\}", content)
        if m:
            return json.loads(m.group())
        return {"_raw": content[:500]}
    except requests.Timeout:
        return {"error": f"timeout after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # 测试
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ADB = [os.path.join(PROJECT_ROOT, "3rd-party", "adb", "adb.exe"), "-s", "localhost:16512"]
    r = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
    if r.returncode != 0 or len(r.stdout) < 1000:
        print("截图失败")
        sys.exit(1)
    b64 = base64.b64encode(r.stdout).decode("utf-8")
    print(f"截图大小: {len(r.stdout)} bytes")

    models_to_test = [
        "qwen/qwen3.6-plus",
        "qwen/qwen3.5-397b-a17b",
        "qwen/qwen3.5-35b-a3b",
        "qwen/qwen3-vl-plus",
    ]
    for mid in models_to_test:
        print(f"\n--- {mid} ---")
        t0 = time.time()
        result = call_vlm_direct(b64, "用一句话描述这个画面。JSON:{\"page\":\"\"}", mid, timeout=60)
        dt = time.time() - t0
        if "error" in result:
            print(f"  ERROR({dt:.1f}s): {result['error']}")
        else:
            print(f"  ({dt:.1f}s): {json.dumps(result, ensure_ascii=False)[:200]}")

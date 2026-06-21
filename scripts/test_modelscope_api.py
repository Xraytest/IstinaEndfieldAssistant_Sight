#!/usr/bin/env python3
"""测试ModelScope API连接"""
import sys
import time
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()

from openai import OpenAI

client = OpenAI(
    base_url='https://ms-ens-6d80e112-9e63.api-inference.modelscope.cn/v1',
    api_key='ms-4a16f9dc-5d45-48d7-874d-2f5a7f25bf2d'
)

print("正在测试ModelScope API...")
start = time.time()

try:
    resp = client.chat.completions.create(
        model='AtomicChat/gemma-4-E2B-it-assistant-GGUF',
        messages=[
            {'role': 'system', 'content': '你是一个助手'},
            {'role': 'user', 'content': '你好'}
        ],
        max_tokens=50,
        timeout=30
    )
    print("✅ API连接成功")
    print(f"响应: {resp.choices[0].message.content[:100]}")
    print(f"耗时: {time.time() - start:.1f}秒")
except Exception as e:
    print("❌ API连接失败")
    print(f"错误: {e}")
    print(f"耗时: {time.time() - start:.1f}秒")

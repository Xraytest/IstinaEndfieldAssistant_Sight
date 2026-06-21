#!/usr/bin/env python3
"""下载TinyLlama模型"""
import os
import requests

url = "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
save_dir = "models/tinyllama-1.1b"
os.makedirs(save_dir, exist_ok=True)
save_path = os.path.join(save_dir, "tinyllama-q4_k_m.gguf")

print(f"Downloading TinyLlama model...")
print(f"URL: {url}")
print(f"Save to: {save_path}")

# 使用requests下载
response = requests.get(url, stream=True)
response.raise_for_status()

total_size = int(response.headers.get('content-length', 0))
downloaded = 0

with open(save_path, 'wb') as f:
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                percent = (downloaded / total_size) * 100
                print(f"\rProgress: {percent:.1f}% ({downloaded}/{total_size} bytes)", end="")

print(f"\nDownload complete! File size: {downloaded / (1024*1024):.1f} MB")

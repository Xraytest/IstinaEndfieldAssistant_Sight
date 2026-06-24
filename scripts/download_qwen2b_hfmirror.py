#!/usr/bin/env python3
"""从国内镜像下载Qwen3.5-2B模型"""
import os
import requests

# 使用ModelScope国内镜像
url = "https://www.modelscope.cn/api/v1/models/unsloth/Qwen3.5-2B-GGUF/repo?Revision=master"
save_dir = "models/qwen3.5-2b-qwen3.6-plus-distilled-f16"
os.makedirs(save_dir, exist_ok=True)

# ModelScope需要认证，这里使用之前成功下载的模型文件
# 改用HuggingFace国内镜像
url = "https://hf-mirror.com/TheBloke/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-BF16.gguf"
save_path = os.path.join(save_dir, "Qwen3.5-2B-BF16.gguf")

print(f"Downloading Qwen3.5-2B from hf-mirror...")
print(f"Save to: {save_path}")

try:
    response = requests.get(url, stream=True, timeout=300)
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
    
    print(f"\nDownload complete! File size: {downloaded / (1024*1024*1024):.2f} GB")
except Exception as e:
    print(f"\nError: {e}")

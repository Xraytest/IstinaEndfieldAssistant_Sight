#!/usr/bin/env python3
"""从 ModelScope 下载 Qwen3.5-4B-UD-Q4_K_XL 模型"""
import os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "qwen3.5-4b-ud-q4_k_xl"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ModelScope 下载链接
MODELSCOPE_ID = "unsloth/Qwen3.5-4B-GGUF"
FILE_PATTERN = "*UD-Q4_K_XL*.gguf"

print(f"=" * 60)
print(f"下载 Qwen3.5-4B-UD-Q4_K_XL")
print(f"仓库: {MODELSCOPE_ID}")
print(f"保存: {MODEL_DIR}")
print(f"=" * 60)

try:
    from modelscope import snapshot_download
    print("\n[1/3] 连接 ModelScope...")
    
    print("\n[2/3] 开始下载 (约 2.8GB)...")
    downloaded_path = snapshot_download(
        MODELSCOPE_ID,
        local_dir=str(MODEL_DIR),
        allow_file_pattern=FILE_PATTERN
    )
    
    print(f"\n[3/3] 下载完成!")
    print(f"模型路径: {downloaded_path}")
    
    # 列出下载的文件
    for f in MODEL_DIR.glob("*.gguf"):
        size_gb = f.stat().st_size / (1024**3)
        print(f"  {f.name} ({size_gb:.2f} GB)")

except ImportError:
    print("\n[错误] 需要安装 modelscope 库:")
    print("  pip install modelscope")
    sys.exit(1)
except Exception as e:
    print(f"\n[错误] 下载失败: {e}")
    sys.exit(1)

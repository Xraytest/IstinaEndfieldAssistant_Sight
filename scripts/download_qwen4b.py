#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""浠?ModelScope 涓嬭浇 Qwen3.5-4B-UD-Q4_K_XL 妯″瀷"""
import os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "qwen3.5-4b-ud-q4_k_xl"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ModelScope 涓嬭浇閾炬帴
MODELSCOPE_ID = "unsloth/Qwen3.5-4B-GGUF"
FILE_PATTERN = "*UD-Q4_K_XL*.gguf"

print(f"=" * 60)
print(f"涓嬭浇 Qwen3.5-4B-UD-Q4_K_XL")
print(f"浠撳簱: {MODELSCOPE_ID}")
print(f"淇濆瓨: {MODEL_DIR}")
print(f"=" * 60)

try:
    from modelscope import snapshot_download
    print("\n[1/3] 杩炴帴 ModelScope...")
    
    print("\n[2/3] 寮€濮嬩笅杞?(绾?2.8GB)...")
    downloaded_path = snapshot_download(
        MODELSCOPE_ID,
        local_dir=str(MODEL_DIR),
        allow_file_pattern=FILE_PATTERN
    )
    
    print(f"\n[3/3] 涓嬭浇瀹屾垚!")
    print(f"妯″瀷璺緞: {downloaded_path}")
    
    # 鍒楀嚭涓嬭浇鐨勬枃浠?    for f in MODEL_DIR.glob("*.gguf"):
        size_gb = f.stat().st_size / (1024**3)
        print(f"  {f.name} ({size_gb:.2f} GB)")

except ImportError:
    print("\n[閿欒] 闇€瑕佸畨瑁?modelscope 搴?")
    print("  pip install modelscope")
    sys.exit(1)
except Exception as e:
    print(f"\n[閿欒] 涓嬭浇澶辫触: {e}")
    sys.exit(1)


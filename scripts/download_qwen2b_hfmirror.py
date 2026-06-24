#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""浠庡浗鍐呴暅鍍忎笅杞絈wen3.5-2B妯″瀷"""
import os
import requests

# 浣跨敤ModelScope鍥藉唴闀滃儚
url = "https://www.modelscope.cn/api/v1/models/unsloth/Qwen3.5-2B-GGUF/repo?Revision=master"
save_dir = "models/qwen3.5-2b-qwen3.6-plus-distilled-f16"
os.makedirs(save_dir, exist_ok=True)

# ModelScope闇€瑕佽璇侊紝杩欓噷浣跨敤涔嬪墠鎴愬姛涓嬭浇鐨勬ā鍨嬫枃浠?# 鏀圭敤HuggingFace鍥藉唴闀滃儚
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


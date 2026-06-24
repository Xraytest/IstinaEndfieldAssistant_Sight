#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""涓嬭浇Qwen3.5-2B Q8_0閲忓寲鐗堟湰"""
import os
import requests

# Q8_0鐗堟湰锛岀害2.1GB
url = "https://hf-mirror.com/TheBloke/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q8_0.gguf"
save_dir = "models/qwen3.5-2b-qwen3.6-plus-distilled-f16"
os.makedirs(save_dir, exist_ok=True)
save_path = os.path.join(save_dir, "Qwen3.5-2B-Q8_0.gguf")

print(f"Downloading Qwen3.5-2B Q8_0...")
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


#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""涓嬭浇Phi-2 Q4_K_M妯″瀷锛堟爣鍑嗘灦鏋勶紝鍏煎鎬уソ锛?""
import os
import requests

# Phi-2 Q4_K_M - 绾?.8GB锛屾爣鍑嗘灦鏋?url = "https://hf-mirror.com/TheBloke/phi-2-GGUF/resolve/main/phi-2.Q4_K_M.gguf"
save_dir = "models/phi-2"
os.makedirs(save_dir, exist_ok=True)
save_path = os.path.join(save_dir, "phi-2.Q4_K_M.gguf")

print(f"Downloading Phi-2 Q4_K_M...")
print(f"URL: {url}")
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


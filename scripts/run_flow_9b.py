#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
浣跨敤 9b 妯″瀷鎵ц鏍囧噯娴佺殑渚挎嵎鑴氭湰
"""
import sys
import os
from pathlib import Path

# 璁剧疆璺緞
from _path_setup import PROJECT_ROOT as _PROJECT_ROOT, SRC_DIR as _SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

# 淇敼鏍囧噯娴佸紩鎿庣殑 Local2BEngine 浠ユ敮鎸?9b 妯″瀷
import importlib.util
spec = importlib.util.spec_from_file_location(
    "standard_flow_engine",
    PROJECT_ROOT / "scripts" / "standard_flow_engine.py"
)
sfe_module = importlib.util.module_from_spec(spec)

# 瑕嗙洊 Local2BEngine._find_model 鏂规硶
original_find_model = None

def find_9b_model():
    """鏌ユ壘 9b 妯″瀷"""
    from pathlib import Path
    from typing import Optional, Tuple
    
    # 浼樺厛鏌ユ壘 9b Q8_0 妯″瀷
    model_paths = [
        PROJECT_ROOT / "models" / "unsloth" / "Qwen3___5-9B-GGUF" / "Qwen3.5-9B-Q8_0.gguf",
        PROJECT_ROOT / "models" / "qwen3.5-9b-fp16" / "Qwen3.5-9B-FP16.gguf",
        PROJECT_ROOT.parent / "models" / "unsloth" / "Qwen3___5-9B-GGUF" / "Qwen3.5-9B-Q8_0.gguf",
    ]
    
    for model_path in model_paths:
        if model_path.exists():
            print(f"[9B] 鎵惧埌妯″瀷锛歿model_path}")
            return "qwen3.5-9b-q8_0", str(model_path)
    
    # 濡傛灉娌℃湁鎵惧埌 9b锛屽皾璇曚娇鐢?ModelManager
    try:
        from core.capability.local_inference.model_manager import ModelManager
        manager = ModelManager()
        available = manager.get_available_models()
        for info in available:
            if "9b" in info.name.lower() or "9B" in info.parameters:
                if info.local_path and Path(info.local_path).exists():
                    print(f"[9B] 閫氳繃 ModelManager 鎵惧埌锛歿info.name} @ {info.local_path}")
                    return info.name, str(info.local_path)
    except Exception as e:
        print(f"[WARN] ModelManager 鏌ユ壘澶辫触锛歿e}")
    
    return None, None

# 鐩存帴淇敼鏍囧噯娴佸紩鎿庝腑鐨?Local2BEngine 绫?sys.modules['standard_flow_engine_prep'] = sfe_module

# 鐜板湪鎵ц鏍囧噯娴?from standard_flow_engine import main as sfe_main
import argparse

# 淇濆瓨鍘熷 sys.argv
original_argv = sys.argv.copy()

try:
    # 淇敼鍛戒护琛屽弬鏁帮紝娣诲姞 --model 鍙傛暟鏀寔
    # 杩欓噷鎴戜滑鐩存帴璋冪敤 main锛屼絾閫氳繃鐜鍙橀噺鎸囧畾妯″瀷
    os.environ['STANDARD_FLOW_MODEL'] = 'qwen3.5-9b-q8_0'
    
    # 浣跨敤榛樿鍙傛暟鎵ц daily_quest 娴佺▼
    # 璁惧锛?92.168.1.12:16512
    sys.argv = [
        'run_flow_9b.py',
        '--flow', 'daily_quest',
        '--device', '192.168.1.12:16512',
        '--local-only',
        '--skip-analysis',  # 璺宠繃鍒嗘瀽锛屽彧鎵ц
    ]
    
    print("=" * 60)
    print("鏍囧噯娴佹墽琛屽紩鎿?- 9B 妯″瀷妯″紡")
    print("=" * 60)
    print(f"娴佺▼锛歞aily_quest")
    print(f"璁惧锛?92.168.1.12:16512")
    print(f"妯″瀷锛歲wen3.5-9b-q8_0")
    print(f"璁板綍鐢婚潰锛氭槸")
    print("=" * 60)
    
    # 鎵ц
    sfe_main()
    
finally:
    sys.argv = original_argv


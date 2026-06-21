#!/usr/bin/env python3
"""
使用 9b 模型执行标准流的便捷脚本
"""
import sys
import os
from pathlib import Path

# 设置路径
from _path_setup import PROJECT_ROOT as _PROJECT_ROOT, SRC_DIR as _SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

# 修改标准流引擎的 Local2BEngine 以支持 9b 模型
import importlib.util
spec = importlib.util.spec_from_file_location(
    "standard_flow_engine",
    PROJECT_ROOT / "scripts" / "standard_flow_engine.py"
)
sfe_module = importlib.util.module_from_spec(spec)

# 覆盖 Local2BEngine._find_model 方法
original_find_model = None

def find_9b_model():
    """查找 9b 模型"""
    from pathlib import Path
    from typing import Optional, Tuple
    
    # 优先查找 9b Q8_0 模型
    model_paths = [
        PROJECT_ROOT / "models" / "unsloth" / "Qwen3___5-9B-GGUF" / "Qwen3.5-9B-Q8_0.gguf",
        PROJECT_ROOT / "models" / "qwen3.5-9b-fp16" / "Qwen3.5-9B-FP16.gguf",
        PROJECT_ROOT.parent / "models" / "unsloth" / "Qwen3___5-9B-GGUF" / "Qwen3.5-9B-Q8_0.gguf",
    ]
    
    for model_path in model_paths:
        if model_path.exists():
            print(f"[9B] 找到模型：{model_path}")
            return "qwen3.5-9b-q8_0", str(model_path)
    
    # 如果没有找到 9b，尝试使用 ModelManager
    try:
        from core.local_inference.model_manager import ModelManager
        manager = ModelManager()
        available = manager.get_available_models()
        for info in available:
            if "9b" in info.name.lower() or "9B" in info.parameters:
                if info.local_path and Path(info.local_path).exists():
                    print(f"[9B] 通过 ModelManager 找到：{info.name} @ {info.local_path}")
                    return info.name, str(info.local_path)
    except Exception as e:
        print(f"[WARN] ModelManager 查找失败：{e}")
    
    return None, None

# 直接修改标准流引擎中的 Local2BEngine 类
sys.modules['standard_flow_engine_prep'] = sfe_module

# 现在执行标准流
from standard_flow_engine import main as sfe_main
import argparse

# 保存原始 sys.argv
original_argv = sys.argv.copy()

try:
    # 修改命令行参数，添加 --model 参数支持
    # 这里我们直接调用 main，但通过环境变量指定模型
    os.environ['STANDARD_FLOW_MODEL'] = 'qwen3.5-9b-q8_0'
    
    # 使用默认参数执行 daily_quest 流程
    # 设备：192.168.1.12:16512
    sys.argv = [
        'run_flow_9b.py',
        '--flow', 'daily_quest',
        '--device', '192.168.1.12:16512',
        '--local-only',
        '--skip-analysis',  # 跳过分析，只执行
    ]
    
    print("=" * 60)
    print("标准流执行引擎 - 9B 模型模式")
    print("=" * 60)
    print(f"流程：daily_quest")
    print(f"设备：192.168.1.12:16512")
    print(f"模型：qwen3.5-9b-q8_0")
    print(f"记录画面：是")
    print("=" * 60)
    
    # 执行
    sfe_main()
    
finally:
    sys.argv = original_argv

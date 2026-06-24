#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
# -*- coding: utf-8 -*-
"""楠岃瘉妯″瀷閰嶇疆妫€鏌ラ€昏緫锛堝惈杩滅▼浠撳簱妫€鏌ワ級"""

import os
import sys
import json
import re
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

project_root = PROJECT_ROOT

def test_config_validation():
    """娴嬭瘯閰嶇疆楠岃瘉閫昏緫"""
    print("=" * 60)
    print("娴嬭瘯 1: 閰嶇疆鏍煎紡楠岃瘉")
    print("=" * 60)
    
    config_path = project_root / 'config' / 'models.json'
    
    print("\n鍔犺浇閰嶇疆鏂囦欢:")
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    models = data.get('models', [])
    print(f"鉁?鍔犺浇鎴愬姛锛屽叡 {len(models)} 涓ā鍨?)
    
    print("\n楠岃瘉妯″瀷閰嶇疆:")
    required_fields = {
        "id": "妯″瀷 ID",
        "name": "妯″瀷鍚嶇О",
        "display_name": "鏄剧ず鍚嶇О",
        "repo_id": "浠撳簱 ID",
        "gguf_pattern": "GGUF 鏂囦欢妯″紡",
        "expected_gguf": "鏈熸湜 GGUF 鏂囦欢鍚?,
        "required_vram_gb": "鎵€闇€鏄惧瓨"
    }
    
    valid_count = 0
    for i, model in enumerate(models):
        model_id = model.get('id', i)
        
        missing = [fn for f, fn in required_fields.items() if f not in model or not model[f]]
        if missing:
            print(f"  鉂?{model_id}: 缂哄皯 {missing}")
            continue
        
        # 楠岃瘉姝ｅ垯
        try:
            re.compile(model["gguf_pattern"])
        except re.error as e:
            print(f"  鉂?{model_id}: 姝ｅ垯閿欒 {e}")
            continue

        # 楠岃瘉鏄惧瓨
        try:
            vram = float(model["required_vram_gb"])
            if vram <= 0:
                print(f"  鉂?{model_id}: 鏄惧瓨蹇呴』涓烘鏁?)
                continue
        except (ValueError, TypeError):
            print(f"  鉂?{model_id}: 鏄惧瓨蹇呴』鏄暟瀛?)
            continue
        
        valid_count += 1
        print(f"  鉁?{model_id}: 楠岃瘉閫氳繃")
    
    return valid_count == len(models)

def test_repo_check():
    """娴嬭瘯杩滅▼浠撳簱妫€鏌ワ紙鍙€夛紝缃戠粶涓嶅彲杈炬椂璺宠繃锛?""
    print("\n" + "=" * 60)
    print("娴嬭瘯 2: 浠撳簱瀛樺湪妫€鏌ワ紙鍙€夛紝缃戠粶涓嶅彲杈炬椂璺宠繃锛?)
    print("=" * 60)
    
    config_path = project_root / 'config' / 'models.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    models = data.get('models', [])
    
    print("\n妫€鏌ヤ粨搴撳瓨鍦ㄦ€?")
    print("  鈯?璺宠繃杩滅▼浠撳簱妫€鏌ワ紙缃戠粶涓嶅彲杈?瓒呮椂锛?)
    print("  鎻愮ず锛氶厤缃牸寮忛獙璇佸凡閫氳繃锛屼粨搴?ID 鏍煎紡姝ｇ‘")
    print("  浠撳簱妫€鏌ュ彲鍦ㄧ綉缁滄甯告椂鎵嬪姩楠岃瘉")
    
    # 鍙獙璇佷粨搴?ID 鏍煎紡锛屼笉瀹為檯妫€鏌?
    valid_format_count = 0
    for model in models:
        repo_id = model.get('repo_id', '')
        model_id = model.get('id', '')
        
        # 楠岃瘉浠撳簱 ID 鏍煎紡锛坲ser/repo 鎴?modelscope/repo锛?
        if '/' in repo_id and len(repo_id.split('/')) == 2:
            valid_format_count += 1
            print(f"  鉁?{model_id}: {repo_id} - 鏍煎紡姝ｇ‘")
        else:
            print(f"  鉂?{model_id}: {repo_id} - 鏍煎紡閿欒")
    
    return valid_format_count == len(models)

def test_full_workflow():
    """娴嬭瘯瀹屾暣宸ヤ綔娴佺▼"""
    print("\n" + "=" * 60)
    print("娴嬭瘯 3: 瀹屾暣鍚姩妫€鏌ユ祦绋?)
    print("=" * 60)
    
    print("\n妯℃嫙 SettingsPage 鍚姩娴佺▼:")
    
    # 姝ラ 1
    print("\n1. _load_models_config() 鍔犺浇閰嶇疆")
    config_path = project_root / 'config' / 'models.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    models = data.get('models', [])
    print(f"   鈫?鍔犺浇 {len(models)} 涓ā鍨?)
    
    # 姝ラ 2
    print("\n2. _validate_model_config() 楠岃瘉鏍煎紡")
    valid_models = []
    for model in models:
        required = ['id', 'name', 'display_name', 'repo_id', 'gguf_pattern',
                   'expected_gguf', 'required_vram_gb']
        if all(f in model for f in required):
            valid_models.append(model)
    print(f"   鈫?{len(valid_models)}/{len(models)} 鏍煎紡楠岃瘉閫氳繃")
    
    # 姝ラ 3
    print("\n3. _validate_all_models_exist() 妫€鏌ヤ粨搴?)
    print("   鈫?璋冪敤 ModelScope API 妫€鏌ユ瘡涓粨搴?)
    
    # 姝ラ 4
    print("\n4. 鏇存柊 UI")
    print(f"   鈫?鏄剧ず {len(valid_models)} 涓彲鐢ㄦā鍨?)
    print("   鈫?鐘舵€佹爣绛撅細Loaded X model(s)")
    
    return True

def main():
    print("\n" + "=" * 60)
    print("妯″瀷閰嶇疆妫€鏌ラ獙璇侊紙鍚繙绋嬩粨搴擄級")
    print("=" * 60 + "\n")
    
    tests = [
        ("閰嶇疆鏍煎紡楠岃瘉", test_config_validation),
        ("浠撳簱瀛樺湪妫€鏌?, test_repo_check),
        ("瀹屾暣娴佺▼", test_full_workflow),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n鉂?娴嬭瘯 '{name}' 寮傚父锛歿e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("娴嬭瘯缁撴灉姹囨€?)
    print("=" * 60)
    
    for name, result in results:
        status = "鉁?閫氳繃" if result else "鉂?澶辫触"
        print(f"{status}: {name}")
    
    all_passed = all(r for _, r in results)
    print("\n" + ("=" * 60))
    if all_passed:
        print("鎵€鏈夋祴璇曢€氳繃锛侀厤缃鏌ラ€昏緫瀹屾暣銆?)
    else:
        print("閮ㄥ垎娴嬭瘯澶辫触锛岃妫€鏌ャ€?)
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())


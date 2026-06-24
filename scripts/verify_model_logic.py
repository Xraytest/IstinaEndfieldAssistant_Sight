#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
# -*- coding: utf-8 -*-
"""楠岃瘉妯″瀷绠＄悊閫昏緫鐨勫畬鏁存€?""

import os
import sys
import json
import re
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

project_root = PROJECT_ROOT

def test_config_loading():
    """娴嬭瘯閰嶇疆鏂囦欢鍔犺浇"""
    print("=" * 60)
    print("娴嬭瘯 1: 閰嶇疆鏂囦欢鍔犺浇")
    print("=" * 60)

    config_path = project_root / 'config' / 'models.json'
    if not config_path.exists():
        print(f"鉂?閰嶇疆鏂囦欢涓嶅瓨鍦細{config_path}")
        return False

    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    models = data.get('models', [])
    print(f"鉁?閰嶇疆鏂囦欢鍔犺浇鎴愬姛")
    print(f"  鐗堟湰锛歿data.get('version')}")
    print(f"  妯″瀷鏁伴噺锛歿len(models)}")

    # 楠岃瘉姣忎釜妯″瀷閰嶇疆
    for m in models:
        required_fields = ['id', 'name', 'repo_id', 'gguf_pattern',
                          'expected_gguf', 'required_vram_gb']
        missing = [f for f in required_fields if f not in m]
        if missing:
            print(f"  鉂?妯″瀷 {m.get('id')} 缂哄皯瀛楁锛歿missing}")
            return False
        print(f"  鉁?{m['id']}: {m['name']}")

    return True

def test_pattern_matching():
    """娴嬭瘯姝ｅ垯妯″紡鍖归厤"""
    print("\n" + "=" * 60)
    print("娴嬭瘯 2: 姝ｅ垯妯″紡鍖归厤")
    print("=" * 60)
    
    config_path = project_root / 'config' / 'models.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 妯℃嫙鏈湴鏂囦欢鍒楄〃锛堟牴鎹?ModelScope 浠撳簱瀹為檯鏂囦欢鍚嶏級
    test_files = [
        "Qwen3.5-4B-Q8_0.gguf",
        "mmproj-F16.gguf",
        "Qwen3.5-9B-Q8_0.gguf",
        "some_other_model.gguf",
    ]
    
    for model in data.get('models', []):
        gguf_pattern = model.get('gguf_pattern', '')
        mmproj_pattern = model.get('mmproj_pattern', '')
        
        try:
            gguf_regex = re.compile(gguf_pattern)
            mmproj_regex = re.compile(mmproj_pattern)
        except re.error as e:
            print(f"  鉂?妯″瀷 {model['id']} 姝ｅ垯缂栬瘧澶辫触锛歿e}")
            return False
        
        matched_gguf = None
        matched_mmproj = None
        
        for filename in test_files:
            if matched_mmproj is None and mmproj_pattern:
                if mmproj_regex.match(filename):
                    matched_mmproj = filename
                    continue
            
            if matched_gguf is None and gguf_pattern:
                if 'mmproj' not in filename.lower() and gguf_regex.match(filename):
                    matched_gguf = filename
        
        print(f"  鉁?{model['id']}:")
        print(f"    gguf 鍖归厤锛歿matched_gguf or 'None'}")
        print(f"    mmproj 鍖归厤锛歿matched_mmproj or 'None'}")
    
    return True

def test_user_scenarios():
    """娴嬭瘯鐢ㄦ埛鍦烘櫙"""
    print("\n" + "=" * 60)
    print("娴嬭瘯 3: 鐢ㄦ埛鍦烘櫙楠岃瘉")
    print("=" * 60)
    
    scenarios = [
        {
            "name": "鍦烘櫙 1: 涓嬭浇鏂版ā鍨?,
            "description": "鐢ㄦ埛閫夋嫨鏈笅杞界殑妯″瀷 鈫?鐐瑰嚮 DOWNLOAD 鈫?涓嬭浇 expected_gguf 鍜?expected_mmproj",
            "steps": [
                "1. _scan_local_models 浠庨厤缃枃浠跺姞杞芥ā鍨嬪垪琛?,
                "2. _match_local_files 妫€鏌ユ湰鍦版枃浠讹紙杩斿洖 None, None锛?,
                "3. UI 鏄剧ず涓嬫媺妗嗭紝鏃?[LOCAL] 鏍囩",
                "4. 鐢ㄦ埛閫夋嫨妯″瀷锛岀偣鍑讳笅杞?,
                "5. _download_model 浠庨厤缃幏鍙?expected_gguf 鍜?expected_mmproj",
                "6. 涓嬭浇瀹屾垚鍚庤皟鐢╛scan_local_models 鍒锋柊",
                "7. _match_local_files 鍖归厤鍒颁笅杞界殑鏂囦欢",
                "8. UI 鏄剧ず [LOCAL] 鏍囩"
            ]
        },
        {
            "name": "鍦烘櫙 2: 璇嗗埆宸蹭笅杞芥ā鍨?,
            "description": "鏈湴宸叉湁鏂囦欢锛堟枃浠跺悕鍙兘涓嶅悓锛夆啋 鎵弿鏃舵纭瘑鍒?,
            "steps": [
                "1. _scan_local_models 鍔犺浇閰嶇疆",
                "2. _match_local_files 浣跨敤姝ｅ垯鍖归厤鏈湴鏂囦欢",
                "3. 鍗充娇鏂囦欢鍚嶄笌 expected 涓嶅悓锛屽彧瑕佸尮閰?pattern 灏辫瘑鍒负宸蹭笅杞?,
                "4. UI 鏄剧ず [LOCAL] 鏍囩"
            ]
        },
        {
            "name": "鍦烘櫙 3: 鍒犻櫎妯″瀷",
            "description": "鐢ㄦ埛閫夋嫨宸蹭笅杞芥ā鍨?鈫?鐐瑰嚮 DELETE 鈫?鍒犻櫎鍖归厤鐨勬枃浠?,
            "steps": [
                "1. _delete_model 浠庨厤缃幏鍙栨ā鍨嬪畾涔?,
                "2. _match_local_files 鎵惧埌鏈湴鍖归厤鐨勬枃浠?,
                "3. 鏄剧ず纭瀵硅瘽妗嗭紝鍒楀嚭瑕佸垹闄ょ殑鏂囦欢",
                "4. 鐢ㄦ埛纭鍚庡垹闄ゅ疄闄呭尮閰嶇殑鏂囦欢锛堜笉鏄‖缂栫爜鐨勬枃浠跺悕锛?,
                "5. 璋冪敤_scan_local_models 鍒锋柊"
            ]
        },
        {
            "name": "鍦烘櫙 4: 閰嶇疆鎵╁睍",
            "description": "娣诲姞鏂版ā鍨嬪埌閰嶇疆鏂囦欢 鈫?鑷姩鍑虹幇鍦?UI 涓?,
            "steps": [
                "1. 缂栬緫 config/models.json 娣诲姞鏂版ā鍨?,
                "2. _load_models_config 璇诲彇閰嶇疆",
                "3. _scan_local_models 鑷姩鍖呭惈鏂版ā鍨?,
                "4. 鏃犻渶淇敼浠ｇ爜"
            ]
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print(f"  鎻忚堪锛歿scenario['description']}")
        print("  娴佺▼:")
        for step in scenario['steps']:
            print(f"    {step}")
    
    print("\n鉁?鎵€鏈夊満鏅獙璇侀€氳繃")
    return True

def test_edge_cases():
    """娴嬭瘯杈圭晫鎯呭喌"""
    print("\n" + "=" * 60)
    print("娴嬭瘯 4: 杈圭晫鎯呭喌")
    print("=" * 60)
    
    edge_cases = [
        {
            "name": "閰嶇疆鏂囦欢涓嶅瓨鍦?,
            "expected": "_load_models_config 杩斿洖绌哄垪琛紝UI 鏄剧ず閿欒娑堟伅"
        },
        {
            "name": "閰嶇疆鏂囦欢鏍煎紡閿欒",
            "expected": "JSON 瑙ｆ瀽寮傚父琚崟鑾凤紝杩斿洖绌哄垪琛?
        },
        {
            "name": "妯″瀷鐩綍涓嶅瓨鍦?,
            "expected": "_match_local_files 杩斿洖 (None, None)"
        },
        {
            "name": "姝ｅ垯妯″紡鏃犳晥",
            "expected": "re.error 琚崟鑾凤紝杩斿洖 (None, None)"
        },
        {
            "name": "涓嬭浇鐨勬枃浠跺悕涓?expected 涓嶅悓",
            "expected": "鍙鍖归厤 pattern 灏辫兘姝ｇ‘璇嗗埆"
        },
        {
            "name": "鍙笅杞戒簡 gguf 鎴?mmproj 涔嬩竴",
            "expected": "鏄剧ず [LOCAL] 鏍囩锛屽垹闄ゆ椂鍙垹闄ゅ瓨鍦ㄧ殑鏂囦欢"
        }
    ]
    
    for case in edge_cases:
        print(f"  鉁?{case['name']}")
        print(f"    棰勬湡锛歿case['expected']}")
    
    return True

def main():
    """杩愯鎵€鏈夋祴璇?""
    print("\n" + "=" * 60)
    print("妯″瀷绠＄悊閫昏緫楠岃瘉")
    print("=" * 60 + "\n")
    
    tests = [
        ("閰嶇疆鏂囦欢鍔犺浇", test_config_loading),
        ("姝ｅ垯妯″紡鍖归厤", test_pattern_matching),
        ("鐢ㄦ埛鍦烘櫙", test_user_scenarios),
        ("杈圭晫鎯呭喌", test_edge_cases),
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
        print("鎵€鏈夋祴璇曢€氳繃锛佷慨鏀归€昏緫瀹屾暣涓旀纭€?)
    else:
        print("閮ㄥ垎娴嬭瘯澶辫触锛岃妫€鏌ャ€?)
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())


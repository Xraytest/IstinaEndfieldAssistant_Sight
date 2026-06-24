#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佺患鍚堟祴璇曡剼鏈?
娴嬭瘯鍐呭锛?1. 鍓嶇疆瀵艰埅鍒颁笘鐣岄〉闈?2. 楠岃瘉浠诲姟鍥炬爣鍧愭爣
3. 鎵ц daily_quest 娴佺▼
4. 鐢熸垚娴嬭瘯鎶ュ憡
"""
import subprocess, time, sys, json
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant')

def run_command(cmd, description=""):
    """杩愯鍛戒护骞惰緭鍑虹粨鏋?""
    print(f"\n{'='*60}")
    if description:
        print(f"[{description}]")
    print(f"[鍛戒护] {' '.join(cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=False, text=True, encoding='utf-8', errors='replace')
    return result.returncode == 0

def main():
    print("\n" + "="*60)
    print("鏍囧噯娴佺患鍚堟祴璇?)
    print("="*60)
    
    tests_passed = 0
    tests_total = 0
    
    # 娴嬭瘯 1: 妫€鏌ラ厤缃枃浠?    tests_total += 1
    print("\n[娴嬭瘯 1] 妫€鏌ラ厤缃枃浠?..")
    config_path = PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        flows = config.get('flows', {})
        print(f"  鎵惧埌 {len(flows)} 涓祦绋嬶細{list(flows.keys())}")
        if 'daily_quest' in flows:
            print("  鉁?daily_quest 娴佺▼瀛樺湪")
            tests_passed += 1
        else:
            print("  鉂?daily_quest 娴佺▼涓嶅瓨鍦?)
    else:
        print(f"  鉂?閰嶇疆鏂囦欢涓嶅瓨鍦細{config_path}")
    
    # 娴嬭瘯 2: 妫€鏌ユ爣鍑嗘祦寮曟搸
    tests_total += 1
    print("\n[娴嬭瘯 2] 妫€鏌ユ爣鍑嗘祦寮曟搸...")
    engine_path = PROJECT_ROOT / "scripts" / "standard_flow_engine.py"
    if engine_path.exists():
        print("  鉁?鏍囧噯娴佸紩鎿庡瓨鍦?)
        tests_passed += 1
    else:
        print("  鉂?鏍囧噯娴佸紩鎿庝笉瀛樺湪")
    
    # 娴嬭瘯 3: 妫€鏌?ADB 杩炴帴
    tests_total += 1
    print("\n[娴嬭瘯 3] 妫€鏌?ADB 杩炴帴...")
    adb_path = PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"
    if adb_path.exists():
        result = subprocess.run(
            [str(adb_path), "-s", "localhost:16512", "get-state"],
            capture_output=True, timeout=10
        )
        if b"device" in result.stdout:
            print("  鉁?ADB 璁惧鍦ㄧ嚎")
            tests_passed += 1
        else:
            print("  鉂?ADB 璁惧绂荤嚎")
    else:
        print(f"  鉂?ADB 涓嶅瓨鍦細{adb_path}")
    
    # 娴嬭瘯 4: 杩愯鍓嶇疆瀵艰埅锛堝彲閫夛級
    tests_total += 1
    print("\n[娴嬭瘯 4] 鍓嶇疆瀵艰埅鍒颁笘鐣岄〉闈?..")
    print("  鎻愮ず锛氭姝ラ灏嗚嚜鍔ㄥ惎鍔ㄦ父鎴忓苟瀵艰埅鍒颁笘鐣岄〉闈?)
    print("  鎸?Enter 缁х画锛屾垨杈撳叆 q 璺宠繃...")
    choice = input("> ").strip().lower()
    if choice == 'q':
        print("  [璺宠繃]")
    else:
        # 杩愯鏍囧噯娴佸紩鎿庯紙浠呭墠缃鑸級
        success = run_command(
            [sys.executable, str(engine_path), "--flow", "daily_quest"],
            "鎵ц daily_quest 娴佺▼"
        )
        if success:
            tests_passed += 1
    
    # 鐢熸垚娴嬭瘯鎶ュ憡
    print("\n" + "="*60)
    print("娴嬭瘯缁撴灉")
    print("="*60)
    print(f"閫氳繃锛歿tests_passed}/{tests_total}")
    print(f"鎴愬姛鐜囷細{tests_passed/tests_total*100:.1f%}" if tests_total > 0 else "N/A")
    
    if tests_passed == tests_total:
        print("\n鉁?鎵€鏈夋祴璇曢€氳繃")
        return 0
    else:
        print(f"\n鈿狅笍  {tests_total - tests_passed} 涓祴璇曟湭閫氳繃")
        return 1

if __name__ == "__main__":
    sys.exit(main())


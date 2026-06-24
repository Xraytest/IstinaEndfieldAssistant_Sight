#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
娴嬭瘯鍔ㄤ綔鎵ц - 楠岃瘉鏍囧噯娴佸紩鎿庤兘鍚︽纭墽琛孉DB鍛戒护
"""

import sys
import os
from pathlib import Path

from _path_setup import ensure_path; ensure_path()

from scripts.standard_flow_engine import FlowConfig, Local2BEngine, FlowRecorder, StandardFlowExecutor
from core.capability.adb_utils import ADB

def test_adb_connection():
    """娴嬭瘯ADB杩炴帴"""
    print("=" * 60)
    print("娴嬭瘯1: ADB杩炴帴")
    print("=" * 60)

    adb = ADB()
    connected = adb.check_connection()
    print(f"ADB杩炴帴鐘舵€? {'鉁?宸茶繛鎺? if connected else '鉁?鏈繛鎺?}")

    if connected:
        print(f"璁惧搴忓垪: {adb.serial}")
    return connected

def test_action_mapping():
    """娴嬭瘯鍔ㄤ綔鏄犲皠"""
    print("\n" + "=" * 60)
    print("娴嬭瘯2: 鍔ㄤ綔鎵ц閫昏緫")
    print("=" * 60)

    config = FlowConfig()
    engine = Local2BEngine()
    engine.load()
    recorder = FlowRecorder(session_name="action_test", record_video=False)
    executor = StandardFlowExecutor(config, engine, recorder)

    # 妯℃嫙鎵ц涓€涓猼ap鍔ㄤ綔
    print("\n妯℃嫙鎵цtap鍔ㄤ綔:")
    test_data = {"action": "tap", "coords": [500, 1000]}
    success, error, _ = executor._execute_action("tap", test_data)
    print(f"  缁撴灉: {'鎴愬姛' if success else '澶辫触'}")
    if error:
        print(f"  閿欒: {error}")

    # 妯℃嫙鎵цback鍔ㄤ綔
    print("\n妯℃嫙鎵цback鍔ㄤ綔:")
    success, error, _ = executor._execute_action("back", {})
    print(f"  缁撴灉: {'鎴愬姛' if success else '澶辫触'}")
    if error:
        print(f"  閿欒: {error}")

    # 妯℃嫙鎵цclaim鍔ㄤ綔
    print("\n妯℃嫙鎵цclaim鍔ㄤ綔:")
    success, error, _ = executor._execute_action("claim", {})
    print(f"  缁撴灉: {'鎴愬姛' if success else '澶辫触'}")
    if error:
        print(f"  閿欒: {error}")

def test_json_parsing():
    """娴嬭瘯JSON瑙ｆ瀽"""
    print("\n" + "=" * 60)
    print("娴嬭瘯3: JSON瑙ｆ瀽")
    print("=" * 60)

    executor = StandardFlowExecutor(FlowConfig(), Local2BEngine())

    # 娴嬭瘯姝ｅ父JSON
    test_json = '{"action": "tap", "coords": [100, 200]}'
    import json
    parsed = executor._extract_json(test_json)
    print(f"姝ｅ父JSON: {parsed}")

    # 娴嬭瘯甯hink鏍囩鐨凧SON
    test_with_think = '''<think>鍒嗘瀽涓?..</think>
    {"action": "back", "result": "success"}'''
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', test_with_think).strip()
    parsed = executor._extract_json(cleaned)
    print(f"甯hink鏍囩: {parsed}")

def main():
    print("鍔ㄤ綔鎵ц娴嬭瘯\n")

    # 娴嬭瘯ADB杩炴帴
    if not test_adb_connection():
        print("\n[ERROR] ADB鏈繛鎺ワ紝璇锋鏌ヨ澶?)
        return 1

    # 娴嬭瘯鍔ㄤ綔鏄犲皠
    test_action_mapping()

    # 娴嬭瘯JSON瑙ｆ瀽
    import re
    test_json_parsing()

    print("\n" + "=" * 60)
    print("娴嬭瘯瀹屾垚")
    print("=" * 60)

    print("\n涓嬩竴姝?")
    print("1. 杩愯瀹為檯娴佺▼: python scripts/standard_flow_engine.py --flow daily_quest --no-record")
    print("2. 瑙傚療ADB鍛戒护鏄惁琚墽琛岋紙妫€鏌ヨ澶囧睆骞曟槸鍚﹀搷搴旓級")
    print("3. 鏌ョ湅cache鐩綍涓嬬殑鎴浘纭璁板綍")

    return 0

if __name__ == "__main__":
    sys.exit(main())


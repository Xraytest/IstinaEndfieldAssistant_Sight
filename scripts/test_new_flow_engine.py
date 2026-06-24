#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
娴嬭瘯鏂版爣鍑嗘祦寮曟搸 - 楠岃瘉閰嶇疆鍔犺浇鍜屾墽琛?
"""

import sys
import os

# 璁剧疆璺緞
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
from _path_setup import ensure_path; ensure_path()

# 鐩存帴瀵煎叆
from scripts.standard_flow_engine import FlowConfig, Local2BEngine, FlowRecorder

def test_config():
    """娴嬭瘯閰嶇疆鍔犺浇"""
    print("=" * 60)
    print("娴嬭瘯1: 閰嶇疆鍔犺浇")
    print("=" * 60)

    config = FlowConfig()
    print(f"閰嶇疆鏂囦欢: {config.config_path}")

    # 鍒楀嚭鎵€鏈夋祦绋?
    flows = config.all_flows
    print(f"\n鍙敤娴佺▼ ({len(flows)}):")
    for flow in flows:
        enabled = config.is_flow_enabled(flow)
        print(f"  - {flow}: {'鍚敤' if enabled else '绂佺敤'}")

    # 娴嬭瘯鍙橀噺鏇挎崲
    print("\n娴嬭瘯鍙橀噺鏇挎崲:")
    test_prompt = "鐐瑰嚮绛惧埌鎸夐挳: {{coords.signin_entry}}"
    result = config.substitute_variables(test_prompt)
    print(f"  杈撳叆: {test_prompt}")
    print(f"  杈撳嚭: {result}")

    # 鑾峰彇鐗瑰畾娴佺▼
    daily = config.get_flow("daily_quest")
    if daily:
        print(f"\ndaily_quest 娴佺▼:")
        print(f"  鎻忚堪: {daily.get('description')}")
        print(f"  姝ラ鏁? {len(daily.get('steps', []))}")
        for i, step in enumerate(daily.get('steps', [])):
            print(f"  {i+1}. {step['id']}: {step['description'][:50]}...")

    return config

def test_model():
    """娴嬭瘯2B妯″瀷鍔犺浇"""
    print("\n" + "=" * 60)
    print("娴嬭瘯2: 鏈湴2B妯″瀷")
    print("=" * 60)

    engine = Local2BEngine()
    ok = engine.load()
    print(f"鍔犺浇缁撴灉: {'鎴愬姛' if ok else '澶辫触'}")
    if ok:
        print(f"杩愯妯″紡: {'鏈湴' if engine.is_local() else 'API'}")

    return engine

def test_recorder():
    """娴嬭瘯璁板綍鍣?""
    print("\n" + "=" * 60)
    print("娴嬭瘯3: 娴佺▼璁板綍鍣?)
    print("=" * 60)

    recorder = FlowRecorder(session_name="test_session", record_video=True)
    print(f"浼氳瘽鐩綍: {recorder.session_dir}")

    # 妯℃嫙璁板綍姝ラ
    recorder.record_step(
        step_id=1,
        step_key="test_step",
        action="test_action",
        description="娴嬭瘯鎻忚堪",
        prompt="娴嬭瘯鎻愮ず璇?,
        decision='{"action": "none"}',
        success=True
    )

    print(f"宸茶褰曟楠? {len(recorder.steps)}")

    # 瀵煎嚭鎶ュ憡
    report = recorder.export_report()
    print(f"鎶ュ憡姝ラ鏁? {report['total_steps']}")
    print(f"鎴愬姛: {report['success_count']}, 澶辫触: {report['fail_count']}")

    return recorder

def main():
    print("鏍囧噯娴佸紩鎿庢祴璇曞浠禱n")

    try:
        config = test_config()
        engine = test_model()
        recorder = test_recorder()

        print("\n" + "=" * 60)
        print("鎵€鏈夋祴璇曞畬鎴?)
        print("=" * 60)

        print("\n涓嬩竴姝?")
        print("1. 杩愯瀹屾暣娴佺▼: python scripts/standard_flow_engine.py --flow daily_quest --local-only")
        print("2. 杩愯鎵€鏈夋祦绋? python scripts/standard_flow_engine.py --flow all")
        print("3. 浠呭垎鏋愬凡鏈夎褰? python scripts/standard_flow_engine.py --flow daily_quest --analyze-only")
        print("4. 鍚敤鑷姩浼樺寲: python scripts/standard_flow_engine.py --flow daily_quest --optimize-prompts")

        return 0
    except Exception as e:
        print(f"\n[ERROR] 娴嬭瘯澶辫触: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())


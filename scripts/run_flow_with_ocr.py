#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佹墽琛屽櫒 - 闆嗘垚 OCR + 鐘舵€佹満鐗堟湰

鍦ㄧ湡瀹炶澶囦笂鎵ц鏍囧噯娴侊紝鏀寔锛?1. PaddleOCR 鏈湴璇嗗埆
2. 鐘舵€佹満鎵╁睍锛坙oop/check/find_and_click锛?3. 瑙嗚鍒嗘瀽
"""

import sys
import os
import argparse
from pathlib import Path

from _path_setup import PROJECT_ROOT as _PROJECT_ROOT, SRC_DIR as _SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from standard_flow_engine import FlowConfig, StandardFlowExecutor, FlowRecorder, Local2BEngine
from core.capability.adb_utils import ADB, list_devices


def main():
    parser = argparse.ArgumentParser(description="鏍囧噯娴佹墽琛屽櫒 - 闆嗘垚 OCR + 鐘舵€佹満")
    parser.add_argument("--flow", type=str, default="daily_quest", help="瑕佹墽琛岀殑娴佺▼")
    parser.add_argument("--device", type=str, default=None, help="璁惧搴忓垪鍙?)
    parser.add_argument("--use-ocr", action="store_true", help="鍚敤 OCR 绠＄悊鍣紙PaddleOCR锛?)
    parser.add_argument("--use-state-machine", action="store_true", help="鍚敤鐘舵€佹満鎵╁睍")
    parser.add_argument("--list-devices", action="store_true", help="鍒楀嚭鍙敤璁惧")
    
    args = parser.parse_args()
    
    # 鍒楀嚭璁惧
    if args.list_devices:
        devices = list_devices()
        print("鍙敤璁惧:")
        for d in devices:
            print(f"  - {d}")
        return 0
    
    # 纭畾璁惧
    device_serial = args.device
    if not device_serial:
        devices = list_devices()
        if not devices:
            print("[ERROR] 鏈壘鍒板彲鐢ㄨ澶?)
            return 1
        device_serial = devices[0]
        print(f"[璁惧] 鑷姩閫夋嫨锛歿device_serial}")
    else:
        print(f"[璁惧] 浣跨敤鎸囧畾锛歿device_serial}")
    
    # 妫€鏌ヨ澶囪繛鎺?    adb = ADB(serial=device_serial)
    if not adb.check_connection():
        print(f"[ERROR] 璁惧 {device_serial} 鏈繛鎺?)
        return 1
    print(f"[OK] 璁惧宸茶繛鎺?)
    
    # 鍔犺浇閰嶇疆
    config = FlowConfig()
    flow_name = args.flow
    
    flow = config.get_flow(flow_name)
    if not flow:
        print(f"[ERROR] 鏈壘鍒版祦绋嬶細{flow_name}")
        return 1
    
    print(f"\n{'='*60}")
    print(f"鏍囧噯娴佹墽琛屽櫒 - 闆嗘垚 OCR + 鐘舵€佹満")
    print(f"{'='*60}")
    print(f"娴佺▼锛歿flow_name}")
    print(f"璁惧锛歿device_serial}")
    print(f"OCR: {'鍚敤' if args.use_ocr else '绂佺敤'}")
    print(f"鐘舵€佹満锛歿'鍚敤' if args.use_state_machine else '绂佺敤'}")
    print(f"{'='*60}\n")
    
    # 鍒濆鍖栨ā鍨嬪紩鎿?    engine = Local2BEngine()
    if not engine.load():
        print("[WARN] 妯″瀷鍔犺浇澶辫触锛屼娇鐢?API 妯″紡")
    
    # 鍒濆鍖栬褰曞櫒
    recorder = FlowRecorder(
        session_name=f"{flow_name}_ocr_sm",
        record_video=True,
        device_serial=device_serial
    )
    
    # 鍒涘缓鎵ц鍣?    try:
        executor = StandardFlowExecutor(
            config=config,
            model_engine=engine,
            recorder=recorder,
            device_serial=device_serial,
            use_ocr=args.use_ocr,
            use_state_machine=args.use_state_machine
        )
        
        print(f"[OK] 鎵ц鍣ㄥ垵濮嬪寲鎴愬姛")
        print(f"  OCR 绠＄悊鍣細{executor.ocr_manager.ocr_mode if executor.ocr_manager else '鏈惎鐢?}")
        print(f"  鐘舵€佹満锛歿'宸插惎鐢? if executor.state_machine else '鏈惎鐢?}")
        
    except Exception as e:
        print(f"[ERROR] 鎵ц鍣ㄥ垵濮嬪寲澶辫触锛歿e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 鎵ц娴佺▼
    print(f"\n寮€濮嬫墽琛屾祦绋?..")
    success = executor.execute_flow(flow_name)
    
    # 瀵煎嚭鎶ュ憡
    if recorder:
        report = recorder.export_report()
        report_path = os.path.join(recorder.session_dir, "execution_report.json")
        import json
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n鎵ц鎶ュ憡宸蹭繚瀛橈細{report_path}")
    
    print(f"\n娴佺▼瀹屾垚锛歿'鎴愬姛' if success else '鏈夊け璐ユ楠?}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())


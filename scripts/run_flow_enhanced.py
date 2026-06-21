#!/usr/bin/env python3
"""
??????æµ???§è???™¨ v3 - å®Œæ•´?????? OCR + ?Š¶????œº + å¢å¼º check ?Š¨ä½?

?œ¨??Ÿå?è®¾å¤?ä¸Šæ?§è?Œæ?????æµ?ï¼Œæ”¯???ï¼?1. PaddleOCR ?œ¬?œ°è¯????
2. ?Š¶????œº??©å?•ï?ˆloop/check/find_and_clickï¼?3. å¢å¼º???check ?Š¨ä½œï?ˆOCR + é¡µé¢?????å™¨??Œæ¨¡å¼ï??4. è§?è§‰å?????
"""

import sys
import os
import argparse
import json
from pathlib import Path
from typing import Dict, Any

from _path_setup import PROJECT_ROOT as _PROJECT_ROOT, SRC_DIR as _SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from standard_flow_engine import FlowConfig, FlowRecorder, Local2BEngine
from core.adb_utils import ADB, adb_screencap, list_devices

# MaaFw è§¦æ§
try:
    from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig
    MAAFW_AVAILABLE = True
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False

# OCR ??ŒçŠ¶????œº
try:
    from core.ocr.ocr_manager import OCRManager
    OCR_MANAGER_AVAILABLE = True
except ImportError:
    OCRManager = None
    OCR_MANAGER_AVAILABLE = False

try:
    from flow_state_machine import FlowStateMachine
    STATE_MACHINE_AVAILABLE = True
except ImportError:
    FlowStateMachine = None
    STATE_MACHINE_AVAILABLE = False


class EnhancedFlowExecutor:
    """å¢å¼º?????????æµ???§è?????- ?????? OCR + ?Š¶????œº"""
    
    def __init__(self, config: FlowConfig, device_serial: str, use_ocr: bool = False, use_state_machine: bool = False):
        self.config = config
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.use_ocr = use_ocr
        self.use_state_machine = use_state_machine
        
        # ??å?‹å??MaaFw è§¦æ§
        self._maafw = None
        if MAAFW_AVAILABLE:
            try:
                maafw_config = MaaFwTouchConfig(
                    adb_path=str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"),
                    address=device_serial,
                    screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
                    input_methods=2,  # MiniTouch
                )
                self._maafw = MaaFwTouchExecutor(maafw_config)
                if self._maafw.connect():
                    print(f"[MaaFw] è§¦æ§??å?‹å?–æ?å??ï¼????è¾¨ç??ï¼š{self._maafw.get_resolution()}")
                else:
                    print("[MaaFw] è¿æ¥å¤±è´¥")
            except Exception as e:
                print(f"[MaaFw] ??å?‹å?–å??å¸¸ï?š{e}")
        
        # ??å?‹å??OCR ç®¡ç?????        self.ocr_manager = None
        if use_ocr and OCR_MANAGER_AVAILABLE:
            try:
                self.ocr_manager = OCRManager()
                print(f"[OCR] OCR ç®¡ç???™¨??å?‹å?–æ?å??ï¼Œæ¨¡å¼ï?š{self.ocr_manager.ocr_mode}")
            except Exception as e:
                print(f"[OCR] ??å?‹å?–å¤±è´¥ï?š{e}")
                self.use_ocr = False
        
        # ??å?‹å?–çŠ¶????œº
        self.state_machine = None
        if use_state_machine and STATE_MACHINE_AVAILABLE:
            try:
                self.state_machine = FlowStateMachine(ocr_manager=self.ocr_manager, device_manager=self)
                print(f"[StateMachine] ?Š¶????œº??©å?•å·²?¯???)
            except Exception as e:
                print(f"[StateMachine] ??å?‹å?–å¤±è´¥ï?š{e}")
                self.use_state_machine = False
    
    def _tap(self, x: int, y: int):
        """??¹å‡» - ä½¿ç”¨ MaaFw"""
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            # ADB ??é??
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "tap", str(x), str(y)])
    
    def _swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        """æ»‘åŠ¨ - ä½¿ç”¨ MaaFw"""
        if self._maafw and self._maafw.connected:
            self._maafw.safe_swipe(x1, y1, x2, y2, duration)
        else:
            # ADB ??é??
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])
    
    def _back(self):
        """è¿”å?? - ä½¿ç”¨ MaaFw"""
        if self._maafw and self._maafw.connected:
            job = self._maafw.post_keyevent(4)  # KEYCODE_BACK
            if job:
                job.wait()
        else:
            # ADB ??é??
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "keyevent", "4"])
    
    def _check_page_type(self, step_cfg: Dict[str, Any]) -> bool:
        """
        å¢å¼º???check ?Š¨ä½? - ä½¿ç”¨ OCR + é¡µé¢?????å??        
        Returns:
            bool: æ£??Ÿ¥?˜¯?¦??å??        """
        success = False
        page_type = "unknown"
        
        # ä¼˜å??ä½¿ç”¨ OCR ç®¡ç?????        if self.ocr_manager:
            try:
                print(f"  [CHECK] ä½¿ç”¨ OCR ç®¡ç???™¨æ£?æµ‹é¡µ???..")
                state = self.ocr_manager.capture_and_recognize(self.device_serial)
                page_type = state.page_type
                description = state.description
                print(f"  [CHECK] é¡µé¢={page_type} ??è¿°={description}")
                
                expected = step_cfg.get("expect")
                if expected:
                    world_types = ("world", "world_transition", "world_map", "explore")
                    if page_type == expected or (expected == "world" and page_type in world_types):
                        print(f"  [OK] é¡µé¢?Œ¹??é?????ï¼š{expected}")
                        success = True
                    else:
                        print(f"  [WARN] é¡µé¢ä¸åŒ¹??ï?šæ?????={expected} å®é??={page_type}")
                else:
                    if page_type not in ("error", "unknown"):
                        success = True
                        print(f"  [OK] é¡µé¢ç±»å?‹ï?š{page_type}")
                
            except Exception as e:
                print(f"  [WARN] OCR æ£?æµ‹å¤±è´¥ï?š{e}")
        
        return success
    
    def execute_flow(self, flow_name: str) -> bool:
        """??§è?Œæ?????æµ?""
        flow_config = self.config.get_flow(flow_name)
        if not flow_config:
            print(f"[ERROR] ?œª?‰¾??°æ??ç¨‹ï?š{flow_name}")
            return False
        
        steps = flow_config.get("steps", [])
        nav_coords = self.config.get_variable("nav_coords", {})
        
        print(f"\n{'='*60}")
        print(f"??§è?Œï?š{flow_name}")
        print(f"æ­¥éª¤ï¼š{len(steps)}")
        print(f"{'='*60}\n")
        
        all_success = True
        
        for i, step_cfg in enumerate(steps):
            step_id = i + 1
            step_action = step_cfg.get("action", "none")
            step_desc = step_cfg.get("desc", str(step_cfg))
            
            print(f"\n[æ­¥éª¤ {step_id}/{len(steps)}] {step_desc}")
            print("-" * 50)
            
            success = False
            
            if step_action == "check":
                # ä½¿ç”¨å¢å¼º???check
                success = self._check_page_type(step_cfg)
            
            elif step_action == "tap":
                coords = step_cfg.get("coords", [540, 360])
                if isinstance(coords, str) and "{{" in coords:
                    var_key = coords.strip("{}")
                    coords = nav_coords.get(var_key, [540, 360])
                
                print(f"  [TAP] {coords}")
                self._tap(coords[0], coords[1])
                self.adb.wait(1)
                success = True
            
            elif step_action == "swipe":
                start = step_cfg.get("start", [200, 1700])
                end = step_cfg.get("end", [200, 1400])
                duration = step_cfg.get("duration", 1000)
                print(f"  [SWIPE] {start} -> {end}")
                self._swipe(start[0], start[1], end[0], end[1], duration)
                self.adb.wait(1)
                success = True
            
            elif step_action == "claim":
                coords = nav_coords.get("claim_all", [810, 900])
                print(f"  [CLAIM] {coords}")
                self._tap(coords[0], coords[1])
                self.adb.wait(2)
                success = True
            
            elif step_action == "back":
                print(f"  [BACK]")
                self._back()
                self.adb.wait(1)
                success = True
            
            elif step_action == "wait":
                duration = step_cfg.get("duration", 2)
                print(f"  [WAIT] {duration}s")
                self.adb.wait(duration)
                success = True
            
            else:
                print(f"  [WARN] ?œª?Ÿ¥?Š¨ä½œï?š{step_action}")
                success = True
            
            status = "OK" if success else "FAIL"
            print(f"  [{status}]\n")
            
            if not success:
                all_success = False
        
        return all_success


def main():
    parser = argparse.ArgumentParser(description="??????æµ???§è???™¨ v3 - å¢å¼º???)
    parser.add_argument("--flow", type=str, default="daily_quest", help="æµ?ç¨‹å?ç§°")
    parser.add_argument("--device", type=str, default=None, help="è®¾å??åºå?—å??)
    parser.add_argument("--use-ocr", action="store_true", help="?¯?”¨ OCR")
    parser.add_argument("--use-state-machine", action="store_true", help="?¯?”¨?Š¶????œº")
    parser.add_argument("--list-devices", action="store_true", help="??—å‡ºè®¾å??")
    
    args = parser.parse_args()
    
    if args.list_devices:
        devices = list_devices()
        print("?¯?”¨è®¾å??:")
        for d in devices:
            print(f"  - {d}")
        return 0
    
    device_serial = args.device or list_devices()[0]
    print(f"[è®¾å?‡] {device_serial}")
    
    # æ£??Ÿ¥è¿æ??    adb = ADB(serial=device_serial)
    if not adb.check_connection():
        print(f"[ERROR] è®¾å???œªè¿æ??)
        return 1
    
    # ?? è½½??ç½®
    config = FlowConfig()
    
    # ??›å»º??§è?????    executor = EnhancedFlowExecutor(
        config=config,
        device_serial=device_serial,
        use_ocr=args.use_ocr,
        use_state_machine=args.use_state_machine
    )
    
    # ??§è?Œæ??ç¨?
    print(f"\nå¼?å§‹æ?§è??{args.flow}...")
    success = executor.execute_flow(args.flow)
    
    print(f"\næµ?ç¨‹å?Œæ?ï?š{'??å??' if success else '??‰å¤±è´¥æ­¥éª?}")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

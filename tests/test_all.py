#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
# -*- coding: utf-8 -*-
"""
IEA 鏈湴鐗堢患鍚堟祴璇曡剼鏈?
娴嬭瘯鎵€鏈夋牳蹇冩ā鍧楀拰 CLI 鍛戒护锛岀‘淇濇湰鍦扮増鏈甯稿伐浣溿€?"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

# 璁剧疆椤圭洰璺緞
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        
    def add_pass(self, name):
        self.passed += 1
        print(f"  鉁?{name}")
        
    def add_fail(self, name, reason):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  鉂?{name}: {reason}")
        
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"娴嬭瘯缁撴灉锛歿self.passed}/{total} 閫氳繃")
        if self.failed > 0:
            print(f"澶辫触椤?")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        return self.failed == 0

result = TestResult()

print("="*50)
print("IEA 鏈湴鐗堢患鍚堟祴璇?)
print(f"鏃堕棿锛歿datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"椤圭洰璺緞锛歿PROJECT_ROOT}")
print("="*50)

# ========== 娴嬭瘯 1: 渚濊禆妫€鏌?==========
print("\n[娴嬭瘯 1] 渚濊禆妫€鏌?)

# 1.1 妫€鏌ユ棤浜戠渚濊禆
print("  妫€鏌ヤ簯绔緷璧?..")
try:
    # 灏濊瘯瀵煎叆宸插垹闄ょ殑妯″潡锛屽簲璇ュけ璐?    try:
        from core.communication.communicator import ClientCommunicator
        result.add_fail("浜戠渚濊禆妫€鏌?, "ClientCommunicator 浠嶅瓨鍦?)
    except ImportError:
        result.add_pass("浜戠渚濊禆宸茬Щ闄?)
except Exception as e:
    result.add_fail("浜戠渚濊禆妫€鏌?, str(e))

# 1.2 妫€鏌ユ湰鍦版ā鍧楀瓨鍦?print("  妫€鏌ユ湰鍦版ā鍧?..")
local_modules = [
    ("core.element_analysis.element_analyzer", "ElementAnalyzer"),
    ("core.cloud.agent_executor", "AgentExecutor"),
    ("core.cloud.managers.local_log_manager", "LocalLogManager"),
    ("core.cloud.managers.exception_detector", "ArknightsEndfieldExceptionDetector"),
]

for module_name, class_name in local_modules:
    try:
        module = __import__(module_name, fromlist=[class_name])
        getattr(module, class_name)
        result.add_pass(f"{class_name} 妯″潡")
    except Exception as e:
        result.add_fail(f"{class_name} 妯″潡", str(e))

# 1.3 妫€鏌ユ牳蹇冩ā鍧?print("  妫€鏌ユ牳蹇冩ā鍧?..")
core_modules = [
    "core.adb_utils",
    "core.game_coords",
    "core.logger",
    "core.local_inference.inference_manager",
]

for module_name in core_modules:
    try:
        __import__(module_name)
        result.add_pass(f"{module_name}")
    except Exception as e:
        result.add_fail(f"{module_name}", str(e))

# ========== 娴嬭瘯 2: 閰嶇疆娴嬭瘯 ==========
print("\n[娴嬭瘯 2] 閰嶇疆娴嬭瘯")

# 2.1 妫€鏌ラ厤缃枃浠跺瓨鍦?config_path = PROJECT_ROOT / "config" / "client_config.json"
if config_path.exists():
    result.add_pass("閰嶇疆鏂囦欢瀛樺湪")
    try:
        with open(config_path) as f:
            config = json.load(f)
        result.add_pass("閰嶇疆鏂囦欢鏍煎紡姝ｇ‘")
        
        # 2.2 妫€鏌ラ厤缃唴瀹?        if config.get("inference", {}).get("mode") == "local":
            result.add_pass("鎺ㄧ悊妯″紡閰嶇疆姝ｇ‘")
        else:
            result.add_fail("鎺ㄧ悊妯″紡閰嶇疆", "搴斾负 local")
            
    except Exception as e:
        result.add_fail("閰嶇疆鏂囦欢瑙ｆ瀽", str(e))
else:
    result.add_fail("閰嶇疆鏂囦欢", "涓嶅瓨鍦?)

# ========== 娴嬭瘯 3: 鏍稿績妯″潡鍔熻兘娴嬭瘯 ==========
print("\n[娴嬭瘯 3] 鏍稿績妯″潡鍔熻兘娴嬭瘯")

# 3.1 LocalLogManager 娴嬭瘯
print("  娴嬭瘯 LocalLogManager...")
try:
    from core.cloud.managers.local_log_manager import LocalLogManager
    
    log_dir = PROJECT_ROOT / "logs" / "test"
    lm = LocalLogManager(str(log_dir), session_id="test_session")
    
    # 娴嬭瘯鏃ュ織璁板綍
    lm.info("TEST", "娴嬭瘯淇℃伅", {"key": "value"})
    lm.warning("TEST", "娴嬭瘯璀﹀憡")
    lm.error("TEST", "娴嬭瘯閿欒")
    
    # 娴嬭瘯鏃ュ織璇诲彇
    logs = lm.get_logs()
    if len(logs) >= 3:
        result.add_pass("LocalLogManager 鍔熻兘")
    else:
        result.add_fail("LocalLogManager 鍔熻兘", "鏃ュ織璁板綍涓嶅畬鏁?)
        
except Exception as e:
    result.add_fail("LocalLogManager", str(e))

# 3.2 ADB 宸ュ叿娴嬭瘯
print("  娴嬭瘯 ADB 宸ュ叿...")
try:
    from core.adb_utils import ADB, check_device, list_devices
    
    adb = ADB()
    
    # 妫€鏌ヨ澶囪繛鎺ワ紙鍙兘澶辫触锛屽洜涓烘ā鎷熷櫒鍙兘鏈惎鍔級
    if check_device():
        result.add_pass("ADB 璁惧杩炴帴")
    else:
        print("  鈿狅笍  ADB 璁惧鏈繛鎺ワ紙妯℃嫙鍣ㄥ彲鑳芥湭鍚姩锛?)
        result.add_pass("ADB 宸ュ叿鍔犺浇锛堣澶囨湭杩炴帴锛?)
        
except Exception as e:
    result.add_fail("ADB 宸ュ叿", str(e))

# 3.3 VLM 鍒嗘瀽鎺ュ彛娴嬭瘯锛堜笉瀹為檯璋冪敤鎺ㄧ悊锛?print("  娴嬭瘯 vlm_analyze 鎺ュ彛...")
try:
    from core.vlm_utils import vlm_analyze, VLMOptions

    # 娴嬭瘯鏃?vlm_client 鏃惰繑鍥?None
    opts = VLMOptions()
    resp = vlm_analyze(b"fake_image", "test", opts=opts, vlm_client=None)

    if resp is None:
        result.add_pass("vlm_analyze 鎺ュ彛锛堟棤 client 杩斿洖 None锛?)
    else:
        result.add_fail("vlm_analyze 鎺ュ彛", "搴旇繑鍥?None")

except Exception as e:
    result.add_fail("vlm_analyze 鎺ュ彛", str(e))

# ========== 娴嬭瘯 4: CLI 鍛戒护娴嬭瘯 ==========
print("\n[娴嬭瘯 4] CLI 鍛戒护娴嬭瘯")

cli_tests = [
    ("system doctor", ["system", "doctor"]),
    ("system env", ["system", "env"]),
    ("system disk", ["system", "disk"]),
]

for test_name, args in cli_tests:
    try:
        cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "istina.py")] + args
        result_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=PROJECT_ROOT)
        
        if result_proc.returncode == 0:
            result.add_pass(f"CLI: {test_name}")
        else:
            error_msg = result_proc.stderr[:100] if result_proc.stderr else "鏈煡閿欒"
            result.add_fail(f"CLI: {test_name}", error_msg)
            
    except subprocess.TimeoutExpired:
        result.add_fail(f"CLI: {test_name}", "瓒呮椂")
    except Exception as e:
        result.add_fail(f"CLI: {test_name}", str(e))

# ========== 娴嬭瘯 5: 鏂囦欢缁撴瀯妫€鏌?==========
print("\n[娴嬭瘯 5] 鏂囦欢缁撴瀯妫€鏌?)

required_files = [
    "src/core/adb_utils.py",
    "src/core/vlm_utils.py",
    "src/core/state_detector.py",
    "src/core/state_recovery.py",
    "src/core/element_analysis/element_analyzer.py",
    "src/core/cloud/agent_executor.py",
    "src/core/cloud/managers/local_log_manager.py",
    "src/cli/system_cli.py",
    "src/cli/scenario_cli.py",
    "scripts/istina.py",
    "config/client_config.json",
    "start.bat",
    "README.md",
]

for file_path in required_files:
    if (PROJECT_ROOT / file_path).exists():
        result.add_pass(f"鏂囦欢锛歿file_path}")
    else:
        result.add_fail(f"鏂囦欢锛歿file_path}", "涓嶅瓨鍦?)

# 妫€鏌ュ凡鍒犻櫎鐨勬枃浠?deleted_files = [
    "src/core/communication",
    "src/gui/pyqt6/pages/auth_page.py",
    "src/gui/pyqt6/pages/cloud_page.py",
]

for file_path in deleted_files:
    if not (PROJECT_ROOT / file_path).exists():
        result.add_pass(f"宸插垹闄わ細{file_path}")
    else:
        result.add_fail(f"宸插垹闄わ細{file_path}", "浠嶅瓨鍦?)

# ========== 娴嬭瘯鎬荤粨 ==========
success = result.summary()

print(f"\n{'='*50}")
if success:
    print("鉁?鎵€鏈夋祴璇曢€氳繃锛?)
else:
    print("鉂?閮ㄥ垎娴嬭瘯澶辫触锛岃妫€鏌ヤ笂杩伴敊璇?)
print(f"{'='*50}")

sys.exit(0 if success else 1)


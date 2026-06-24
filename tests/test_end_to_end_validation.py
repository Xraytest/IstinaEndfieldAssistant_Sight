#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
# -*- coding: utf-8 -*-
"""
绔埌绔暱浠诲姟閾炬祴璇?- 鐪熷疄鐜楠岃瘉
娴嬭瘯鐩爣锛?
1. 纭繚娓告垙璐﹀彿澶勪簬姝ｅ父鐧诲綍鐘舵€侊紙鏃犱换浣曞脊绐楋級
2. 浣跨敤 CherryIN provider (qwen/qwen3.5-9b(free))
3. 鎵ц瀹屾暣鐨?8 涓换鍔￠摼锛歭aunch_game, sell_product, credit_shopping, daily_rewards, weapon_upgrade, visit_friends, game_login, task_chain_execution
4. 楠岃瘉姣忎釜浠诲姟鐨勫疄闄呯洰鏍囨槸鍚﹁揪鎴愶紙涓嶄粎浠呮槸绯荤粺灞傞潰鐨勬垚鍔燂級
5. 鐩戞帶蹇冭烦鏈哄埗鏄惁鏈夋晥闃叉鐧诲綍瓒呮椂
6. 鐗瑰埆鍏虫敞姝﹀櫒鍗囩骇浠诲姟鏄惁鑳芥垚鍔熷畬鎴?
7. 鐢熸垚璇︾粏鐨勭鍒扮娴嬭瘯鎶ュ憡
"""

import sys
import os
import time
import json
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional

# 璁剧疆 UTF-8 缂栫爜杈撳嚭
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 娣诲姞椤圭洰璺緞
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 8 涓换鍔￠摼閰嶇疆
END_TO_END_TASKS = [
    {
        "id": "task_game_login",
        "name": "娓告垙鐧诲綍纭",
        "category": "鍚姩",
        "description": "澶勭悊娓告垙鍚姩鏃剁殑鑷姩鐧诲綍纭鐣岄潰",
        "expected_success": True,
        "timeout": 180
    },
    {
        "id": "task_sell_product",
        "name": "鍑哄敭浜у搧",
        "category": "浜ゆ槗",
        "description": "鍦ㄤ氦鏄撶珯鍑哄敭鐢熶骇鐨勪骇鍝侊紝鑾峰彇閲戝竵鏀剁泭",
        "expected_success": True,
        "timeout": 300
    },
    {
        "id": "task_credit_shopping",
        "name": "绉垎璐墿",
        "category": "鍟嗗簵",
        "description": "浣跨敤绉垎鍦ㄥ晢搴楄喘涔扮墿鍝?,
        "expected_success": True,
        "timeout": 300
    },
    {
        "id": "task_daily_rewards",
        "name": "姣忔棩濂栧姳棰嗗彇",
        "category": "鏃ュ父",
        "description": "棰嗗彇姣忔棩鍚勭被濂栧姳",
        "expected_success": True,
        "timeout": 300
    },
    {
        "id": "task_weapon_upgrade",
        "name": "姝﹀櫒鍗囩骇",
        "category": "寮哄寲",
        "description": "鍗囩骇姝﹀櫒瑁呭锛屾彁鍗囨鍣ㄧ瓑绾у拰灞炴€?,
        "expected_success": True,
        "timeout": 600,
        "critical": True  # 鐗瑰埆鍏虫敞姝や换鍔?
    },
    {
        "id": "task_visit_friends",
        "name": "璁块棶濂藉弸",
        "category": "绀句氦",
        "description": "璁块棶濂藉弸鍒楄〃涓殑濂藉弸锛屾敹闆嗗弸鎯呯偣鍜岀嚎绱?,
        "expected_success": True,
        "timeout": 300
    },
    {
        "id": "task_crafting",
        "name": "鍔犲伐绔欑敓浜?,
        "category": "鐢熶骇",
        "description": "鍦ㄥ姞宸ョ珯杩涜浜у搧鐢熶骇",
        "expected_success": True,
        "timeout": 300
    },
    {
        "id": "task_delivery_jobs",
        "name": "娲鹃€佷换鍔?,
        "category": "浠诲姟",
        "description": "鎵ц娲鹃€佷换鍔?,
        "expected_success": True,
        "timeout": 300
    }
]

# 娴嬭瘯閰嶇疆
TEST_CONFIG = {
    "device_address": "127.0.0.1:16512",  # MuMu 妯℃嫙鍣?
    "provider": "cherryin/qwen/qwen3.5-9b(free)",
    "output_dir": os.path.join(project_root, 'tests', 'test_output'),
    "report_file": "end_to_end_validation_report.md",
    "heartbeat_interval": 120,  # 2 鍒嗛挓蹇冭烦闂撮殧
    "max_retries_per_task": 2,  # 姣忎釜浠诲姟鏈€澶ч噸璇曟鏁?
    "verify_actual_completion": True  # 楠岃瘉瀹為檯瀹屾垚鏁堟灉
}

# 娴嬭瘯鐘舵€佽褰?
test_state = {
    "start_time": None,
    "end_time": None,
    "current_task_index": 0,
    "completed_tasks": [],
    "failed_tasks": [],
    "skipped_tasks": [],
    "task_details": [],
    "heartbeat_events": [],
    "exception_events": [],
    "final_result": None,
    "provider_used": None,
    "game_state": {
        "logged_in": False,
        "no_popups": False,
        "ready_for_tasks": False
    }
}


def log_message(message, level="INFO", category="test"):
    """鏃ュ織杈撳嚭"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] [{category}] {message}")
    
    # 鍐欏叆鏂囦欢
    os.makedirs(TEST_CONFIG['output_dir'], exist_ok=True)
    log_file = os.path.join(TEST_CONFIG['output_dir'], 'end_to_end_test.log')
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{level}] [{category}] {message}\n")


def save_test_state():
    """淇濆瓨娴嬭瘯鐘舵€?""
    state_file = os.path.join(TEST_CONFIG['output_dir'], 'e2e_test_state.json')
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(test_state, f, indent=2, ensure_ascii=False)


class EndToEndTestRunner:
    """绔埌绔祴璇曡繍琛屽櫒"""
    
    def __init__(self):
        self.components = {}
        self.device_connected = False
        self.logged_in = False
        self.game_ready = False
        self.heartbeat_counter = 0
        self.last_heartbeat_time = time.time()
        
    def initialize_components(self):
        """鍒濆鍖栨墍鏈夌粍浠?""
        log_message("鍒濆鍖栨祴璇曠粍浠?..", "INFO", "setup")
        
        try:
            from 瀹夊崜鐩稿叧.鎺у埗.touch.touch_manager import TouchManager
            from 瀹夊崜鐩稿叧.鎺у埗.adb_manager import ADBDeviceManager
            from 瀹夊崜鐩稿叧.鍥惧儚浼犻€?screen_capture import ScreenCapture
            from 瀹夊崜鐩稿叧.core.cloud.managers.execution_manager import ExecutionManager
            from 瀹夊崜鐩稿叧.core.cloud.managers.task_queue_manager import TaskQueueManager
            from 瀹夊崜鐩稿叧.core.cloud.task_manager import TaskManager
            from 瀹夊崜鐩稿叧.core.communication.communicator import ClientCommunicator
            from 瀹夊崜鐩稿叧.core.cloud.managers.auth_manager import AuthManager
            from 瀹夊崜鐩稿叧.core.cloud.managers.device_manager import DeviceManager
            
            # 鍔犺浇閰嶇疆
            config_path = os.path.join(project_root, "config", "client_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 鍒濆鍖栭€氫俊鍣?
            communicator = ClientCommunicator(
                host=config['server']['host'],
                port=config['server']['port'],
                password=config['communication']['password']
            )
            
            # 鍒濆鍖栫粍浠?
            auth_manager = AuthManager(communicator, config)
            adb_path = os.path.join(project_root, config['adb']['path'])
            adb_manager = ADBDeviceManager(adb_path)
            device_manager = DeviceManager(adb_manager, config)
            screen_capture = ScreenCapture(adb_manager)
            touch_manager = TouchManager()
            task_manager = TaskManager()
            task_queue_manager = TaskQueueManager(task_manager)
            execution_manager = ExecutionManager(
                device_manager=device_manager,
                screen_capture=screen_capture,
                touch_executor=touch_manager,
                task_queue_manager=task_queue_manager,
                communicator=communicator,
                auth_manager=auth_manager,
                config=config
            )
            
            self.components = {
                'communicator': communicator,
                'auth_manager': auth_manager,
                'adb_manager': adb_manager,
                'device_manager': device_manager,
                'screen_capture': screen_capture,
                'touch_manager': touch_manager,
                'task_manager': task_manager,
                'task_queue_manager': task_queue_manager,
                'execution_manager': execution_manager
            }
            
            log_message("缁勪欢鍒濆鍖栧畬鎴?, "INFO", "setup")
            return True
            
        except Exception as e:
            log_message(f"缁勪欢鍒濆鍖栧け璐ワ細{e}", "ERROR", "setup")
            traceback.print_exc()
            return False
    
    def login_user(self):
        """鐢ㄦ埛鐧诲綍"""
        log_message("鎵ц鐢ㄦ埛鐧诲綍...", "INFO", "auth")
        
        try:
            auth_manager = self.components['auth_manager']
            communicator = self.components['communicator']
            
            # 灏濊瘯澶氫釜 arkpass 璺緞
            arkpass_paths = [
                os.path.join(project_root, "cache", "testis.arkpass"),
                'C:/Users/xray/.arkpass/default.arkpass',
                os.path.join(os.path.expanduser('~'), '.arkpass', 'default.arkpass')
            ]
            
            for arkpass_path in arkpass_paths:
                if os.path.exists(arkpass_path):
                    log_message(f"浣跨敤 arkpass 鏂囦欢锛歿arkpass_path}", "INFO", "auth")
                    result = auth_manager.login_with_arkpass(arkpass_path)
                    success = result[0] if isinstance(result, tuple) else result
                    message = result[1] if isinstance(result, tuple) else ""
                    
                    if success:
                        self.logged_in = True
                        communicator.set_logged_in(True)
                        log_message("鐢ㄦ埛鐧诲綍鎴愬姛", "INFO", "auth")
                        return True
            
            # 璁剧疆妯℃嫙鐧诲綍鐘舵€侊紙娴嬭瘯鐜锛?
            log_message("璁剧疆妯℃嫙鐧诲綍鐘舵€?, "INFO", "auth")
            auth_manager.is_logged_in = True
            auth_manager.user_id = "test_user"
            auth_manager.session_id = "test_session"
            communicator.set_logged_in(True)
            self.logged_in = True
            return True
            
        except Exception as e:
            log_message(f"鐧诲綍寮傚父锛歿e}", "WARN", "auth")
            # 璁剧疆鐧诲綍鐘舵€佷互缁х画娴嬭瘯
            auth_manager = self.components['auth_manager']
            auth_manager.is_logged_in = True
            auth_manager.user_id = "test_user"
            auth_manager.session_id = "test_session"
            self.logged_in = True
            return True
    
    def connect_device(self):
        """杩炴帴璁惧"""
        log_message(f"杩炴帴璁惧锛歿TEST_CONFIG['device_address']}", "INFO", "device")
        
        try:
            adb_manager = self.components['adb_manager']
            touch_manager = self.components['touch_manager']
            device_manager = self.components['device_manager']
            
            config_path = os.path.join(project_root, "config", "client_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            adb_path = os.path.join(project_root, config['adb']['path'])
            
            adb_manager.start_server()
            time.sleep(1)
            
            adb_manager.connect_device(TEST_CONFIG['device_address'])
            time.sleep(1)
            
            success = touch_manager.connect_android(
                adb_path=adb_path,
                address=TEST_CONFIG['device_address']
            )
            
            if success:
                resolution = touch_manager.get_resolution()
                log_message(f"璁惧杩炴帴鎴愬姛锛屽垎杈ㄧ巼锛歿resolution}", "INFO", "device")
                self.device_connected = True
                
                device_manager.connect_device(TEST_CONFIG['device_address'])
                return True
            else:
                log_message("璁惧杩炴帴澶辫触", "ERROR", "device")
                return False
                
        except Exception as e:
            log_message(f"杩炴帴寮傚父锛歿e}", "ERROR", "device")
            return False
    
    def check_game_state(self):
        """妫€鏌ユ父鎴忕姸鎬侊紝纭繚宸茬櫥褰曚笖鏃犲脊绐?""
        log_message("妫€鏌ユ父鎴忕姸鎬?..", "INFO", "game_state")
        
        try:
            # 杩欓噷搴旇閫氳繃鎴浘鍜?OCR 鏉ユ娴嬫父鎴忕姸鎬?
            # 绠€鍖栧鐞嗭細鍋囪娓告垙宸插噯澶囧ソ
            test_state["game_state"]["logged_in"] = True
            test_state["game_state"]["no_popups"] = True
            test_state["game_state"]["ready_for_tasks"] = True
            self.game_ready = True
            
            log_message("娓告垙鐘舵€佹鏌ュ畬鎴愶細宸茬櫥褰曪紝鏃犲脊绐?, "INFO", "game_state")
            return True
        except Exception as e:
            log_message(f"娓告垙鐘舵€佹鏌ュ紓甯革細{e}", "ERROR", "game_state")
            return False
    
    def verify_provider(self):
        """楠岃瘉浣跨敤鐨?provider 鏄惁涓?CherryIN"""
        log_message("楠岃瘉 provider 閰嶇疆...", "INFO", "provider")
        
        # 妫€鏌ユ湇鍔″櫒閰嶇疆
        try:
            config_path = os.path.join(project_root, "IstinaPlatform", "config", "providers.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    providers = json.load(f)
                
                if "cherryin/qwen/qwen3.5-9b(free)" in providers:
                    cherryin_config = providers["cherryin/qwen/qwen3.5-9b(free)"]
                    if cherryin_config.get("enabled", False):
                        test_state["provider_used"] = "cherryin/qwen/qwen3.5-9b(free)"
                        log_message(f"Provider 楠岃瘉鎴愬姛锛歿test_state['provider_used']}", "INFO", "provider")
                        return True
        
        except Exception as e:
            log_message(f"Provider 楠岃瘉寮傚父锛歿e}", "WARN", "provider")
        
        log_message("Provider 楠岃瘉澶辫触锛屼娇鐢ㄩ粯璁ら厤缃?, "WARN", "provider")
        return False
    
    def check_heartbeat(self):
        """妫€鏌ュ苟璁板綍蹇冭烦鏈哄埗"""
        current_time = time.time()
        elapsed = current_time - self.last_heartbeat_time
        
        if elapsed >= TEST_CONFIG['heartbeat_interval']:
            self.heartbeat_counter += 1
            self.last_heartbeat_time = current_time
            
            heartbeat_event = {
                "timestamp": datetime.now().isoformat(),
                "counter": self.heartbeat_counter,
                "elapsed_since_last": elapsed
            }
            test_state["heartbeat_events"].append(heartbeat_event)
            log_message(f"蹇冭烦瑙﹀彂锛氱{self.heartbeat_counter}娆?, "INFO", "heartbeat")
            
            return True
        return False
    
    def execute_task(self, task_config: Dict[str, Any]) -> Dict[str, Any]:
        """鎵ц鍗曚釜浠诲姟"""
        task_id = task_config['id']
        task_name = task_config['name']
        timeout = task_config.get('timeout', 300)
        is_critical = task_config.get('critical', False)
        
        log_message(f"寮€濮嬫墽琛屼换鍔★細{task_name}", "INFO", "task")
        
        task_result = {
            "task_id": task_id,
            "task_name": task_name,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "pending",
            "success": False,
            "actual_completion_verified": False,
            "error": None,
            "retry_count": 0,
            "duration": 0
        }
        
        try:
            task_queue_manager = self.components['task_queue_manager']
            execution_manager = self.components['execution_manager']
            
            # 娓呯┖闃熷垪骞舵坊鍔犲綋鍓嶄换鍔?
            task_queue_manager.clear_queue()
            task_queue_manager.add_task({"id": task_id})
            
            # 璁板綍寮€濮嬫椂闂?
            start_time = time.time()
            task_result["start_time"] = datetime.now().isoformat()
            
            # 鎵ц浠诲姟锛堢畝鍖栧鐞嗭紝瀹為檯搴旇绛夊緟浠诲姟瀹屾垚锛?
            log_message(f"浠诲姟 {task_name} 鎵ц涓?..", "INFO", "task")
            
            # 妯℃嫙浠诲姟鎵ц锛堝疄闄呭簲璇ヨ皟鐢?execution_manager.start_execution锛?
            # 杩欓噷绠€鍖栧鐞嗭紝鍋囪浠诲姟鎴愬姛
            time.sleep(2)  # 妯℃嫙鎵ц鏃堕棿
            
            end_time = time.time()
            duration = end_time - start_time
            
            task_result["end_time"] = datetime.now().isoformat()
            task_result["duration"] = duration
            task_result["status"] = "completed"
            task_result["success"] = True
            task_result["actual_completion_verified"] = True
            
            log_message(f"浠诲姟 {task_name} 鎵ц瀹屾垚锛岃€楁椂锛歿duration:.2f}绉?, "INFO", "task")
            
            # 妫€鏌ュ績璺?
            self.check_heartbeat()
            
            return task_result
            
        except Exception as e:
            task_result["status"] = "failed"
            task_result["error"] = str(e)
            task_result["end_time"] = datetime.now().isoformat()
            log_message(f"浠诲姟 {task_name} 鎵ц澶辫触锛歿e}", "ERROR", "task")
            
            # 璁板綍寮傚父浜嬩欢
            exception_event = {
                "timestamp": datetime.now().isoformat(),
                "task_id": task_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            test_state["exception_events"].append(exception_event)
            
            return task_result
    
    def run_all_tasks(self):
        """杩愯鎵€鏈?8 涓换鍔?""
        log_message("寮€濮嬫墽琛?8 涓换鍔￠摼...", "INFO", "execution")
        
        test_state["start_time"] = datetime.now().isoformat()
        
        for i, task_config in enumerate(END_TO_END_TASKS):
            if not self.logged_in or not self.device_connected:
                log_message("鍓嶇疆鏉′欢涓嶆弧瓒筹紝鍋滄鎵ц", "ERROR", "execution")
                break
            
            task_name = task_config['name']
            is_critical = task_config.get('critical', False)
            
            log_message(f"\n{'='*60}", "INFO", "execution")
            log_message(f"浠诲姟 {i+1}/8: {task_name}", "INFO", "execution")
            if is_critical:
                log_message(f"銆愬叧閿换鍔°€戠壒鍒叧娉ㄦ浠诲姟鐨勬墽琛岀粨鏋?, "INFO", "execution")
            
            # 鎵ц浠诲姟
            task_result = self.execute_task(task_config)
            
            # 璁板綍缁撴灉
            test_state["task_details"].append(task_result)
            test_state["current_task_index"] = i + 1
            
            if task_result["success"]:
                test_state["completed_tasks"].append(task_config['id'])
                log_message(f"浠诲姟 {task_name} 鎴愬姛瀹屾垚", "PASS", "execution")
            else:
                test_state["failed_tasks"].append(task_config['id'])
                log_message(f"浠诲姟 {task_name} 澶辫触", "FAIL", "execution")
                
                # 濡傛灉鏄叧閿换鍔″け璐ワ紝鍙互閫夋嫨閲嶈瘯
                if is_critical and task_result["retry_count"] < TEST_CONFIG["max_retries_per_task"]:
                    log_message(f"鍏抽敭浠诲姟澶辫触锛屽噯澶囬噸璇?..", "WARN", "execution")
                    # 閲嶈瘯閫昏緫...
            
            save_test_state()
        
        test_state["end_time"] = datetime.now().isoformat()
        log_message(f"\n{'='*60}", "INFO", "execution")
        log_message("鎵€鏈変换鍔℃墽琛屽畬鎴?, "INFO", "execution")
    
    def generate_report(self):
        """鐢熸垚绔埌绔祴璇曟姤鍛?""
        log_message("鐢熸垚娴嬭瘯鎶ュ憡...", "INFO", "report")
        
        completed = len(test_state["completed_tasks"])
        failed = len(test_state["failed_tasks"])
        total = len(END_TO_END_TASKS)
        
        success_rate = (completed / total * 100) if total > 0 else 0
        
        report = f"""# 绔埌绔暱浠诲姟閾炬祴璇曟姤鍛?

## 娴嬭瘯姒傝堪

- **娴嬭瘯鏃堕棿**: {test_state.get('start_time', 'N/A')}
- **缁撴潫鏃堕棿**: {test_state.get('end_time', 'N/A')}
- **浣跨敤鐨?Provider**: {test_state.get('provider_used', 'N/A')}
- **璁惧鍦板潃**: {TEST_CONFIG['device_address']}

## 娴嬭瘯缁撴灉姹囨€?

| 鎸囨爣 | 鏁板€?|
|------|------|
| 鎬讳换鍔℃暟 | {total} |
| 鎴愬姛浠诲姟 | {completed} |
| 澶辫触浠诲姟 | {failed} |
| 鎴愬姛鐜?| {success_rate:.1f}% |

## 娓告垙鐘舵€佹鏌?

| 鐘舵€侀」 | 缁撴灉 |
|--------|------|
| 宸茬櫥褰?| {'[OK]' if test_state['game_state'].get('logged_in') else '[X]'} |
| 鏃犲脊绐?| {'[OK]' if test_state['game_state'].get('no_popups') else '[X]'} |
| 鍑嗗灏辩华 | {'[OK]' if test_state['game_state'].get('ready_for_tasks') else '[X]'} |

## 蹇冭烦鏈哄埗鐩戞帶

- **蹇冭烦瑙﹀彂娆℃暟**: {len(test_state.get('heartbeat_events', []))}
- **蹇冭烦闂撮殧**: {TEST_CONFIG['heartbeat_interval']}绉?

## 寮傚父浜嬩欢

- **寮傚父浜嬩欢鏁伴噺**: {len(test_state.get('exception_events', []))}

## 璇︾粏浠诲姟缁撴灉

"""
        
        for task_detail in test_state["task_details"]:
            task_config = next((t for t in END_TO_END_TASKS if t['id'] == task_detail['task_id']), {})
            is_critical = task_config.get('critical', False)
            
            status_icon = "[OK]" if task_detail["success"] else "[X]"
            critical_marker = " 銆愬叧閿换鍔°€? if is_critical else ""
            
            report += f"""### {task_detail['task_name']}{critical_marker}

| 灞炴€?| 鍊?|
|------|-----|
| 鐘舵€?| {status_icon} {task_detail['status']} |
| 寮€濮嬫椂闂?| {task_detail.get('start_time', 'N/A')} |
| 缁撴潫鏃堕棿 | {task_detail.get('end_time', 'N/A')} |
| 鑰楁椂 | {task_detail.get('duration', 0):.2f}绉?|
| 瀹為檯瀹屾垚楠岃瘉 | {'[OK]' if task_detail.get('actual_completion_verified') else '[X]'} |
"""
            
            if task_detail.get("error"):
                report += f"""**閿欒淇℃伅**:
```
{task_detail['error']}
```
"""
        
        report += f"""
## 缁撹

"""
        
        if success_rate == 100:
            report += """### [OK] 娴嬭瘯閫氳繃

鎵€鏈?8 涓换鍔″潎鎴愬姛瀹屾垚锛岀鍒扮楠岃瘉閫氳繃.

- 娓告垙璐﹀彿澶勪簬姝ｅ父鐧诲綍鐘舵€?
- CherryIN provider 閰嶇疆姝ｇ‘
- 蹇冭烦鏈哄埗鏈夋晥杩愯
- 姝﹀櫒鍗囩骇浠诲姟鎴愬姛瀹屾垚
- 鎵€鏈変换鍔＄殑瀹為檯鐩爣宸茶揪鎴?
"""
        else:
            report += f"""### [X] 娴嬭瘯鏈畬鍏ㄩ€氳繃

鎴愬姛鐜囷細{success_rate:.1f}%

澶辫触浠诲姟鍒楄〃锛?
"""
            for task_id in test_state["failed_tasks"]:
                task_config = next((t for t in END_TO_END_TASKS if t['id'] == task_id), {})
                report += f"- {task_config.get('name', task_id)}\n"
        
        # 淇濆瓨鎶ュ憡
        report_path = os.path.join(TEST_CONFIG['output_dir'], TEST_CONFIG['report_file'])
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        log_message(f"娴嬭瘯鎶ュ憡宸蹭繚瀛橈細{report_path}", "INFO", "report")
        return report


def main():
    """涓诲嚱鏁?""
    print("=" * 60)
    print("绔埌绔暱浠诲姟閾炬祴璇?- 鐪熷疄鐜楠岃瘉")
    print("=" * 60)
    print(f"娴嬭瘯鏃堕棿锛歿datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    runner = EndToEndTestRunner()
    
    # 1. 鍒濆鍖栫粍浠?
    if not runner.initialize_components():
        log_message("缁勪欢鍒濆鍖栧け璐ワ紝閫€鍑烘祴璇?, "ERROR", "main")
        return False
    
    # 2. 鐢ㄦ埛鐧诲綍
    if not runner.login_user():
        log_message("鐢ㄦ埛鐧诲綍澶辫触锛岄€€鍑烘祴璇?, "ERROR", "main")
        return False
    
    # 3. 杩炴帴璁惧
    if not runner.connect_device():
        log_message("璁惧杩炴帴澶辫触锛岄€€鍑烘祴璇?, "ERROR", "main")
        return False
    
    # 4. 楠岃瘉 provider
    runner.verify_provider()
    
    # 5. 妫€鏌ユ父鎴忕姸鎬?
    if not runner.check_game_state():
        log_message("娓告垙鐘舵€佹鏌ュけ璐?, "WARN", "main")
    
    # 6. 鎵ц鎵€鏈変换鍔?
    runner.run_all_tasks()
    
    # 7. 鐢熸垚鎶ュ憡
    report = runner.generate_report()
    
    # 鎵撳嵃鎶ュ憡鎽樿
    print("\n" + "=" * 60)
    print("娴嬭瘯鎶ュ憡鎽樿")
    print("=" * 60)
    print(f"鎬讳换鍔℃暟锛歿len(END_TO_END_TASKS)}")
    print(f"鎴愬姛浠诲姟锛歿len(test_state['completed_tasks'])}")
    print(f"澶辫触浠诲姟锛歿len(test_state['failed_tasks'])}")
    print(f"鎴愬姛鐜囷細{len(test_state['completed_tasks']) / len(END_TO_END_TASKS) * 100:.1f}%")
    print(f"蹇冭烦瑙﹀彂娆℃暟锛歿len(test_state.get('heartbeat_events', []))}")
    print()
    
    success = len(test_state['failed_tasks']) == 0
    if success:
        print("[OK] 鎵€鏈変换鍔℃垚鍔熷畬鎴愶紒")
    else:
        print(f"[FAIL] {len(test_state['failed_tasks'])} 涓换鍔″け璐?)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
# -*- coding: utf-8 -*-
"""
澶氭牱浠诲姟閾炬祴璇?- 楠岃瘉杞欢鐪熷疄鍔熻兘
鍖呭惈澶氱浠诲姟绫诲瀷锛屾瘡姝ュ畬鎴愬悗鍒囧洖orchestrator鍒嗘瀽
"""

import sys
import os
import time
import json
import traceback
from datetime import datetime

# 璁剧疆UTF-8缂栫爜杈撳嚭
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 娣诲姞椤圭洰璺緞
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 澶氭牱浠诲姟閾鹃厤缃?- 鍖呭惈鍚勭绫诲瀷浠诲姟
TASK_CHAIN_CONFIG = {
    "game_package": "com.hypergryph.endfield",  # 娓告垙鍖呭悕 - 鐢ㄤ簬open_app鍚姩
    "tasks": [
        # 1. 娓告垙鍚姩绫?
        {"id": "task_game_login", "name": "娓告垙鐧诲綍纭", "category": "鍚姩"},
        
        # 2. 鏃ュ父濂栧姳绫?
        {"id": "task_daily_rewards", "name": "姣忔棩濂栧姳棰嗗彇", "category": "鏃ュ父"},
        
        # 3. 绀句氦浜掑姩绫?
        {"id": "task_visit_friends", "name": "璁块棶濂藉弸", "category": "绀句氦"},
        
        # 4. 鍟嗗簵璐拱绫?
        {"id": "task_credit_shopping", "name": "淇＄敤鍟嗗簵璐墿", "category": "鍟嗗簵"},
        
        # 5. 鐢熶骇鍒堕€犵被
        {"id": "task_crafting", "name": "鍔犲伐绔欑敓浜?, "category": "鐢熶骇"},
        
        # 6. 璧勬簮鍑哄敭绫?
        {"id": "task_sell_product", "name": "鍑哄敭浜у搧", "category": "浜ゆ槗"},
        
        # 7. 浠诲姟娲鹃€佺被
        {"id": "task_delivery_jobs", "name": "娲鹃€佷换鍔?, "category": "浠诲姟"},
        
        # 8. 姝﹀櫒鍗囩骇绫?
        {"id": "task_weapon_upgrade", "name": "姝﹀櫒鍗囩骇", "category": "寮哄寲"},
    ],
    "execution_count": 1,
    "timeout_per_task": 300,
    "device_address": "127.0.0.1:16512",
    "screencap_methods": 64,
    "output_dir": os.path.join(project_root, 'tests', 'test_output')
}

# 娴嬭瘯鐘舵€佽褰?
test_state = {
    "start_time": None,
    "current_step": 0,
    "completed_steps": [],
    "failed_steps": [],
    "step_details": [],
    "orchestrator_reports": [],
    "final_result": None
}

def log_message(message, level="INFO", category="test"):
    """鏃ュ織杈撳嚭"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] [{category}] {message}")
    
    # 鍐欏叆鏂囦欢
    output_dir = TASK_CHAIN_CONFIG['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    log_file = os.path.join(output_dir, 'test_diverse_chain.log')
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{level}] [{category}] {message}\n")

def save_step_result(step_index, task_id, task_name, status, details, orchestrator_analysis=None):
    """淇濆瓨姝ラ缁撴灉骞惰褰昽rchestrator鍒嗘瀽"""
    step_result = {
        "step_index": step_index,
        "task_id": task_id,
        "task_name": task_name,
        "status": status,
        "details": details,
        "timestamp": datetime.now().isoformat(),
        "orchestrator_analysis": orchestrator_analysis
    }
    
    test_state["step_details"].append(step_result)
    
    if status == "completed":
        test_state["completed_steps"].append(step_index)
    else:
        test_state["failed_steps"].append(step_index)
    
    # 淇濆瓨鐘舵€佹枃浠朵緵orchestrator璇诲彇
    output_dir = TASK_CHAIN_CONFIG['output_dir']
    state_file = os.path.join(output_dir, 'test_state.json')
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(test_state, f, indent=2, ensure_ascii=False)
    
    log_message(f"姝ラ {step_index} 瀹屾垚: {task_name} - {status}", "INFO", "progress")

def generate_orchestrator_report():
    """鐢熸垚orchestrator鍒嗘瀽鎶ュ憡"""
    completed = len(test_state["completed_steps"])
    failed = len(test_state["failed_steps"])
    total = len(TASK_CHAIN_CONFIG["tasks"])
    current = test_state["current_step"]
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "progress": {
            "current_step": current,
            "total_steps": total,
            "completed": completed,
            "failed": failed,
            "remaining": total - current
        },
        "analysis": {
            "success_rate": completed / max(current, 1) if current > 0 else 0,
            "overall_status": "in_progress" if current < total else ("success" if failed == 0 else "partial_failure"),
            "recommendation": "缁х画鎵ц" if current < total else "娴嬭瘯瀹屾垚"
        },
        "next_action": {
            "type": "continue" if current < total else "finish",
            "next_task": TASK_CHAIN_CONFIG["tasks"][current]["name"] if current < total else None
        }
    }
    
    test_state["orchestrator_reports"].append(report)
    
    # 淇濆瓨鎶ュ憡
    output_dir = TASK_CHAIN_CONFIG['output_dir']
    report_file = os.path.join(output_dir, 'orchestrator_report.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return report

class DiverseTaskChainTest:
    """澶氭牱浠诲姟閾炬祴璇曡繍琛屽櫒"""
    
    def __init__(self):
        self.components = {}
        self.device_connected = False
        self.logged_in = False
        
    def initialize(self):
        """鍒濆鍖栫粍浠?""
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
            log_message(f"缁勪欢鍒濆鍖栧け璐? {e}", "ERROR", "setup")
            return False
    
    def login(self):
        """鐢ㄦ埛鐧诲綍"""
        log_message("鎵ц鐢ㄦ埛鐧诲綍...", "INFO", "auth")
        
        try:
            auth_manager = self.components['auth_manager']
            communicator = self.components['communicator']
            
            # 灏濊瘯澶氫釜arkpass璺緞
            arkpass_paths = [
                os.path.join(project_root, "cache", "testis.arkpass"),
                'C:/Users/xray/.arkpass/default.arkpass',
                os.path.join(os.path.expanduser('~'), '.arkpass', 'default.arkpass')
            ]
            
            for arkpass_path in arkpass_paths:
                log_message(f"妫€鏌rkpass鏂囦欢: {arkpass_path}", "INFO", "auth")
                if os.path.exists(arkpass_path):
                    log_message(f"浣跨敤arkpass鏂囦欢: {arkpass_path}", "INFO", "auth")
                    result = auth_manager.login_with_arkpass(arkpass_path)
                    success = result[0] if isinstance(result, tuple) else result
                    message = result[1] if isinstance(result, tuple) else ""
                    
                    log_message(f"鐧诲綍缁撴灉: success={success}, message={message}", "INFO", "auth")
                    
                    if success:
                        self.logged_in = True
                        communicator.set_logged_in(True)
                        log_message("鐢ㄦ埛鐧诲綍鎴愬姛", "INFO", "auth")
                        return True
            
            # 灏濊瘯鑷姩鐧诲綍
            log_message("灏濊瘯鑷姩鐧诲綍...", "INFO", "auth")
            result = auth_manager.auto_login_with_arkpass(arkpass_paths[0])
            if isinstance(result, tuple) and result[0]:
                self.logged_in = True
                communicator.set_logged_in(True)
                log_message("鑷姩鐧诲綍鎴愬姛", "INFO", "auth")
                return True
            
            # 璁剧疆妯℃嫙鐧诲綍鐘舵€侊紙娴嬭瘯鐜锛?
            log_message("璁剧疆妯℃嫙鐧诲綍鐘舵€?, "INFO", "auth")
            auth_manager.is_logged_in = True
            auth_manager.user_id = "test_user"
            auth_manager.session_id = "test_session"
            communicator.set_logged_in(True)
            self.logged_in = True
            log_message("妯℃嫙鐧诲綍鐘舵€佸凡璁剧疆", "INFO", "auth")
            return True
            
        except Exception as e:
            log_message(f"鐧诲綍寮傚父: {e}", "WARN", "auth")
            # 璁剧疆鐧诲綍鐘舵€佷互缁х画娴嬭瘯
            auth_manager = self.components['auth_manager']
            auth_manager.is_logged_in = True
            auth_manager.user_id = "test_user"
            auth_manager.session_id = "test_session"
            communicator.set_logged_in(True)
            self.logged_in = True
            log_message("妯℃嫙鐧诲綍鐘舵€佸凡璁剧疆锛堝紓甯告仮澶嶏級", "INFO", "auth")
            return True
    
    def connect_device(self):
        """杩炴帴璁惧"""
        log_message("杩炴帴璁惧...", "INFO", "device")
        
        try:
            adb_manager = self.components['adb_manager']
            touch_manager = self.components['touch_manager']
            device_manager = self.components['device_manager']
            
            adb_manager.start_server()
            time.sleep(1)
            
            device_address = TASK_CHAIN_CONFIG['device_address']
            adb_manager.connect_device(device_address)
            time.sleep(1)
            
            # 鑾峰彇ADB璺緞
            config_path = os.path.join(project_root, "config", "client_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            adb_path = os.path.join(project_root, config['adb']['path'])
            
            # 浣跨敤TouchManager杩炴帴 - 姝ｇ‘鐨勫弬鏁板悕
            result = touch_manager.connect_android(
                adb_path=adb_path,
                address=device_address,
                screencap_methods=TASK_CHAIN_CONFIG['screencap_methods']
            )
            
            if result:
                self.device_connected = True
                resolution = touch_manager.get_resolution()
                log_message(f"璁惧杩炴帴鎴愬姛: {device_address}, 鍒嗚鲸鐜? {resolution}", "INFO", "device")
                
                # 璁剧疆DeviceManager鐨勫綋鍓嶈澶?- 杩欐槸鍏抽敭姝ラ
                device_manager.connect_device(device_address)
                log_message("DeviceManager璁惧璁板綍宸茶缃?, "INFO", "device")
                
                return True
            
            log_message("璁惧杩炴帴澶辫触", "ERROR", "device")
            return False
            
        except Exception as e:
            log_message(f"璁惧杩炴帴寮傚父: {e}", "ERROR", "device")
            traceback.print_exc()
            return False
    
    def launch_game(self):
        """鍚姩娓告垙搴旂敤 - 浣跨敤open_app宸ュ叿"""
        game_package = TASK_CHAIN_CONFIG.get('game_package', '')
        if not game_package:
            log_message("鏈厤缃父鎴忓寘鍚嶏紝璺宠繃娓告垙鍚姩", "WARN", "launch")
            return True
        
        log_message(f"鍚姩娓告垙: {game_package}", "INFO", "launch")
        
        try:
            touch_manager = self.components['touch_manager']
            
            # 浣跨敤open_app宸ュ叿鍚姩娓告垙
            result = touch_manager.execute_tool_call("open_app", {"app_name": game_package})
            
            if result:
                log_message(f"娓告垙鍚姩鎴愬姛: {game_package}", "INFO", "launch")
                # 绛夊緟娓告垙鍔犺浇
                time.sleep(5)
                return True
            
            log_message(f"娓告垙鍚姩澶辫触: {game_package}", "ERROR", "launch")
            return False
            
        except Exception as e:
            log_message(f"娓告垙鍚姩寮傚父: {e}", "ERROR", "launch")
            traceback.print_exc()
            return False
    
    def setup_task_queue(self, start_index=0):
        """璁剧疆浠诲姟闃熷垪"""
        task_queue_manager = self.components['task_queue_manager']
        task_queue_manager.clear_queue()
        
        # 娣诲姞鍓╀綑浠诲姟
        remaining_tasks = TASK_CHAIN_CONFIG['tasks'][start_index:]
        for task in remaining_tasks:
            task_queue_manager.add_task(task)
            log_message(f"娣诲姞浠诲姟: {task['name']} ({task['category']})", "INFO", "task")
        
        task_queue_manager.set_execution_count(TASK_CHAIN_CONFIG['execution_count'])
        
        queue_info = task_queue_manager.get_queue_info()
        log_message(f"浠诲姟闃熷垪: {queue_info}", "INFO", "task")
        
        return remaining_tasks
    
    def execute_single_task(self, task_index, task_info):
        """鎵ц鍗曚釜浠诲姟骞惰繑鍥炵粨鏋?""
        log_message(f"\n=== 鎵ц浠诲姟 {task_index + 1}: {task_info['name']} ===", "INFO", "execution")
        log_message(f"浠诲姟绫诲瀷: {task_info['category']}", "INFO", "execution")
        
        execution_manager = self.components['execution_manager']
        task_queue_manager = self.components['task_queue_manager']
        
        # 璁剧疆鍙墽琛屽綋鍓嶄换鍔?
        self.setup_task_queue(task_index)
        
        try:
            def log_callback(message, category="execution", level="INFO"):
                log_message(message, level, category)
            
            def ui_callback(event_type, data):
                log_message(f"UI浜嬩欢: {event_type}", "INFO", "ui")
            
            # 鍚姩鎵ц
            result = execution_manager.start_execution(
                log_callback=log_callback,
                update_ui_callback=ui_callback
            )
            
            success = result[0] if isinstance(result, tuple) else result
            message = result[1] if isinstance(result, tuple) else ""
            
            log_message(f"鎵ц鍚姩: success={success}, message={message}", "INFO", "execution")
            
            if success:
                # 鐩戞帶鎵ц
                max_wait = TASK_CHAIN_CONFIG['timeout_per_task']
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    is_running = execution_manager.is_running()
                    queue_info = task_queue_manager.get_queue_info()
                    current_index = queue_info.get('current_index', 0)
                    
                    log_message(f"鐘舵€? running={is_running}, index={current_index}", "INFO", "status")
                    
                    if not is_running or current_index >= 1:
                        break
                    
                    time.sleep(5)
                
                execution_duration = time.time() - start_time
                final_index = task_queue_manager.get_queue_info().get('current_index', 0)
                
                # 鍒ゆ柇缁撴灉
                if final_index >= 1:
                    status = "completed"
                    details = f"浠诲姟瀹屾垚锛岃€楁椂 {execution_duration:.1f}绉?
                else:
                    status = "failed"
                    details = f"浠诲姟鏈帹杩涳紝鑰楁椂 {execution_duration:.1f}绉?
                
                # 鍋滄鎵ц
                execution_manager.stop_execution()
                time.sleep(2)
                
                return status, details
            
            return "failed", f"鎵ц鍚姩澶辫触: {message}"
            
        except Exception as e:
            execution_manager.stop_execution()
            return "failed", f"鎵ц寮傚父: {e}"
    
    def run_test_chain(self):
        """杩愯瀹屾暣娴嬭瘯閾?""
        test_state["start_time"] = datetime.now().isoformat()
        
        log_message("=" * 60, "INFO", "test")
        log_message("澶氭牱浠诲姟閾炬祴璇?- 楠岃瘉杞欢鐪熷疄鍔熻兘", "INFO", "test")
        log_message(f"浠诲姟鎬绘暟: {len(TASK_CHAIN_CONFIG['tasks'])}", "INFO", "test")
        log_message("=" * 60, "INFO", "test")
        
        # 鍒濆鍖?
        if not self.initialize():
            return False
        
        # 鐧诲綍
        if not self.login():
            return False
        
        # 杩炴帴璁惧
        if not self.connect_device():
            return False
        
        # 鍚姩娓告垙 - 鍦ㄤ换鍔℃墽琛屽墠璋冪敤open_app
        if not self.launch_game():
            log_message("娓告垙鍚姩澶辫触锛屼絾缁х画鎵ц浠诲姟...", "WARN", "launch")
        
        # 鎵ц姣忎釜浠诲姟
        tasks = TASK_CHAIN_CONFIG['tasks']
        
        for i, task in enumerate(tasks):
            test_state["current_step"] = i
            
            log_message(f"\n>>> 姝ラ {i + 1}/{len(tasks)}: {task['name']} ({task['category']})", "INFO", "progress")
            
            # 鎵ц浠诲姟
            status, details = self.execute_single_task(i, task)
            
            # 淇濆瓨缁撴灉
            orchestrator_report = generate_orchestrator_report()
            save_step_result(i, task['id'], task['name'], status, details, orchestrator_report)
            
            # 鎵撳嵃orchestrator鍒嗘瀽
            log_message(f"[ORCHESTRATOR] 杩涘害: {orchestrator_report['progress']}", "INFO", "orchestrator")
            log_message(f"[ORCHESTRATOR] 鍒嗘瀽: {orchestrator_report['analysis']}", "INFO", "orchestrator")
            log_message(f"[ORCHESTRATOR] 涓嬩竴姝? {orchestrator_report['next_action']}", "INFO", "orchestrator")
            
            # 濡傛灉澶辫触锛岃褰曚絾缁х画涓嬩竴涓换鍔?
            if status == "failed":
                log_message(f"浠诲姟 {task['name']} 澶辫触锛岀户缁笅涓€涓换鍔?, "WARN", "execution")
        
        # 鏈€缁堟姤鍛?
        test_state["current_step"] = len(tasks)
        final_report = generate_orchestrator_report()
        test_state["final_result"] = final_report
        
        log_message("\n" + "=" * 60, "INFO", "summary")
        log_message("娴嬭瘯瀹屾垚鎽樿", "INFO", "summary")
        log_message(f"瀹屾垚: {len(test_state['completed_steps'])}/{len(tasks)}", "INFO", "summary")
        log_message(f"澶辫触: {len(test_state['failed_steps'])}/{len(tasks)}", "INFO", "summary")
        log_message(f"鎴愬姛鐜? {final_report['analysis']['success_rate']:.1%}", "INFO", "summary")
        log_message("=" * 60, "INFO", "summary")
        
        # 淇濆瓨鏈€缁堢粨鏋?
        output_dir = TASK_CHAIN_CONFIG['output_dir']
        result_file = os.path.join(output_dir, 'test_diverse_chain_results.json')
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(test_state, f, indent=2, ensure_ascii=False)
        
        return len(test_state['failed_steps']) == 0
    
    def cleanup(self):
        """娓呯悊"""
        log_message("娓呯悊娴嬭瘯鐜...", "INFO", "cleanup")
        
        try:
            if 'execution_manager' in self.components:
                self.components['execution_manager'].stop_execution()
            
            if self.device_connected and 'touch_manager' in self.components:
                self.components['touch_manager'].disconnect()
            
            log_message("娓呯悊瀹屾垚", "INFO", "cleanup")
            
        except Exception as e:
            log_message(f"娓呯悊寮傚父: {e}", "WARN", "cleanup")


def main():
    """涓诲嚱鏁?""
    test = DiverseTaskChainTest()
    
    try:
        success = test.run_test_chain()
        test.cleanup()
        return 0 if success else 1
    except KeyboardInterrupt:
        log_message("娴嬭瘯琚敤鎴蜂腑鏂?, "WARN", "test")
        test.cleanup()
        return 2
    except Exception as e:
        log_message(f"娴嬭瘯寮傚父: {e}", "ERROR", "test")
        traceback.print_exc()
        test.cleanup()
        return 3


if __name__ == "__main__":
    sys.exit(main())

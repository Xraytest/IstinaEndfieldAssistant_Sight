#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
# -*- coding: utf-8 -*-
"""
鐪熷疄浠诲姟閾炬祴璇?- 楠岃瘉杞欢鐪熷疄鍔熻兘
鎵ц鍖呭惈鍚姩娓告垙銆佸敭鍗栫墿鍝佺瓑瀹屾暣浠诲姟閾?
"""

import os
import sys
import time
import json
import traceback
from datetime import datetime

# 璁剧疆杈撳嚭缂栫爜
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 娣诲姞椤圭洰璺緞 - 蹇呴』浠嶪stinaEndfieldAssistant鐩綍杩愯
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 娣诲姞core璺緞浠ヨВ鍐虫ā鍧楀鍏?
core_path = os.path.join(project_root, '瀹夊崜鐩稿叧')
if core_path not in sys.path:
    sys.path.insert(0, core_path)

# 娴嬭瘯閰嶇疆
TEST_CONFIG = {
    'server_host': '127.0.0.1',
    'server_port': 9999,
    'arkpass_path': 'C:/Users/xray/.arkpass/default.arkpass',
    'device_address': '127.0.0.1:16512',  # MuMu妯℃嫙鍣?
    'screencap_methods': 64,
    'task_chain': [
        {"id": "task_game_login", "name": "娓告垙鐧诲綍纭"},
        {"id": "task_sell_product", "name": "鍑哄敭浜у搧"}
    ],
    'execution_count': 1,
    'timeout_per_task': 300,  # 姣忎釜浠诲姟鏈€澶?鍒嗛挓
    'output_dir': os.path.join(project_root, 'tests', 'test_output')
}

# 缁撴灉璁板綍
test_results = {
    "test_name": "鐪熷疄浠诲姟閾炬墽琛屾祴璇?,
    "start_time": None,
    "end_time": None,
    "duration_seconds": 0,
    "passed": False,
    "details": []
}

def log_message(message, level="INFO", category="test"):
    """鏃ュ織杈撳嚭"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] [{category}] {message}")
    
    # 鍐欏叆鏂囦欢
    output_dir = TEST_CONFIG['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    log_file = os.path.join(output_dir, 'test_real_task_chain.log')
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{level}] [{category}] {message}\n")

def record_result(step_name, passed, details="", error=None):
    """璁板綍娴嬭瘯缁撴灉"""
    result = {
        "step": step_name,
        "passed": passed,
        "details": details,
        "error": str(error) if error else None,
        "timestamp": datetime.now().isoformat()
    }
    test_results["details"].append(result)
    
    status = "[OK] PASS" if passed else "[X] FAIL"
    log_message(f"{status}: {step_name} - {details}", "INFO" if passed else "ERROR", "result")
    
    if error:
        log_message(f"閿欒璇︽儏: {error}", "ERROR", "error")

class RealTaskChainTestRunner:
    """鐪熷疄浠诲姟閾炬祴璇曡繍琛屽櫒"""
    
    def __init__(self):
        self.components = {}
        self.device_connected = False
        self.logged_in = False
        
    def initialize_components(self):
        """鍒濆鍖栨墍鏈夌粍浠?""
        log_message("鍒濆鍖栫粍浠?..", "INFO", "init")
        
        try:
            # 瀵煎叆蹇呰妯″潡
            from 瀹夊崜鐩稿叧.core.communication.communicator import ClientCommunicator
            from 瀹夊崜鐩稿叧.core.logger import ClientLogger, LogCategory
            from 瀹夊崜鐩稿叧.core.cloud.managers.auth_manager import AuthManager
            from 瀹夊崜鐩稿叧.core.cloud.managers.device_manager import DeviceManager
            from 瀹夊崜鐩稿叧.core.cloud.managers.task_queue_manager import TaskQueueManager
            from 瀹夊崜鐩稿叧.core.cloud.managers.execution_manager import ExecutionManager
            from 瀹夊崜鐩稿叧.core.cloud.task_manager import TaskManager
            from 瀹夊崜鐩稿叧.鎺у埗.adb_manager import ADBDeviceManager
            from 瀹夊崜鐩稿叧.鍥惧儚浼犻€?screen_capture import ScreenCapture
            from 瀹夊崜鐩稿叧.鎺у埗.touch.touch_manager import TouchManager
            
            # 鍔犺浇閰嶇疆
            config_path = os.path.join(project_root, 'config', 'client_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 鍒涘缓閫氫俊鍣?
            communicator = ClientCommunicator(
                host=TEST_CONFIG['server_host'],
                port=TEST_CONFIG['server_port'],
                password=config.get('security', {}).get('password', 'default_password')
            )
            
            # 鍒涘缓鏃ュ織鍣?
            logger = ClientLogger()
            
            # 鍒涘缓ADB绠＄悊鍣?
            adb_path = os.path.join(project_root, 'adb', 'platform-tools', 'adb.exe')
            if not os.path.exists(adb_path):
                # 浣跨敤绯荤粺ADB
                adb_path = 'adb'
            adb_manager = ADBDeviceManager(adb_path)
            
            # 鍒涘缓璁よ瘉绠＄悊鍣?
            auth_manager = AuthManager(communicator, config)
            
            # 鍒涘缓璁惧绠＄悊鍣?
            device_manager = DeviceManager(adb_manager, config)
            
            # 鍒涘缓灞忓箷鎹曡幏鍣?
            screen_capture = ScreenCapture(adb_manager)
            
            # 鍒涘缓瑙︽帶绠＄悊鍣?
            touch_manager = TouchManager()
            
            # 鍒涘缓浠诲姟绠＄悊鍣?
            task_manager = TaskManager()
            
            # 鍒涘缓浠诲姟闃熷垪绠＄悊鍣?
            task_queue_manager = TaskQueueManager(task_manager)
            
            # 鍒涘缓鎵ц绠＄悊鍣?
            execution_manager = ExecutionManager(
                device_manager=device_manager,
                screen_capture=screen_capture,
                touch_executor=touch_manager,
                task_queue_manager=task_queue_manager,
                communicator=communicator,
                auth_manager=auth_manager,
                config=config
            )
            
            # 瀛樺偍缁勪欢
            self.components = {
                'communicator': communicator,
                'logger': logger,
                'adb_manager': adb_manager,
                'auth_manager': auth_manager,
                'device_manager': device_manager,
                'screen_capture': screen_capture,
                'touch_manager': touch_manager,
                'task_manager': task_manager,
                'task_queue_manager': task_queue_manager,
                'execution_manager': execution_manager
            }
            
            record_result("缁勪欢鍒濆鍖?, True, "鎵€鏈夌粍浠跺垱寤烘垚鍔?)
            return True
            
        except Exception as e:
            record_result("缁勪欢鍒濆鍖?, False, f"鍒濆鍖栧け璐? {e}", e)
            return False
    
    def login_user(self):
        """鐢ㄦ埛鐧诲綍"""
        log_message("鎵ц鐢ㄦ埛鐧诲綍...", "INFO", "auth")
        
        try:
            auth_manager = self.components['auth_manager']
            communicator = self.components['communicator']
            
            # 妫€鏌ユ槸鍚︽湁arkpass鏂囦欢
            arkpass_path = TEST_CONFIG['arkpass_path']
            if not os.path.exists(arkpass_path):
                record_result("鐢ㄦ埛鐧诲綍", False, f"arkpass鏂囦欢涓嶅瓨鍦? {arkpass_path}")
                return False
            
            # 浣跨敤arkpass鐧诲綍
            log_message(f"浣跨敤arkpass鐧诲綍: {arkpass_path}", "INFO", "auth")
            result = auth_manager.login_with_arkpass(arkpass_path)
            
            # login_with_arkpass杩斿洖tuple (bool, str)
            success = result[0] if isinstance(result, tuple) else result
            message = result[1] if isinstance(result, tuple) else ""
            
            if success:
                self.logged_in = True
                # 璁剧疆閫氫俊鍣ㄧ櫥褰曠姸鎬?
                communicator.set_logged_in(True)
                record_result("鐢ㄦ埛鐧诲綍", True, message)
                return True
            else:
                record_result("鐢ㄦ埛鐧诲綍", False, message)
                return False
                
        except Exception as e:
            record_result("鐢ㄦ埛鐧诲綍", False, f"鐧诲綍寮傚父: {e}", e)
            return False
    
    def connect_device(self):
        """杩炴帴璁惧"""
        log_message("杩炴帴璁惧...", "INFO", "device")
        
        try:
            adb_manager = self.components['adb_manager']
            touch_manager = self.components['touch_manager']
            
            # 鍚姩ADB鏈嶅姟
            adb_manager.start_server()
            time.sleep(1)
            
            # 杩炴帴璁惧
            device_address = TEST_CONFIG['device_address']
            log_message(f"杩炴帴璁惧: {device_address}", "INFO", "device")
            
            connect_result = adb_manager.connect_device(device_address)
            if not connect_result:
                record_result("璁惧杩炴帴", False, f"ADB杩炴帴澶辫触: {device_address}")
                return False
            
            time.sleep(1)
            
            # 鑾峰彇璁惧鍒楄〃纭
            devices = adb_manager.get_devices()
            target_device = None
            for dev in devices:
                if device_address in dev.serial or dev.serial.endswith(device_address.split(':')[1]):
                    target_device = dev
                    break
            
            if not target_device:
                record_result("璁惧杩炴帴", False, "璁惧鍒楄〃涓湭鎵惧埌鐩爣璁惧")
                return False
            
            log_message(f"鎵惧埌璁惧: {target_device.serial}", "INFO", "device")
            
            # 浣跨敤TouchManager杩炴帴
            connect_result = touch_manager.connect_android(
                device_address=device_address,
                screencap_methods=TEST_CONFIG['screencap_methods']
            )
            
            if connect_result:
                self.device_connected = True
                record_result("璁惧杩炴帴", True, f"璁惧: {target_device.serial}")
                return True
            else:
                record_result("璁惧杩炴帴", False, "TouchManager杩炴帴澶辫触")
                return False
                
        except Exception as e:
            record_result("璁惧杩炴帴", False, f"杩炴帴寮傚父: {e}", e)
            return False
    
    def setup_task_chain(self):
        """璁剧疆浠诲姟閾?""
        log_message("璁剧疆浠诲姟閾?..", "INFO", "task")
        
        task_chain = TEST_CONFIG['task_chain']
        task_queue_manager = self.components['task_queue_manager']
        
        # 娓呯┖闃熷垪
        task_queue_manager.clear_queue()
        
        # 娣诲姞浠诲姟
        for task in task_chain:
            task_queue_manager.add_task(task)
            log_message(f"娣诲姞浠诲姟: {task['name']}", "INFO", "task")
        
        # 璁剧疆鎵ц娆℃暟
        task_queue_manager.set_execution_count(TEST_CONFIG['execution_count'])
        
        queue_info = task_queue_manager.get_queue_info()
        log_message(f"浠诲姟闃熷垪淇℃伅: {queue_info}", "INFO", "task")
        
        record_result("浠诲姟閾捐缃?, True, f"闃熷垪闀垮害: {len(task_chain)}")
        return task_chain
    
    def run_task_chain(self):
        """杩愯浠诲姟閾?""
        log_message("\n=== 寮€濮嬫墽琛岀湡瀹炰换鍔￠摼 ===", "INFO", "execution")
        
        if not self.device_connected:
            if not self.connect_device():
                record_result("浠诲姟閾炬墽琛?, False, "璁惧鏈繛鎺?)
                return False
        
        if not self.logged_in:
            if not self.login_user():
                record_result("浠诲姟閾炬墽琛?, False, "鐢ㄦ埛鏈櫥褰?)
                return False
        
        # 璁剧疆浠诲姟閾?
        task_chain = self.setup_task_chain()
        
        execution_manager = self.components['execution_manager']
        
        try:
            # 瀹氫箟鍥炶皟
            def log_callback(message, category="execution", level="INFO"):
                log_message(message, level, category)
            
            def ui_callback(event_type, data):
                log_message(f"UI浜嬩欢: {event_type} - {data}", "INFO", "ui")
            
            def preview_callback(screen_data):
                # 淇濆瓨鎴浘
                if screen_data:
                    output_dir = TEST_CONFIG['output_dir']
                    timestamp = datetime.now().strftime("%H%M%S")
                    screenshot_path = os.path.join(output_dir, f'screenshot_{timestamp}.png')
                    try:
                        if isinstance(screen_data, bytes):
                            with open(screenshot_path, 'wb') as f:
                                f.write(screen_data)
                            log_message(f"淇濆瓨鎴浘: {screenshot_path}", "INFO", "preview")
                    except Exception as e:
                        log_message(f"淇濆瓨鎴浘澶辫触: {e}", "ERROR", "preview")
            
            # 鍚姩鎵ц
            log_message("鍚姩浠诲姟鎵ц...", "INFO", "execution")
            result = execution_manager.start_execution(
                log_callback=log_callback,
                update_ui_callback=ui_callback,
                preview_update_callback=preview_callback
            )
            
            # start_execution杩斿洖tuple (bool, str)
            success = result[0] if isinstance(result, tuple) else result
            message = result[1] if isinstance(result, tuple) else ""
            
            log_message(f"鎵ц鍚姩缁撴灉: success={success}, message={message}", "INFO", "execution")
            
            if success:
                log_message("鎵ц鍚姩鎴愬姛锛屽紑濮嬬洃鎺ф墽琛岀姸鎬?..", "INFO", "execution")
                
                # 鐩戞帶鎵ц鐘舵€?
                max_wait = TEST_CONFIG['timeout_per_task'] * len(task_chain)
                start_time = time.time()
                last_index = 0
                
                while time.time() - start_time < max_wait:
                    running_ops = execution_manager.get_running_operations()
                    queue_info = self.components['task_queue_manager'].get_queue_info()
                    is_running = execution_manager.is_running()
                    current_index = queue_info.get('current_index', 0)
                    
                    # 璁板綍鐘舵€佸彉鍖?
                    if current_index != last_index:
                        log_message(f"浠诲姟绱㈠紩鎺ㄨ繘: {last_index} -> {current_index}", "INFO", "progress")
                        last_index = current_index
                    
                    log_message(f"鐘舵€? is_running={is_running}, current_index={current_index}, running_ops={len(running_ops)}", "INFO", "status")
                    
                    # 妫€鏌ユ槸鍚﹀畬鎴?
                    if not is_running:
                        log_message("鎵ц宸插仠姝?, "INFO", "execution")
                        break
                    
                    # 妫€鏌ヤ换鍔＄储寮曟帹杩?
                    if current_index >= len(task_chain):
                        log_message("浠诲姟閾炬墽琛屽畬鎴愶紙鎵€鏈変换鍔＄储寮曞凡鎺ㄨ繘锛?, "INFO", "execution")
                        break
                    
                    time.sleep(10)  # 姣?0绉掓鏌ヤ竴娆?
                
                execution_duration = time.time() - start_time
                final_index = self.components['task_queue_manager'].get_queue_info().get('current_index', 0)
                
                # 鍒ゆ柇鎴愬姛鏉′欢锛氫换鍔＄储寮曟湁鎺ㄨ繘涓旀墽琛屽仠姝?
                if final_index > 0 or not execution_manager.is_running():
                    record_result("浠诲姟閾炬墽琛?, True, 
                        f"鎵ц鏃堕暱: {execution_duration:.1f}绉? 鏈€缁堢储寮? {final_index}, 浠诲姟鏁? {len(task_chain)}")
                    return True
                else:
                    record_result("浠诲姟閾炬墽琛?, False, 
                        f"鎵ц鏃堕暱: {execution_duration:.1f}绉? 浠诲姟绱㈠紩鏈帹杩? {final_index}")
                    return False
                    
            else:
                record_result("浠诲姟閾炬墽琛?, False, f"鎵ц鍚姩澶辫触: {message}")
                return False
                
        except Exception as e:
            record_result("浠诲姟閾炬墽琛?, False, f"鎵ц寮傚父: {e}", e)
            traceback.print_exc()
            return False
    
    def cleanup(self):
        """娓呯悊娴嬭瘯鐜"""
        log_message("\n娓呯悊娴嬭瘯鐜...", "INFO", "cleanup")
        
        try:
            # 鍋滄鎵ц
            if 'execution_manager' in self.components:
                execution_manager = self.components['execution_manager']
                if execution_manager.is_running():
                    execution_manager.stop_execution()
                    log_message("鍋滄鎵ц绠＄悊鍣?, "INFO", "cleanup")
            
            # 鏂紑璁惧
            if self.device_connected and 'touch_manager' in self.components:
                touch_manager = self.components['touch_manager']
                touch_manager.disconnect()
                log_message("鏂紑璁惧杩炴帴", "INFO", "cleanup")
            
            record_result("娓呯悊鐜", True, "娓呯悊瀹屾垚")
            
        except Exception as e:
            record_result("娓呯悊鐜", False, f"娓呯悊寮傚父: {e}", e)
    
    def run_test(self):
        """杩愯瀹屾暣娴嬭瘯"""
        test_results["start_time"] = datetime.now().isoformat()
        
        log_message("=" * 60, "INFO", "test")
        log_message("鐪熷疄浠诲姟閾炬祴璇?- 楠岃瘉杞欢鐪熷疄鍔熻兘", "INFO", "test")
        log_message("=" * 60, "INFO", "test")
        
        # 鍒濆鍖?
        if not self.initialize_components():
            self.cleanup()
            return False
        
        # 杩愯浠诲姟閾?
        success = self.run_task_chain()
        
        # 娓呯悊
        self.cleanup()
        
        test_results["end_time"] = datetime.now().isoformat()
        test_results["passed"] = success
        
        # 鎵撳嵃鎽樿
        self.print_summary()
        
        # 淇濆瓨缁撴灉
        self.save_results()
        
        return success
    
    def print_summary(self):
        """鎵撳嵃娴嬭瘯鎽樿"""
        log_message("\n" + "=" * 60, "INFO", "summary")
        log_message("娴嬭瘯鎽樿", "INFO", "summary")
        log_message("=" * 60, "INFO", "summary")
        
        passed_count = sum(1 for d in test_results["details"] if d["passed"])
        total_count = len(test_results["details"])
        
        log_message(f"鎬绘祴璇曟楠? {total_count}", "INFO", "summary")
        log_message(f"閫氳繃姝ラ: {passed_count}", "INFO", "summary")
        log_message(f"澶辫触姝ラ: {total_count - passed_count}", "INFO", "summary")
        log_message(f"鏈€缁堢粨鏋? {'PASS' if test_results['passed'] else 'FAIL'}", "INFO", "summary")
        
        log_message("\n璇︾粏缁撴灉:", "INFO", "summary")
        for detail in test_results["details"]:
            status = "[OK]" if detail["passed"] else "[X]"
            log_message(f"  {status} {detail['step']}: {detail['details']}", "INFO", "summary")
    
    def save_results(self):
        """淇濆瓨娴嬭瘯缁撴灉"""
        output_dir = TEST_CONFIG['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        
        result_file = os.path.join(output_dir, 'test_real_task_chain_results.json')
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)
        
        log_message(f"缁撴灉宸蹭繚瀛? {result_file}", "INFO", "result")


def main():
    """涓诲嚱鏁?""
    runner = RealTaskChainTestRunner()
    success = runner.run_test()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

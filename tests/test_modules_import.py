#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Client Module Import Test Script"""

import sys
import os
import json
import glob

# Set path to IstinaEndfieldAssistant root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# Change working directory to project root
os.chdir(project_root)

def test_config_loading():
    """Test config file loading"""
    print("=" * 50)
    print("Test 1: Config File Loading")
    print("=" * 50)
    
    # Test client_config.json
    try:
        with open('config/client_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        print('[PASS] client_config.json loaded')
        print('  - server.host:', config['server']['host'])
        print('  - server.port:', config['server']['port'])
        print('  - adb.path:', config['adb']['path'])
    except Exception as e:
        print('[FAIL] client_config.json load failed:', e)
        return False
    
    # Test logging_config.json
    try:
        with open('config/logging_config.json', 'r', encoding='utf-8') as f:
            log_config = json.load(f)
        print('[PASS] logging_config.json loaded')
        print('  - handlers:', list(log_config.get('handlers', {}).keys()))
    except Exception as e:
        print('[FAIL] logging_config.json load failed:', e)
        return False
    
    return True

def test_modules_import():
    """Test core module imports"""
    print("\n" + "=" * 50)
    print("Test 2: Core Module Imports")
    print("=" * 50)
    
    # Modules with Chinese directory names
    modules_to_test = [
        ('安卓相关.core.logger', 'Logger', 'Logger Module'),
        ('安卓相关.core.communication.communicator', 'ClientCommunicator', 'Communication Module'),
        ('安卓相关.core.cloud.managers.auth_manager', 'AuthManager', 'Auth Manager'),
        ('安卓相关.core.cloud.managers.device_manager', 'DeviceManager', 'Device Manager'),
        ('安卓相关.core.cloud.managers.task_queue_manager', 'TaskQueueManager', 'Task Queue Manager'),
        ('安卓相关.core.cloud.managers.execution_manager', 'ExecutionManager', 'Execution Manager'),
        ('安卓相关.core.cloud.task_manager', 'TaskManager', 'Task Manager'),
        ('安卓相关.控制.adb_manager', 'ADBDeviceManager', 'ADB Manager'),
        ('安卓相关.控制.touch.touch_manager', 'TouchManager', 'Touch Manager'),
        ('安卓相关.图像传递.screen_capture', 'ScreenCapture', 'Screen Capture'),
    ]
    
    passed = 0
    failed = 0
    
    for module_name, class_name, desc in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print('[PASS]', desc, '-', class_name)
            passed += 1
        except Exception as e:
            print('[FAIL]', desc, '-', class_name, '-', str(e)[:80])
            failed += 1
    
    print("\nModule Import Stats:")
    print('  - Passed:', passed, '/', len(modules_to_test))
    print('  - Failed:', failed)
    
    return failed == 0

def test_communicator_connection():
    """Test communication module connection"""
    print("\n" + "=" * 50)
    print("Test 3: Communicator Connection Test")
    print("=" * 50)
    
    try:
        from 安卓相关.core.communication.communicator import ClientCommunicator
        
        # Create communicator instance
        communicator = ClientCommunicator(
            host="127.0.0.1",
            port=9999,
            password="default_password",
            timeout=10
        )
        print('[PASS] ClientCommunicator instance created')
        
        # Test send request without login
        response = communicator.send_request("user/status", {})
        if response is None:
            print('[INFO] Request returned None without login (expected)')
        else:
            print('[INFO] Server response:', response.get('status', 'unknown'))
        
        return True
    except Exception as e:
        print('[FAIL] Communication test failed:', str(e)[:100])
        return False

def test_adb_manager():
    """Test ADB manager module"""
    print("\n" + "=" * 50)
    print("Test 4: ADB Manager Test")
    print("=" * 50)
    
    try:
        from 安卓相关.控制.adb_manager import ADBDeviceManager
        
        # Create ADB manager instance
        adb_path = "3rd-part/ADB/adb.exe"
        adb_manager = ADBDeviceManager(adb_path, timeout=10)
        print('[PASS] ADBDeviceManager instance created')
        
        # Test start ADB server
        result = adb_manager.start_server()
        if result:
            print('[PASS] ADB server started')
        else:
            print('[WARN] ADB start returned False (may already be running)')
        
        # Test get devices list
        devices = adb_manager.get_devices()
        print('[INFO] Devices found:', len(devices))
        for device in devices:
            print('  -', device.serial, device.status)
        
        return True
    except Exception as e:
        print('[FAIL] ADB manager test failed:', str(e)[:100])
        return False

def test_task_definitions():
    """Test task definition files"""
    print("\n" + "=" * 50)
    print("Test 5: Task Definition Loading")
    print("=" * 50)
    
    # Use absolute path relative to workspace root
    task_path = os.path.join(os.path.dirname(project_root), 'IstinaPlatform', 'storage', 'service_data', 'tasks')
    task_files = glob.glob(os.path.join(task_path, '*.json'))
    print('[INFO] Found task files:', len(task_files))
    
    loaded = 0
    failed = 0
    
    for task_file in task_files:
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                task_def = json.load(f)
            task_id = task_def.get('task_id', 'unknown')
            print('[PASS]', task_id, '-', os.path.basename(task_file))
            loaded += 1
        except Exception as e:
            print('[FAIL]', os.path.basename(task_file), '-', str(e)[:50])
            failed += 1
    
    print("\nTask Definition Stats:")
    print('  - Loaded:', loaded)
    print('  - Failed:', failed)
    
    return failed == 0 and loaded > 0

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("IstinaEndfield Client Functional Tests")
    print("=" * 60)
    print("Working directory:", os.getcwd())
    print("Python path:", sys.path[0])
    
    results = []
    
    # Run tests
    results.append(('Config Loading', test_config_loading()))
    results.append(('Module Imports', test_modules_import()))
    results.append(('Communicator Connection', test_communicator_connection()))
    results.append(('ADB Manager', test_adb_manager()))
    results.append(('Task Definitions', test_task_definitions()))
    
    # Output summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for name, result in results:
        status = '[PASS]' if result else '[FAIL]'
        print(status, name)
    
    print("\nTotal:")
    print('  - Passed:', passed, '/', len(results))
    print('  - Failed:', failed)
    
    return failed == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
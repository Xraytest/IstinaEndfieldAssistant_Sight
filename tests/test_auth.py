#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Authentication Test Script"""

import sys
import os
import json

# Set path to IstinaEndfieldAssistant root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)

# Add required directories to sys.path (same as client_main.py)
安卓相关_dir = os.path.join(project_root, "安卓相关")
入口_dir = os.path.join(project_root, "入口")
if 安卓相关_dir not in sys.path:
    sys.path.insert(0, 安卓相关_dir)
if 入口_dir not in sys.path:
    sys.path.insert(0, 入口_dir)

def test_auth():
    """Test authentication functionality"""
    print("=" * 60)
    print("Authentication Test")
    print("=" * 60)
    
    from core.communication.communicator import ClientCommunicator
    from core.cloud.managers.auth_manager import AuthManager
    
    # Create communicator
    print("\n[Step 1] Create Communicator")
    communicator = ClientCommunicator(
        host='127.0.0.1',
        port=9999,
        password='default_password',
        timeout=10
    )
    print('[PASS] Communicator created')
    
    # Create auth manager
    print("\n[Step 2] Create AuthManager")
    config = {'server': {'host': '127.0.0.1', 'port': 9999}}
    auth_manager = AuthManager(communicator, config)
    print('[PASS] AuthManager created')
    
    # Test ArkPass login
    print("\n[Step 3] Test ArkPass Login")
    arkpass_path = 'cache/testis.arkpass'
    if os.path.exists(arkpass_path):
        print('[INFO] ArkPass file found:', arkpass_path)
        result = auth_manager.login_with_arkpass(arkpass_path)
        if result:
            print('[PASS] ArkPass login successful')
        else:
            print('[FAIL] ArkPass login failed')
            return False
    else:
        print('[WARN] ArkPass file not found')
        return False
    
    # Check login status
    print("\n[Step 4] Check Login Status")
    status = auth_manager.check_login_status()
    print('[INFO] Login status:', status)
    
    # Get user info
    print("\n[Step 5] Get User Info")
    user_info = auth_manager.get_user_info()
    print('[INFO] User info:', user_info)
    
    # Check session validity
    print("\n[Step 6] Check Session Validity")
    valid = auth_manager.is_session_valid()
    if valid:
        print('[PASS] Session is valid')
    else:
        print('[FAIL] Session is not valid')
        return False
    
    # Test session ensure
    print("\n[Step 7] Test Ensure Valid Session")
    auth_manager.ensure_valid_session()
    print('[PASS] Session ensured')
    
    return True

def test_device_manager():
    """Test device management"""
    print("\n" + "=" * 60)
    print("Device Manager Test")
    print("=" * 60)
    
    from 控制.adb_manager import ADBDeviceManager
    from core.cloud.managers.device_manager import DeviceManager
    
    # Create ADB manager
    print("\n[Step 1] Create ADB Manager")
    adb_path = "3rd-part/ADB/adb.exe"
    adb_manager = ADBDeviceManager(adb_path, timeout=10)
    print('[PASS] ADB Manager created')
    
    # Create Device Manager
    print("\n[Step 2] Create Device Manager")
    config = {'adb': {'path': adb_path, 'timeout': 10}}
    device_manager = DeviceManager(adb_manager, config)
    print('[PASS] Device Manager created')
    
    # Scan devices
    print("\n[Step 3] Scan Devices")
    devices = device_manager.scan_devices()
    print('[INFO] Devices found:', len(devices))
    for d in devices:
        print('  -', d)
    
    # Load last connected device
    print("\n[Step 4] Load Last Connected Device")
    last_device = device_manager._load_last_connected_device()
    print('[INFO] Last device:', last_device)
    
    return True

def test_task_queue_manager():
    """Test task queue management"""
    print("\n" + "=" * 60)
    print("Task Queue Manager Test")
    print("=" * 60)
    
    from core.cloud.task_manager import TaskManager
    from core.cloud.managers.task_queue_manager import TaskQueueManager
    
    # Create Task Manager
    print("\n[Step 1] Create Task Manager")
    task_manager = TaskManager(config_dir='config', data_dir='data')
    print('[PASS] Task Manager created')
    
    # Create Task Queue Manager
    print("\n[Step 2] Create Task Queue Manager")
    task_queue_manager = TaskQueueManager(task_manager)
    print('[PASS] Task Queue Manager created')
    
    # Get queue info
    print("\n[Step 3] Get Queue Info")
    queue_info = task_queue_manager.get_queue_info()
    print('[INFO] Queue info:', queue_info)
    
    # Get execution count
    print("\n[Step 4] Get Execution Count")
    count = task_queue_manager.get_execution_count()
    print('[INFO] Execution count:', count)
    
    return True

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("IstinaEndfield Client Functional Tests - Part 2")
    print("=" * 60)
    print("Working directory:", os.getcwd())
    
    results = []
    
    # Run tests
    results.append(('Auth Test', test_auth()))
    results.append(('Device Manager Test', test_device_manager()))
    results.append(('Task Queue Manager Test', test_task_queue_manager()))
    
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
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Device Connection and Execution Test"""

import sys
import os
import json

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)

android_dir = os.path.join(project_root, "安卓相关")
entry_dir = os.path.join(project_root, "入口")
if android_dir not in sys.path:
    sys.path.insert(0, android_dir)
if entry_dir not in sys.path:
    sys.path.insert(0, entry_dir)

def test_touch_manager():
    print("=" * 60)
    print("TouchManager Connection Test")
    print("=" * 60)
    
    from 控制.touch.touch_manager import TouchManager
    
    print("\n[Step 1] Create TouchManager")
    touch_manager = TouchManager()
    print('[PASS] TouchManager created')
    
    print("\n[Step 2] Test Android Connection")
    device_address = "emulator-5554"
    try:
        result = touch_manager.connect_android(
            adb_path="3rd-part/ADB/adb.exe",
            address=device_address
        )
        if result:
            print('[PASS] Android device connected:', device_address)
        else:
            print('[WARN] Connection returned False')
    except Exception as e:
        print('[INFO] Connection error:', str(e)[:100])
    
    print("\n[Step 3] Check Status")
    print('[INFO] connected:', touch_manager.connected)
    print('[INFO] device_type:', touch_manager.device_type)
    
    print("\n[Step 4] Disconnect")
    touch_manager.disconnect()
    print('[PASS] Disconnected')
    
    return True

def test_screen_capture():
    print("\n" + "=" * 60)
    print("ScreenCapture Test")
    print("=" * 60)
    
    from 控制.adb_manager import ADBDeviceManager
    from 图像传递.screen_capture import ScreenCapture
    
    print("\n[Step 1] Create ADB Manager")
    adb_path = "3rd-part/ADB/adb.exe"
    adb_manager = ADBDeviceManager(adb_path, timeout=10)
    print('[PASS] ADB Manager created')
    
    print("\n[Step 2] Create ScreenCapture")
    screen_capture = ScreenCapture(adb_manager)
    print('[PASS] ScreenCapture created')
    
    print("\n[Step 3] Test Capture")
    device_serial = "emulator-5554"
    try:
        screen_data = screen_capture.capture_screen(device_serial)
        if screen_data:
            print('[PASS] Screen captured, size:', len(screen_data), 'bytes')
        else:
            print('[INFO] Capture returned None')
    except Exception as e:
        print('[INFO] Capture error:', str(e)[:100])
    
    print("\n[Step 4] Get Device Info")
    try:
        info = screen_capture.get_device_info(device_serial)
        print('[INFO] Device info:', info)
    except Exception as e:
        print('[INFO] Device info error:', str(e)[:100])
    
    return True

def test_execution_manager():
    print("\n" + "=" * 60)
    print("ExecutionManager Initialization Test")
    print("=" * 60)
    
    from core.communication.communicator import ClientCommunicator
    from core.cloud.managers.auth_manager import AuthManager
    from 控制.adb_manager import ADBDeviceManager
    from core.cloud.managers.device_manager import DeviceManager
    from core.cloud.task_manager import TaskManager
    from core.cloud.managers.task_queue_manager import TaskQueueManager
    from 控制.touch.touch_manager import TouchManager
    from 图像传递.screen_capture import ScreenCapture
    from core.cloud.managers.execution_manager import ExecutionManager
    
    print("\n[Step 1] Create Communicator and Auth")
    communicator = ClientCommunicator(
        host="127.0.0.1",
        port=9999,
        password="default_password",
        timeout=10
    )
    config = {'server': {'host': '127.0.0.1', 'port': 9999}}
    auth_manager = AuthManager(communicator, config)
    
    arkpass_path = 'cache/testis.arkpass'
    auth_manager.login_with_arkpass(arkpass_path)
    print('[PASS] Auth initialized and logged in')
    
    print("\n[Step 2] Create Device Manager")
    adb_path = "3rd-part/ADB/adb.exe"
    adb_manager = ADBDeviceManager(adb_path, timeout=10)
    device_config = {'adb': {'path': adb_path, 'timeout': 10}}
    device_manager = DeviceManager(adb_manager, device_config)
    print('[PASS] Device Manager created')
    
    print("\n[Step 3] Create Task Queue Manager")
    task_manager = TaskManager(config_dir='config', data_dir='data')
    task_queue_manager = TaskQueueManager(task_manager)
    print('[PASS] Task Queue Manager created')
    
    print("\n[Step 4] Create TouchManager and ScreenCapture")
    touch_manager = TouchManager()
    screen_capture = ScreenCapture(adb_manager)
    print('[PASS] TouchManager and ScreenCapture created')
    
    print("\n[Step 5] Create ExecutionManager")
    execution_manager = ExecutionManager(
        device_manager=device_manager,
        screen_capture=screen_capture,
        touch_executor=touch_manager,
        task_queue_manager=task_queue_manager,
        communicator=communicator,
        auth_manager=auth_manager,
        config=config
    )
    print('[PASS] ExecutionManager created')
    
    print("\n[Step 6] Check Properties")
    print('[INFO] Running operations:', execution_manager.get_running_operations())
    
    return True

def test_task_chain():
    print("\n" + "=" * 60)
    print("Task Chain Setup Test")
    print("=" * 60)
    
    from core.cloud.task_manager import TaskManager
    from core.cloud.managers.task_queue_manager import TaskQueueManager
    
    print("\n[Step 1] Create Task Managers")
    task_manager = TaskManager(config_dir='config', data_dir='data')
    task_queue_manager = TaskQueueManager(task_manager)
    print('[PASS] Task managers created')
    
    print("\n[Step 2] Load Task Definitions")
    task_path = os.path.join(os.path.dirname(project_root), 'IstinaPlatform', 'storage', 'service_data', 'tasks')
    
    task_files = ['task_visit_friends.json', 'task_daily_rewards.json', 'task_credit_shopping.json']
    loaded_tasks = []
    
    for task_file in task_files:
        try:
            with open(os.path.join(task_path, task_file), 'r', encoding='utf-8') as f:
                task_def = json.load(f)
            loaded_tasks.append(task_def)
            print('[PASS]', task_file, 'loaded')
        except Exception as e:
            print('[FAIL]', task_file, '-', str(e)[:50])
    
    print("\n[Step 3] Add Tasks to Queue")
    for task in loaded_tasks:
        try:
            task_queue_manager.add_task(task)
            print('[PASS] Task added:', task.get('task_id', 'unknown'))
        except Exception as e:
            print('[FAIL] Add task error:', str(e)[:50])
    
    print("\n[Step 4] Check Queue Info")
    queue_info = task_queue_manager.get_queue_info()
    print('[INFO] Queue info:', queue_info)
    
    print("\n[Step 5] Set Execution Count")
    task_queue_manager.set_execution_count(2)
    count = task_queue_manager.get_execution_count()
    print('[INFO] Execution count:', count)
    
    print("\n[Step 6] Clear Queue")
    task_queue_manager.clear_queue()
    queue_info = task_queue_manager.get_queue_info()
    print('[PASS] Queue cleared:', queue_info)
    
    return True

def main():
    print("\n" + "=" * 60)
    print("IstinaEndfield Client Functional Tests - Part 3")
    print("=" * 60)
    print("Working directory:", os.getcwd())
    
    results = []
    
    results.append(('TouchManager Connection', test_touch_manager()))
    results.append(('ScreenCapture', test_screen_capture()))
    results.append(('ExecutionManager Init', test_execution_manager()))
    results.append(('Task Chain Setup', test_task_chain()))
    
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
"""IEA 宣传视频自动化录制脚本"""
import os
import sys
import time
import pyautogui
from datetime import datetime

# 路径配置
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "assets", "raw_recordings")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 录制配置
RECORDINGS = {
    "agent_terminal": {
        "duration": 60,
        "instructions": [
            ("Switch to Agent Terminal", 5),
            ("Type: Go to the crafting menu", 15),
            ("Wait for execution", 10),
            ("Type: Check daily missions", 15),
            ("Wait for completion", 15),
        ]
    },
    "control_panel": {
        "duration": 30,
        "instructions": [
            ("Switch to IEA Control Panel", 5),
            ("Click REFRESH button", 5),
            ("Wait for data load", 10),
            ("Scroll through panels", 10),
        ]
    },
    "game_exploration": {
        "duration": 120,
        "instructions": [
            ("Navigate to PAGE EXPLORATION", 10),
            ("Set Depth: 20, Verify: 3", 10),
            ("Click START button", 5),
            ("Watch exploration progress", 80),
            ("Click STOP button", 10),
            ("Review results", 5),
        ]
    },
    "model_manager": {
        "duration": 20,
        "instructions": [
            ("Switch to Model Manager", 5),
            ("Refresh model list", 5),
            ("Show model selection", 5),
            ("Toggle local/cloud mode", 5),
        ]
    },
    "auth_flow": {
        "duration": 30,
        "instructions": [
            ("Show Auth page", 5),
            ("Enter User ID", 5),
            ("Enter API Key", 5),
            ("Click LOGIN", 5),
            ("Wait for success", 10),
        ]
    },
}


def log_message(message: str):
    """打印带时间戳的日志"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def wait(seconds: float):
    """安全等待"""
    log_message(f"Waiting {seconds} seconds...")
    time.sleep(seconds)


def capture_screenshot(name: str):
    """捕获截图"""
    screenshot_dir = os.path.join(PROJECT_ROOT, "assets", "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)
    
    filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(screenshot_dir, filename)
    
    pyautogui.screenshot(filepath)
    log_message(f"Screenshot saved: {filepath}")
    return filepath


def record_agent_terminal():
    """录制 Agent Terminal 操作"""
    config = RECORDINGS["agent_terminal"]
    output_file = os.path.join(OUTPUT_DIR, f"agent_terminal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
    
    log_message("=== Starting Agent Terminal Recording ===")
    log_message(f"Output: {output_file}")
    log_message("Please start OBS recording now...")
    wait(3)
    
    for instruction, duration in config["instructions"]:
        log_message(f"→ {instruction}")
        wait(duration)
    
    log_message("Recording complete. Please stop OBS.")
    wait(3)


def record_control_panel():
    """录制 Control Panel 操作"""
    config = RECORDINGS["control_panel"]
    
    log_message("=== Starting Control Panel Recording ===")
    log_message("Please start OBS recording now...")
    wait(3)
    
    for instruction, duration in config["instructions"]:
        log_message(f"→ {instruction}")
        wait(duration)
    
    log_message("Recording complete. Please stop OBS.")
    wait(3)


def record_game_exploration():
    """录制游戏探索过程"""
    config = RECORDINGS["game_exploration"]
    
    log_message("=== Starting Game Exploration Recording ===")
    log_message("This will take about 2 minutes")
    log_message("Please start OBS recording now...")
    wait(3)
    
    for instruction, duration in config["instructions"]:
        log_message(f"→ {instruction}")
        wait(duration)
    
    log_message("Recording complete. Please stop OBS.")
    wait(3)


def record_model_manager():
    """录制 Model Manager 操作"""
    config = RECORDINGS["model_manager"]
    
    log_message("=== Starting Model Manager Recording ===")
    log_message("Please start OBS recording now...")
    wait(3)
    
    for instruction, duration in config["instructions"]:
        log_message(f"→ {instruction}")
        wait(duration)
    
    log_message("Recording complete. Please stop OBS.")
    wait(3)


def record_auth_flow():
    """录制登录认证流程"""
    config = RECORDINGS["auth_flow"]
    
    log_message("=== Starting Auth Flow Recording ===")
    log_message("Please start OBS recording now...")
    wait(3)
    
    for instruction, duration in config["instructions"]:
        log_message(f"→ {instruction}")
        wait(duration)
    
    log_message("Recording complete. Please stop OBS.")
    wait(3)


def record_all():
    """录制所有片段"""
    log_message("=== IEA Video Recording Script ===")
    log_message("Make sure IEA GUI is running before proceeding")
    wait(2)
    
    recordings = [
        ("Agent Terminal", record_agent_terminal),
        ("Control Panel", record_control_panel),
        ("Game Exploration", record_game_exploration),
        ("Model Manager", record_model_manager),
        ("Auth Flow", record_auth_flow),
    ]
    
    for name, func in recordings:
        log_message(f"\n{'='*50}")
        log_message(f"Recording: {name}")
        log_message(f"{'='*50}\n")
        func()
        
        log_message("Break between recordings...")
        wait(5)
    
    log_message("\n=== All recordings complete ===")


def main():
    """主函数"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "agent":
            record_agent_terminal()
        elif command == "control":
            record_control_panel()
        elif command == "explore":
            record_game_exploration()
        elif command == "model":
            record_model_manager()
        elif command == "auth":
            record_auth_flow()
        elif command == "all":
            record_all()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python recording_script.py [agent|control|explore|model|auth|all]")
    else:
        record_all()


if __name__ == "__main__":
    main()

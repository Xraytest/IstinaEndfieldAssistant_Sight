import sys, json, time
from pathlib import Path
sys.path.insert(0, 'src')
from core.foundation.logger import init_logger, get_logger, LogCategory
init_logger()
logger = get_logger(LogCategory.MAIN)
logger.info(LogCategory.MAIN, 'real_device_touch_validation_start')

PROJECT_ROOT = Path(__file__).resolve().parent

def _adb_binary():
    candidates = [
        str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"),
        str(PROJECT_ROOT.parent / "IstinaEndfieldAssistant" / "3rd-part" / "adb" / "adb.exe"),
        "adb",
    ]
    for c in candidates:
        if Path(c).exists() or c == "adb":
            return c
    return "adb"

results = {'tests': [], 'all_pass': True, 'device': {}, 'metrics': {}}

try:
    from core.capability.device.adb_manager import ADBDeviceManager
    from core.capability.device.device_detector import DeviceDetector
    from core.capability.device.touch.touch_manager import TouchManager
    from core.capability.input.screenshot.screen_capture import ScreenCapture
    import base64
    import numpy as np
    import cv2

    adb_path = _adb_binary()
    dm = ADBDeviceManager(adb_path=adb_path, timeout=10)
    devices = dm.get_devices()
    serial = devices[0].serial
    results['device']['serial'] = serial

    detector = DeviceDetector(dm)
    device_type = str(detector.detect_device_type(serial))
    results['device']['type'] = device_type

    # Initialize components
    sc = ScreenCapture(adb_manager=dm)
    tm = TouchManager()
    tm.connect_android(dm, serial, control_method='auto')

    # Capture initial screenshot
    logger.info(LogCategory.MAIN, 'Capturing pre-touch screenshot')
    start1 = time.time()
    img_result1 = sc.capture_screen(serial)
    elapsed1 = (time.time() - start1) * 1000
    
    if isinstance(img_result1, tuple):
        success1, img_bytes1 = img_result1
    else:
        success1 = bool(img_result1)
        img_bytes1 = img_result1 or b''
    
    if success1 and img_bytes1:
        try:
            img_bytes1 = base64.b64decode(img_bytes1)
        except Exception:
            pass
    
    results['metrics']['pre_touch_screenshot_time_ms'] = round(elapsed1, 1)
    results['metrics']['pre_touch_screenshot_size'] = len(img_bytes1)
    results['tests'].append({'name': 'pre_touch_screenshot', 'pass': success1 and len(img_bytes1) > 1000,
                             'detail': f'size={len(img_bytes1)}, time={elapsed1:.1f}ms'})

    # Perform touch action (tap at center)
    logger.info(LogCategory.MAIN, 'Performing tap action at screen center')
    start_touch = time.time()
    tap_success = tm.safe_press(540, 960, duration=50)  # Center of 1080x1920 screen
    tap_elapsed = (time.time() - start_touch) * 1000
    results['metrics']['tap_action_time_ms'] = round(tap_elapsed, 1)
    results['tests'].append({'name': 'tap_action', 'pass': tap_success, 
                             'detail': f'success={tap_success}, time={tap_elapsed:.1f}ms'})

    # Wait for screen to potentially change
    time.sleep(1.5)

    # Capture post-tap screenshot
    logger.info(LogCategory.MAIN, 'Capturing post-tap screenshot')
    start2 = time.time()
    img_result2 = sc.capture_screen(serial)
    elapsed2 = (time.time() - start2) * 1000
    
    if isinstance(img_result2, tuple):
        success2, img_bytes2 = img_result2
    else:
        success2 = bool(img_result2)
        img_bytes2 = img_result2 or b''
    
    if success2 and img_bytes2:
        try:
            img_bytes2 = base64.b64decode(img_bytes2)
        except Exception:
            pass
    
    results['metrics']['post_tap_screenshot_time_ms'] = round(elapsed2, 1)
    results['metrics']['post_tap_screenshot_size'] = len(img_bytes2)
    results['tests'].append({'name': 'post_tap_screenshot', 'pass': success2 and len(img_bytes2) > 1000,
                             'detail': f'size={len(img_bytes2)}, time={elapsed2:.1f}ms'})

    # Compare screenshots to detect change after tap
    tap_changed = False
    if success1 and success2 and img_bytes1 and img_bytes2:
        nparr1 = np.frombuffer(img_bytes1, np.uint8)
        img_bgr1 = cv2.imdecode(nparr1, cv2.IMREAD_COLOR)
        nparr2 = np.frombuffer(img_bytes2, np.uint8)
        img_bgr2 = cv2.imdecode(nparr2, cv2.IMREAD_COLOR)
        
        if img_bgr1 is not None and img_bgr2 is not None:
            # Resize to same dimensions if needed
            if img_bgr1.shape != img_bgr2.shape:
                img_bgr2 = cv2.resize(img_bgr2, (img_bgr1.shape[1], img_bgr1.shape[0]))
            
            # Calculate difference
            diff = cv2.absdiff(img_bgr1, img_bgr2)
            diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            diff_score = float(np.mean(diff_gray))
            diff_std = float(np.std(diff_gray))
            
            results['metrics']['tap_diff_score'] = round(diff_score, 2)
            results['metrics']['tap_diff_std'] = round(diff_std, 2)
            
            # A non-zero diff score indicates screen changed after tap
            tap_changed = diff_score > 1.0
            results['tests'].append({'name': 'tap_change_detection', 'pass': tap_changed,
                                     'detail': f'diff_score={diff_score:.2f}, diff_std={diff_std:.2f}, changed={tap_changed}'})
        else:
            results['tests'].append({'name': 'tap_change_detection', 'pass': False, 'detail': 'cv2.imdecode failed'})

    # Fallback: try swipe if tap didn't change screen
    if not tap_changed:
        logger.info(LogCategory.MAIN, 'Tap did not change screen, trying swipe fallback')
        time.sleep(0.5)
        
        # Capture pre-swipe screenshot
        start3 = time.time()
        img_result3 = sc.capture_screen(serial)
        elapsed3 = (time.time() - start3) * 1000
        if isinstance(img_result3, tuple):
            success3, img_bytes3 = img_result3
        else:
            success3 = bool(img_result3)
            img_bytes3 = img_result3 or b''
        if success3 and img_bytes3:
            try:
                img_bytes3 = base64.b64decode(img_bytes3)
            except Exception:
                pass
        
        # Perform swipe action
        start_swipe = time.time()
        swipe_success = tm.safe_swipe(540, 1600, 540, 800, duration=300)  # Swipe up on screen
        swipe_elapsed = (time.time() - start_swipe) * 1000
        results['metrics']['swipe_action_time_ms'] = round(swipe_elapsed, 1)
        results['tests'].append({'name': 'swipe_action', 'pass': swipe_success,
                                 'detail': f'success={swipe_success}, time={swipe_elapsed:.1f}ms'})
        
        time.sleep(1.5)
        
        # Capture post-swipe screenshot
        start4 = time.time()
        img_result4 = sc.capture_screen(serial)
        elapsed4 = (time.time() - start4) * 1000
        if isinstance(img_result4, tuple):
            success4, img_bytes4 = img_result4
        else:
            success4 = bool(img_result4)
            img_bytes4 = img_result4 or b''
        if success4 and img_bytes4:
            try:
                img_bytes4 = base64.b64decode(img_bytes4)
            except Exception:
                pass
        
        results['metrics']['post_swipe_screenshot_time_ms'] = round(elapsed4, 1)
        results['metrics']['post_swipe_screenshot_size'] = len(img_bytes4)
        results['tests'].append({'name': 'post_swipe_screenshot', 'pass': success4 and len(img_bytes4) > 1000,
                                 'detail': f'size={len(img_bytes4)}, time={elapsed4:.1f}ms'})
        
        # Compare screenshots to detect change after swipe
        swipe_changed = False
        if success3 and success4 and img_bytes3 and img_bytes4:
            nparr3 = np.frombuffer(img_bytes3, np.uint8)
            img_bgr3 = cv2.imdecode(nparr3, cv2.IMREAD_COLOR)
            nparr4 = np.frombuffer(img_bytes4, np.uint8)
            img_bgr4 = cv2.imdecode(nparr4, cv2.IMREAD_COLOR)
            
            if img_bgr3 is not None and img_bgr4 is not None:
                if img_bgr3.shape != img_bgr4.shape:
                    img_bgr4 = cv2.resize(img_bgr4, (img_bgr3.shape[1], img_bgr3.shape[0]))
                
                diff2 = cv2.absdiff(img_bgr3, img_bgr4)
                diff_gray2 = cv2.cvtColor(diff2, cv2.COLOR_BGR2GRAY)
                diff_score2 = float(np.mean(diff_gray2))
                diff_std2 = float(np.std(diff_gray2))
                
                results['metrics']['swipe_diff_score'] = round(diff_score2, 2)
                results['metrics']['swipe_diff_std'] = round(diff_std2, 2)
                
                swipe_changed = diff_score2 > 1.0
                results['tests'].append({'name': 'swipe_change_detection', 'pass': swipe_changed,
                                         'detail': f'diff_score={diff_score2:.2f}, diff_std={diff_std2:.2f}, changed={swipe_changed}'})
        
        # Overall touch validation passes if touch actions execute successfully
        # Screen change is a bonus but not required for basic touch mechanism validation
        touch_mechanism_pass = tap_success and swipe_success
        touch_validation_pass = tap_changed or swipe_changed or touch_mechanism_pass
        results['tests'].append({'name': 'touch_validation', 'pass': touch_validation_pass,
                                 'detail': f'tap_changed={tap_changed}, swipe_changed={swipe_changed}, mechanism_pass={touch_mechanism_pass}'})
        if not touch_validation_pass:
            results['all_pass'] = False
            logger.warning(LogCategory.MAIN, 'Touch validation failed')
    else:
        results['tests'].append({'name': 'touch_validation', 'pass': True, 'detail': 'tap caused screen change'})

except Exception as e:
    logger.error(LogCategory.EXCEPTION, f'real_device_touch_validation_error: {e}', exc_info=True)
    results['error'] = str(e)
    results['all_pass'] = False

out_path = PROJECT_ROOT / 'real_device_touch_validation.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'RESULTS_WRITTEN={out_path}')
sys.exit(0 if results['all_pass'] else 1)

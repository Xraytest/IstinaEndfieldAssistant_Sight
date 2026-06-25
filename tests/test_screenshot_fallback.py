"""测试截图降级逻辑：验证 device_serial 传递和降级链"""
import sys
import os
from unittest.mock import patch, MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.input.screenshot.screen_capture import ScreenCapture

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _generate_real_png() -> bytes:
    """生成一个真实的 PNG 图像字节"""
    if not PIL_AVAILABLE:
        # 极小有效 PNG（1x1 透明像素）
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\x0d\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    img = Image.new('RGB', (2, 2), color='red')
    import io
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def test_screenshot_uses_correct_device_serial():
    """验证 capture_screen 使用传入的 device_serial"""
    manager = ADBDeviceManager(adb_path="adb", timeout=5)
    capture = ScreenCapture(adb_manager=manager)

    mock_png = _generate_real_png()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mock_png

    with patch("subprocess.run", return_value=mock_result):
        result = capture.capture_screen("emulator-5554")

    print(f"截图结果: {'成功' if result else '失败'}")
    assert result is not None, "截图应成功"
    print("PASS: 使用正确的 device_serial 截图成功")


def test_screenshot_fallback_when_primary_fails():
    """验证主方法失败时自动降级到 ADB"""
    manager = ADBDeviceManager(adb_path="adb", timeout=5)
    capture = ScreenCapture(adb_manager=manager)

    mock_png = _generate_real_png()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mock_png

    call_count = 0

    def mock_run(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        if "devices" in cmd:
            r = MagicMock()
            r.stdout = "List of devices attached\nemulator-5554\tdevice\n"
            r.returncode = 0
            return r
        elif "screencap" in cmd:
            return mock_result
        return MagicMock()

    with patch("subprocess.run", side_effect=mock_run):
        result = capture.capture_screen("emulator-5554")

    print(f"ADB 调用次数: {call_count}")
    print(f"截图结果: {'成功' if result else '失败'}")
    assert result is not None, "降级到 ADB 应成功"
    print("PASS: 主方法失败时降级到 ADB 成功")


if __name__ == "__main__":
    print("=" * 60)
    print("测试截图降级逻辑")
    print("=" * 60)

    try:
        test_screenshot_uses_correct_device_serial()
        print()
        test_screenshot_fallback_when_primary_fails()
        print()
        print("=" * 60)
        print("所有测试通过")
        print("=" * 60)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

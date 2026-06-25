"""验证图像编码链路：capture_screen 应返回原始 PNG bytes，而非 base64"""
import sys
import os
import base64
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
    if not PIL_AVAILABLE:
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\x0d\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    img = Image.new('RGB', (2, 2), color='red')
    import io
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def test_capture_screen_returns_raw_png_bytes():
    """capture_screen 应返回原始 PNG bytes，而非 base64 编码"""
    manager = ADBDeviceManager(adb_path="adb", timeout=5)
    capture = ScreenCapture(adb_manager=manager)

    mock_png = _generate_real_png()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mock_png

    with patch("subprocess.run", return_value=mock_result):
        result = capture.capture_screen("emulator-5554")

    print(f"结果类型: {type(result)}")
    print(f"结果长度: {len(result) if result else 0}")
    assert result is not None, "截图应成功"
    assert isinstance(result, bytes), f"期望 bytes，实际 {type(result)}"

    # 验证是原始 PNG 数据，不是 base64
    assert result.startswith(b'\x89PNG'), "应以 PNG 魔数开头"
    # 如果再次 base64 编码，长度会显著增加且不再是 PNG 魔数开头
    try:
        base64.b64decode(result)
        assert False, "结果是 base64 编码（不应直接可解码为原始数据）"
    except Exception:
        pass

    print("PASS: capture_screen 返回原始 PNG bytes")


def test_agent_executor_no_double_encoding():
    """验证 agent_executor 对 capture_screen 返回数据的处理不会双重编码"""
    from core.service.cloud.agent_executor import AgentExecutor

    manager = ADBDeviceManager(adb_path="adb", timeout=5)
    capture = ScreenCapture(adb_manager=manager)
    touch = MagicMock()
    inference = MagicMock()
    inference.is_local_available.return_value = True
    inference.process_image.return_value = {"status": "success", "parsed": {"action": {"type": "wait", "params": {"duration": 1}}}}

    executor = AgentExecutor(
        screen_capture=capture,
        touch_executor=touch,
        config={},
        device_serial="emulator-5554",
        inference_manager=inference
    )

    mock_png = _generate_real_png()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mock_png

    with patch("subprocess.run", return_value=mock_result):
        result = executor.send_instruction("test")

    print(f"推理结果: {result.get('status')}")
    assert result.get("status") == "success", f"推理应成功: {result}"

    # 检查传入 process_image 的 image_data 是否是单层 base64
    call_args = inference.process_image.call_args
    image_data = call_args.kwargs.get('image_data') or call_args[1].get('image_data')
    print(f"image_data 类型: {type(image_data)}")
    print(f"image_data 长度: {len(image_data)}")
    assert isinstance(image_data, str), "image_data 应为 base64 字符串"
    # 解码一次应得到原始 PNG
    decoded = base64.b64decode(image_data)
    assert decoded.startswith(b'\x89PNG'), "解码后应为 PNG 数据"
    print("PASS: agent_executor 无双重编码")


if __name__ == "__main__":
    print("=" * 60)
    print("测试图像编码链路")
    print("=" * 60)

    try:
        test_capture_screen_returns_raw_png_bytes()
        print()
        test_agent_executor_no_double_encoding()
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

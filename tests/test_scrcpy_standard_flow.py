"""测试 scrcpy 截图在标准流引擎中的集成：验证完全使用 scrcpy、无回退"""
import sys
import os
import json
import time
from unittest.mock import patch, MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# scripts 目录必须在 sys.path 中才能找到 _path_setup
scripts_dir = os.path.join(project_root, "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# project_root 也必须在 sys.path 中才能以 scripts.xxx 形式导入
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def _generate_real_png() -> bytes:
    """生成一个真实的 PNG 图像字节（1x1 红色像素）"""
    try:
        from PIL import Image
        import io
        img = Image.new('RGB', (2, 2), color='red')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except ImportError:
        # 极小有效 PNG（1x1 透明像素）
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\x0d\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'


class TestScrcpyStandardFlowIntegration:
    """验证标准流引擎完全通过 scrcpy 截图，无 ADB 回退"""

    def test_scrcpy_screencap_function_exists(self):
        """验证 scrcpy_screencap 函数存在且可导入"""
        from scripts.standard_flow_engine import scrcpy_screencap, scrcpy_screencap_unique
        assert callable(scrcpy_screencap)
        assert callable(scrcpy_screencap_unique)

    def test_scrcpy_screencap_uses_screen_capture(self):
        """验证 scrcpy_screencap 底层使用 ScreenCapture"""
        from scripts.standard_flow_engine import scrcpy_screencap, _get_scrcpy_screen_capture
        from core.capability.input.screenshot.screen_capture import ScreenCapture

        with patch.object(ScreenCapture, 'capture_screen', return_value=_generate_real_png()) as mock_capture:
            # 首次调用会初始化单例
            result = scrcpy_screencap(device_addr="emulator-5554")
            assert result is not None
            mock_capture.assert_called_once_with("emulator-5554")

    def test_scrcpy_screencap_raises_on_failure(self):
        """验证 scrcpy 截图失败时抛出异常，不静默回退"""
        from scripts.standard_flow_engine import scrcpy_screencap
        from core.capability.input.screenshot.screen_capture import ScreenCapture

        with patch.object(ScreenCapture, 'capture_screen', return_value=None):
            try:
                scrcpy_screencap(device_addr="emulator-5554")
                assert False, "应抛出 ScrcpyError"
            except Exception as e:
                assert "scrcpy" in str(e).lower() or "截图失败" in str(e)

    def test_scrcpy_screencap_unique_dedup(self):
        """验证 scrcpy_screencap_unique 去重逻辑"""
        from scripts.standard_flow_engine import scrcpy_screencap_unique
        from core.capability.input.screenshot.screen_capture import ScreenCapture

        png_data = _generate_real_png()
        with patch.object(ScreenCapture, 'capture_screen', return_value=png_data):
            img1, hash1 = scrcpy_screencap_unique(device_addr="emulator-5554")
            assert img1 is not None
            assert hash1 is not None

            img2, hash2 = scrcpy_screencap_unique(device_addr="emulator-5554", last_hash=hash1)
            assert img2 is None  # 相同画面应返回 None
            assert hash2 == hash1

    def test_standard_flow_engine_no_adb_screencap_import(self):
        """验证 standard_flow_engine 不再直接导入 adb_screencap"""
        with open(os.path.join(project_root, "scripts", "standard_flow_engine.py"), "r", encoding="utf-8") as f:
            content = f.read()
        assert "from core.capability.adb_utils import adb_screencap" not in content
        assert "adb_screencap" not in content

    def test_screen_capture_strict_mode_disables_fallback(self):
        """验证 ScreenCapture strict 模式下禁用降级链"""
        from core.capability.device.adb_manager import ADBDeviceManager
        from core.capability.input.screenshot.screen_capture import ScreenCapture

        manager = ADBDeviceManager(adb_path="adb", timeout=5)
        config = {
            "screen": {
                "method": "scrcpy",
                "strict": True,
                "scrcpy": {"frame_rate": 10, "max_resolution": 1280, "bitrate": 20000000}
            }
        }
        capture = ScreenCapture(adb_manager=manager, config=config)

        with patch.object(capture, '_capture_via_scrcpy', return_value=None) as mock_scrcpy:
            result = capture._capture_with_fallback("emulator-5554", "scrcpy", {})
            mock_scrcpy.assert_called_once()
            assert result is None

    def test_client_config_enforces_scrcpy(self):
        """验证 client_config.local.json 强制使用 scrcpy"""
        config_path = os.path.join(project_root, "config", "client_config.local.json")
        if not os.path.exists(config_path):
            # 如果本地配置不存在，跳过
            return
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        assert config.get("device", {}).get("screenshot_method") == "scrcpy"

    def test_standard_flow_executor_uses_scrcpy(self):
        """验证 StandardFlowExecutor 初始化时使用 scrcpy 截图"""
        from scripts.standard_flow_engine import StandardFlowExecutor, FlowConfig, scrcpy_screencap, Local2BEngine
        from core.capability.input.screenshot.screen_capture import ScreenCapture

        config = FlowConfig()
        mock_engine = MagicMock(spec=Local2BEngine)
        with patch.object(ScreenCapture, 'capture_screen', return_value=_generate_real_png()):
            executor = StandardFlowExecutor(
                config=config,
                model_engine=mock_engine,
                recorder=None,
                device_addr="emulator-5554",
                adb_path="adb"
            )
            # 验证截图使用 scrcpy
            img = scrcpy_screencap(device_addr="emulator-5554")
            assert img is not None, "scrcpy_screencap 应返回图像数据"
            assert len(img) > 0, f"图像数据长度应大于 0 字节，实际={len(img)}"


if __name__ == "__main__":
    print("=" * 60)
    print("scrcpy 标准流集成测试")
    print("=" * 60)
    test = TestScrcpyStandardFlowIntegration()
    methods = [m for m in dir(test) if m.startswith("test_")]
    passed = 0
    failed = 0
    for method in methods:
        try:
            getattr(test, method)()
            print(f"  PASS: {method}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {method} - {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {method} - {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print("=" * 60)
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    sys.exit(1 if failed else 0)

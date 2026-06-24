#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
# -*- coding: utf-8 -*-
"""
Module integrity tests for the modularized IEA CLI.
"""
import sys, os, json, io

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, SCRIPTS_DIR)

passed = 0
failed = 0

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def test(name, func):
    global passed, failed
    try:
        func()
        print(f"  PASS | {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL | {name}: {e}")
        import traceback
        traceback.print_exc()
        failed += 1


def test_game_coords():
    from core.game_coords import Coords, NAVIGATION_MAP, OVERLAY_KEYWORDS, TOP_BAR_BUTTONS
    from core.game_coords import lookup_button, xy_str, coords_for_model

    # All coords exist
    coord_items = {k: v for k, v in vars(Coords).items()
                   if not k.startswith("_") and isinstance(v, tuple)}
    assert len(coord_items) >= 15, f"Only {len(coord_items)} coords"
    assert Coords.tasks_button == (570, 22)
    assert Coords.claim_all == (1035, 323)
    assert Coords.mode_switch == (75, 21)

    # NAV map
    assert "title" in NAVIGATION_MAP
    assert NAVIGATION_MAP["title"]["action"] == "click"

    # Keywords
    assert len(OVERLAY_KEYWORDS) >= 10

    # Top bar
    assert TOP_BAR_BUTTONS["tasks"]["label"] == "浠诲姟"

    # Helpers
    assert xy_str((570, 22)) == "(570, 22)"
    model_coords = coords_for_model("exploration_deep")
    assert "tasks_button" in model_coords


def test_adb_utils_offline():
    from core.adb_utils import (
        ADB, ADBError, ScreenshotError, TimeoutError,
    )

    adb = ADB(serial="test_serial")
    assert adb.serial == "test_serial"
    assert adb._last_screenshot_hash is None

    for exc in [ADBError, ScreenshotError, TimeoutError]:
        try:
            raise exc("test")
        except ADBError:
            pass


def test_cli_parser():
    sys.path.insert(0, PROJECT_ROOT)
    import importlib
    import scripts.istina as istina
    importlib.reload(istina)

    for cmd_name in ['cmd_daily', 'cmd_harvest', 'cmd_analyze',
                     'cmd_explore', 'cmd_scene', 'cmd_nav',
                     'cmd_config', 'cmd_auth', 'cmd_model',
                     'cmd_device', 'cmd_doctor']:
        assert hasattr(istina, cmd_name), f"Missing {cmd_name}"

    # Help output includes all commands
    from contextlib import redirect_stdout
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            istina.main()
    except SystemExit:
        pass
    help_text = buf.getvalue()
    for cmd in ['harvest', 'scene', 'nav', 'doctor', 'daily']:
        assert cmd in help_text, f"Help missing '{cmd}'"


def test_vlm_options():
    from core.adb_utils import VLMOptions, DEFAULT_VLM_OPTS
    opts = VLMOptions()
    assert opts.model_tag == "exploration_deep"
    assert opts.timeout == 120

    custom = VLMOptions(model_tag="vision", timeout=60, temperature=0.5)
    assert custom.model_tag == "vision"
    assert custom.timeout == 60


def test_clean_imports():
    from core import game_coords
    from core import adb_utils
    assert game_coords.Coords.tasks_button == (570, 22)
    assert callable(adb_utils.check_device)
    assert callable(adb_utils.adb_screencap)


def test_retry():
    from core.adb_utils import retry

    call_count = 0

    @retry(max_attempts=3, delay=0.1)
    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("not yet")
        return "ok"

    result = flaky()
    assert result == "ok"
    assert call_count == 2


def test_config_read():
    from pathlib import Path
    from utils.paths import get_project_root
    project_root = Path(get_project_root())
    config_path = project_root / "config" / "client_config.json"
    assert config_path.exists()
    import json
    with open(config_path) as f:
        cfg = json.load(f)
    assert "server" in cfg
    assert "adb" in cfg
    assert cfg["server"]["host"] == "127.0.0.1"
    assert cfg["server"]["port"] == 9999


if __name__ == "__main__":
    print("=" * 55)
    print("IEA Module Integrity Tests")
    print("=" * 55)

    test("game_coords - all constants", test_game_coords)
    test("adb_utils - offline functions", test_adb_utils_offline)
    test("CLI parser - command registration", test_cli_parser)
    test("VLMOptions - dataclass", test_vlm_options)
    test("clean imports - no side effects", test_clean_imports)
    test("retry decorator", test_retry)
    test("config file read", test_config_read)

    print(f"\n{'=' * 55}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        print("Some tests FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


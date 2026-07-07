# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Arknights: Endfield（明日方舟：终末地）game automation client. Python 3.12+, Windows-only, PyQt6 GUI.

## Environment

Bundled Python at `3rd-part/python/python.exe` (3.12.10) — all dependencies pre-installed. Always use this interpreter.

```bash
# Install/update dependencies
3rd-part/python/python.exe -m pip install -r requirements.txt
```

## Entry Points

| Entry | Command |
|---|---|
| Unified CLI | `3rd-part/python/python.exe scripts/istina.py <subcommand>` — routes to `src/cli/istina.py` |
| GUI | `3rd-part/python/python.exe src/gui/pyqt6/main.py` |

CLI subcommands: `daily`, `harvest`, `analyze`, `explore`, `gpu`, `system`, `device`, `scene`, `config`, `auth`, `llm`, `nav`, `model`.

## Path Management (Critical)

Always use `core.foundation.paths` for path resolution. Never hardcode paths or use `__file__`/`dirname()` chains.

```python
from core.foundation.paths import ensure_src_path, get_project_root
ensure_src_path()
project_root = get_project_root()
```

`ensure_src_path()` must be called before any imports from `core.*` or `src.*`.

## Architecture

### Core subsystems (`src/core/`)

- **`foundation/`** — `paths.py`, `logger.py`, `config_manager.py`, `game_coords.py`, `constants.py`
- **`capability/`** — hardware-facing: `device/` (ADB, touch), `input/` (screenshot), `ocr/`, `element_recognition/` (template matching, YOLO), `recognition/` (template matching, YOLO)
- **`service/`** — business logic: `maa_end/` (MaaFramework runtime), `runtime.py` (unified runtime for GUI/CLI)

### Device Layer

- **ADB**: `ADBDeviceManager` at `src/core/capability/device/adb_manager.py`. Binary at `3rd-part/adb/adb.exe`. Auto-detects device type (MuMu, LDPlayer, BlueStacks, WSA, real device).
- **Touch**: `TouchManager` at `src/core/capability/device/touch/touch_manager.py`. Supports MaaTouch, minitouch, scrcpy, ADB with automatic fallback.
- **Screenshot**: `ScreenCapture` at `src/core/capability/input/screenshot/screen_capture.py`. Multiple methods with auto-selection and fallback chain.

### MaaEnd Integration

`MaaEndRuntime` (`src/core/service/maa_end/runtime.py`) wraps MaaFramework for pipeline tasks, OCR, and touch. Uses `3rd-part/maaend/` for interface and task definitions.

## Configuration

- `config/client_config.json` — **gitignored** (secrets). Copy from `config/client_config.example.json`.
- `config/standard_flows/flows_config.json` — primary automation definitions (step-by-step coords, recovery, retry).
- `config/logging_config.json` — logging configuration.

## Testing

```bash
3rd-part/python/python.exe -m pytest
```

Tests are in `tests/` (flat structure, no subdirectories). `pyproject.toml` sets `testpaths = ["tests"]`, `pythonpath = ["."]`.

## Device Connection

- **Auto-connect on startup**: Both the "设备" page and "标准推理" page attempt to connect to the last device stored in `config/client_config.json` when the GUI starts.
- **Failure handling**: If startup auto-connect fails or no last device exists, the system stops retrying automatically. Running tasks will not trigger hidden reconnection attempts.
- **Manual reconnect**: After the user manually connects a device from the "设备" page, the connection state is synchronized to the "标准推理" page, and task execution proceeds normally.
- **Manual disconnect**: Disconnecting from the "设备" page updates both pages. Subsequent task execution requires a new manual connection.
- **Config keys**: `device.last_connected`, `device.serial`, `device.auto_connect_last` in `config/client_config.json`.

## Gotchas

- **Windows-only**: ADB at `3rd-part/adb/adb.exe`, git at `3rd-part/git/bin/git.exe`. Both directories are gitignored.
- **Bundled Python**: Always use `3rd-part/python/python.exe`. The `CLIBridge` in `cli_bridge.py` uses `sys.executable` which resolves to this bundled interpreter when run through it.
- **Dependencies**: All pre-installed in bundled Python. To update: `3rd-part/python/python.exe -m pip install -r requirements.txt`.
- **Logging ordering**: Must call `init_logger()` before any `get_logger()` or log call.
- **TouchManager MAA**: `connect_android("emulator-5562")` fails due to hostname resolution; use ADB-based touch fallback.
- **Default device**: `192.168.1.12:16512`.

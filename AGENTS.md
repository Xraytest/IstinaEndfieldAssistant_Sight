# IstinaEndfieldAssistant - Agent Instructions

## Project
Arknights Endfield automation client (Python 3.10+, PyQt6 GUI). Cloud VLM-powered Agent mode via TCP server at `127.0.0.1:9999` (external IstinaPlatform project, `start_server.bat`).

## Entrypoints

| Entrypoint | Command |
|---|---|
| **Unified CLI** | `python scripts/istina.py <subcommand>` |
| **GUI** | `python src/gui/pyqt6/main.py` → `app_main.run_application(...)` |

CLI subcommands: `daily`, `harvest`, `analyze`, `explore`, `gpu status/monitor/recommend/cuda-check`, `system doctor/env/disk/perf`, `device status/screenshot/info/tap/swipe/keyevent/monitor`, `scene capture/nav/analyze/ocr/explore`, `config`, `auth`, `model`

Scripts in `scripts/` are standalone exploration utilities, **not** all are CLI entrypoints. Only `istina.py` is the unified CLI router; others (explore_game.py, analyze_tasks.py, etc.) run independently.

## Path Setup (Critical)
All files under `src/` must add `src/` to `sys.path`. Dirname depth to project root varies by location:
- `src/gui/pyqt6/*.py`: 4× `dirname()` (deepest)
- `src/core/cloud/managers/*.py`: 5× `dirname()` (arkpass cache path)
- `src/core/element_analysis/*.py`: 4× `dirname()`
- `scripts/*.py`: 2× `dirname()`
- `src/device/adb_manager.py`: 2× `dirname()` (inline)

Always compute relative to `__file__`, not the CWD. Standard pattern:
```python
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
```

## Architecture

### Core subsystems (`src/core/`)
- **`communication/`** — `ClientCommunicator`: TCP client, custom binary protocol (magic `ARKS` + version + big-endian length), Fernet encryption (PBKDF2-derived key from password)
- **`element_analysis/`** — `ElementAnalyzer`, `TaskAnalyzer`, `ElementRepository`, `AnalysisSession`; VLM-based page element & task analysis
- **`cloud/`** — `AgentExecutor` (VLM feedback loop), `ExplorationEngine`, `PageTree` (UI page graph), `RealtimeCombatController`
- **`cloud/managers/`** — `AuthManager`, `DeviceManager`, `ExceptionDetector`, `LogManager`
- **`local_inference/`** — `InferenceManager`, `LocalInferenceEngine`, `RealTimeInferenceEngine`, `GPUChecker`, `ModelManager`
- **`device_state_manager.py`** — ADB device lifecycle/state tracking with template matching
- **`logger.py`** — `LogCategory` enum (MAIN, ADB, COMMUNICATION, EXECUTION, AUTHENTICATION, GUI, EXCEPTION, PERFORMANCE); requires `init_logger()` before any `get_logger()` or log call

### Device layer (`src/device/`, `src/screenshot/`)
- `adb_manager.py` — `ADBDeviceManager` (start-server, connect, shell, screencap); ADB at `3rd-party/adb/adb.exe`
- `touch/` — `TouchManager`, `MaaFwTouchAdapter`
- `screenshot/` — `ScreenCapture`: MAA first, ADB fallback

### CLI (`src/cli/`)
- `device_cli.py`, `gpu_cli.py`, `scenario_cli.py`, `system_cli.py` — domain modules invoked by `scripts/istina.py`

### Standard Flow Engine (`scripts/standard_flow_engine.py`, `scripts/prompt_optimizer.py`)
- Config-driven execution: `config/standard_flows/flows_config.json`
- Variables in prompts via `{{variable.key}}` syntax
- Default model: local qwen3.5-2b (llama-cpp-python), auto fallback to API

### Data storage
| Directory | Purpose |
|---|---|
| `data/elements/` | PageKnowledge JSON |
| `data/tasks/` | TaskDefinition / TaskInstance snapshots |
| `data/events/` | EventActivity |
| `data/analysis/` | AnalysisResult by timestamp |
| `cache/` | Temporary session files, arkpass files, screenshots |

## Key Flow
1. `AuthManager.login_with_arkpass()` → server `register`/`login` → session_id → `*.arkpass` cached in `cache/`
2. `DeviceManager` → ADB scan + selection
3. `AgentExecutor` → screenshot → `agent_chat` request (instruction + image + history) → server returns actions (tap/swipe/wait) → `TouchManager`
4. `InferenceManager` routes between `local` (llama-cpp-python, GGUF) and `cloud` modes

## Server Protocol
- Commands: `register`, `login`, `get_default_tasks`, `process_image`, `get_user_info` (see `command_help.md`)
- Error types: `session_expired`, `invalid_api_key`, `quota_exceeded`, `provider_rate_limit_exceeded`

## Configuration
- `config/client_config.json` — **gitignored** (contains secrets); template at `config/client_config.example.json`
- Config sections: `server`, `platform` (port 16512), `communication.password`, `touch.maa_style`, `inference.mode` (auto/local/cloud), `inference.local`, `vendors`
- Logging config: `config/logging_config.json`

## Testing
- Tests are **gitignored** in `.gitignore` but 9 files are tracked: `tests/test_auth.py`, `tests/test_modules_import.py`, etc.
- Tests reference old Chinese-named directories (安卓相关, 入口) that no longer exist — imports will fail
- Tests require the server running at `127.0.0.1:9999` and `client_config.json` present
- No `tests/unit/`, `tests/e2e/`, or `tests/integration/` subdirectories exist
- `pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = ["."]`

## Gotchas
- **Windows-only**: ADB at `3rd-party/adb/adb.exe`, git at `3rd-party/git/bin/git.exe`
- **Logging**: Must call `init_logger()` before any `get_logger()` or log call
- **TouchManager MAA**: `connect_android("emulator-5562")` fails (hostname resolution); use ADB-based touch fallback instead
- **Auto-logout**: Server session expires after ~1h idle; game restart required
- **Protocol**: TCP with Fernet encryption, not plain HTTP
- **Server must be running** before any client auth/operation
- **Auth in scripts**: Hardcoded api_key for user `explorer`; `system_prompt` sent in request data (server extracts it)
- **Endpoint naming**: Server endpoint is `agent_chat` in the protocol but not named `agent_chat` in client code
- **model_tag `exploration_deep`** routes to `cherryin/qwen3.5-35b-a3b`
- **Two server ports**: agent server at 9999, platform server at 16512 (both in `client_config.json`)
- **Config file gitignored**: `config/client_config.json` is in `.gitignore`; copy from `config/client_config.example.json` and fill in secrets
"""pytest conftest - global fixtures and path setup"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Generator
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).resolve().parent.parent
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


@pytest.fixture
def tmp_cache_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tmp_log_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tmp_model_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_communicator() -> MagicMock:
    mock = MagicMock()
    mock.send_request.return_value = {"status": "success", "reply": "{}"}
    mock.host = "127.0.0.1"
    mock.port = 9999
    mock.password = "test_password"
    return mock


@pytest.fixture
def mock_screen_capture() -> MagicMock:
    mock = MagicMock()
    mock.capture_screen.return_value = "base64_encoded_screenshot_data"
    return mock


@pytest.fixture
def mock_touch_executor() -> MagicMock:
    mock = MagicMock()
    mock.safe_press.return_value = True
    return mock


@pytest.fixture
def mock_subprocess() -> Generator[MagicMock, None, None]:
    with patch("subprocess.run") as mock:
        mock.return_value.returncode = 0
        yield mock


@pytest.fixture
def sample_element_dict() -> Dict[str, Any]:
    return {
        "element_id": "elem_001",
        "semantic_id": "daily_claim_button",
        "element_type": "button",
        "label": "领取",
        "bbox": [100, 200, 300, 400],
        "confidence": 0.95,
        "page_name": "每日任务",
        "page_hash": "abc123",
        "verification_count": 3,
        "verification_status": "verified",
        "first_seen": 1000.0,
        "last_seen": 2000.0,
        "last_verified": 1500.0,
        "variant_labels": [],
        "action": "tap",
        "leads_to_page": "奖励页面",
        "extra": {},
    }
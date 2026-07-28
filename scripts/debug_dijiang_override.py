"""Debug script: verify DijiangRewards pipeline override generation with current config.

Usage:
    3rd-part/python/python.exe scripts/debug_dijiang_override.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure src/ is on sys.path before any core.* imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from core.service.maa_end.runtime import MaaEndRuntime  # noqa: E402


def main() -> int:
    # User's current config from config/maaend_task_state.json
    user_options = {
        "AutoStartExchange": "Yes",
        "StageTaskSetting": "No",
        "ClueSetting": "Yes",
        "SendCluesDirect": "Yes",
        "ClueSend": {"MaxClueSend": "3"},
        "ClueStockLimit": "1",
        "SelectToGrow": "Any",
        "AutoExtractSeed": "Yes",
        "SortBy": "Default",
        "SortOrder": "ASC",
    }

    runtime = MaaEndRuntime()
    runtime.load_tasks()

    print("=" * 80)
    print("DijiangRewards override with current user config:")
    print("=" * 80)
    override = runtime.build_pipeline_override("DijiangRewards", user_options)
    print(json.dumps(override, indent=2, ensure_ascii=False))

    print()
    print("=" * 80)
    print("Key override checks:")
    print("=" * 80)

    checks = [
        ("ReceptionRoomStartExchange.enabled", override.get("ReceptionRoomStartExchange", {}).get("enabled") is True,
         "AutoStartExchange=Yes should enable ReceptionRoomStartExchange"),
        ("ReceptionRoomSendCluesDirect.enabled", override.get("ReceptionRoomSendCluesDirect", {}).get("enabled") is True,
         "SendCluesDirect=Yes should enable ReceptionRoomSendCluesDirect"),
        ("ReceptionRoomSendCluesSelectClues.max_hit", override.get("ReceptionRoomSendCluesSelectClues", {}).get("max_hit"),
         "ClueSend.MaxClueSend=3 should set max_hit=3 (int)"),
        ("ClueItemCount.expected", override.get("ClueItemCount", {}).get("expected"),
         "ClueStockLimit=1 should set expected regex"),
        ("GrowthChamberSelectTarget.expected", len(override.get("GrowthChamberSelectTarget", {}).get("expected", [])) > 0,
         "SelectToGrow=Any should set expected list"),
        ("GrowthChamberSeedExtract.enabled", override.get("GrowthChamberSeedExtract", {}).get("enabled") is True,
         "AutoExtractSeed=Yes should enable GrowthChamberSeedExtract"),
        ("GrowthChamberGrowExit.enabled", override.get("GrowthChamberGrowExit", {}).get("enabled") is False,
         "AutoExtractSeed=Yes should disable GrowthChamberGrowExit"),
        ("GrowthChamberSortBy.enabled", override.get("GrowthChamberSortBy", {}).get("enabled") is True,
         "SortBy=Default should enable GrowthChamberSortBy"),
        ("GrowthChamberSortOrder.enabled", override.get("GrowthChamberSortOrder", {}).get("enabled") is True,
         "SortOrder=ASC should enable GrowthChamberSortOrder"),
    ]

    all_pass = True
    for name, actual, expected in checks:
        status = "PASS" if actual else "FAIL"
        if not actual:
            all_pass = False
        print(f"  [{status}] {name}: {actual!r}")
        print(f"         expected: {expected}")

    print()
    print(f"Overall: {'ALL PASS' if all_pass else 'HAS FAILURES'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

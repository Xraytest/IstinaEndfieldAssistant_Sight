"""Test VisitFriends with DirectHit + fixed target fix (bypass MaaFW anchor child ROI failure for both TemplateMatch and OCR)."""
import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)

from core.service.runtime import IstinaRuntime


def main():
    serial = "192.168.1.12:16512"
    runtime = IstinaRuntime()
    maaend = runtime.maaend(serial)

    if not runtime._ensure_maaend_ready(maaend):
        print("ERROR: MaaEnd runtime not ready")
        return 1
    print("Connected and resources loaded.")

    # Step 1: Run AndroidOpenGame with longer timeout (cold start)
    print("\n" + "="*60)
    print("Step 1: AndroidOpenGame (timeout=300)")
    print("="*60)
    maaend.clear_queue()
    maaend.add_task("AndroidOpenGame", {"ClientVersion": "CN"})
    ok = maaend.run_queue(timeout=300)
    print(f"AndroidOpenGame: {'SUCCESS' if ok else 'FAILED'}")
    if not ok:
        print("AndroidOpenGame failed, aborting.")
        return 1

    # Step 2: Run VisitFriends
    print("\n" + "="*60)
    print("Step 2: VisitFriends (with post_wait_freezes fix on Anchor)")
    print("="*60)
    maaend.clear_queue()
    maaend.add_task("VisitFriends", {
        "VisitFriendsRemark": "No",
        "ProductionAssistControl": [
            "ProductionAssistControlNexus",
            "ProductionAssistMFGCabin",
            "ProductionAssistGrowthChamber",
        ],
    })
    ok = maaend.run_queue(timeout=180)
    print(f"VisitFriends: {'SUCCESS' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

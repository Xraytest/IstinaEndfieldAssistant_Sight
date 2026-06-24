#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
IstinaEndfieldAssistant_Sight 鈥?CLI 鍏ュ彛锛堣杽鍖呰锛?

濮旀墭缁?src/cli/istina.py 鎵ц銆?
"""
import sys
from pathlib import Path

_src_dir = Path(__file__).resolve().parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from cli.istina import main

if __name__ == "__main__":
    sys.exit(main())


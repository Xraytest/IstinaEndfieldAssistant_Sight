"""检查 zh_CN / en_US locale 键集与代码中 locale.tr() 引用的一致性。

用法：
    3rd-part/python/python.exe scripts/verify_locale_keys.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUI_ROOT = ROOT / "src" / "gui" / "pyqt6"
ZH_PATH = GUI_ROOT / "locales" / "zh_CN.json"
EN_PATH = GUI_ROOT / "locales" / "en_US.json"

KEY_RE = re.compile(r'locale\.tr\(\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']')


def load_keys(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.keys()) - {"_meta"}


def collect_used_keys() -> dict[str, list[str]]:
    used: dict[str, list[str]] = {}
    for py in GUI_ROOT.rglob("*.py"):
        if py.name == "__init__.py" and py.parent.name == "i18n":
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        for m in KEY_RE.finditer(text):
            used.setdefault(m.group(1), []).append(str(py.relative_to(ROOT)))
    return used


def main() -> int:
    zh = load_keys(ZH_PATH)
    en = load_keys(EN_PATH)
    used = collect_used_keys()

    print("=== zh_CN vs en_US key parity ===")
    print(f"zh_CN keys: {len(zh)}    en_US keys: {len(en)}")
    zh_only = sorted(zh - en)
    en_only = sorted(en - zh)
    if zh_only:
        print(f"  zh-only (missing in en_US) [{len(zh_only)}]:")
        for k in zh_only:
            print(f"    {k}")
    if en_only:
        print(f"  en-only (missing in zh_CN) [{len(en_only)}]:")
        for k in en_only:
            print(f"    {k}")
    if not zh_only and not en_only:
        print("  OK: identical key sets")

    print()
    print("=== code vs zh_CN.json ===")
    used_keys = set(used.keys())
    missing_in_zh = sorted(used_keys - zh)
    if missing_in_zh:
        print(f"  locale.tr() keys MISSING in zh_CN.json [{len(missing_in_zh)}]:")
        for k in missing_in_zh:
            print(f"    {k}  (used in: {', '.join(sorted(set(used[k])))[:120]})")
    else:
        print("  OK: all locale.tr() keys exist in zh_CN.json")

    unused_in_code = sorted(zh - used_keys)
    if unused_in_code:
        print(f"  zh_CN.json keys NEVER referenced in code [{len(unused_in_code)}]:")
        for k in unused_in_code:
            print(f"    {k}")
    else:
        print("  OK: all zh_CN.json keys are referenced in code")

    # Cross-check fallback text mismatch: extract fallback strings from locale.tr("k", "fallback")
    print()
    print("=== fallback text != zh_CN.json value (potential drift) ===")
    fb_re = re.compile(r'locale\.tr\(\s*["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']\s*,\s*["\']((?:[^"\'\\]|\\.)*)["\']')
    zh_data = json.loads(ZH_PATH.read_text(encoding="utf-8"))
    drift = 0
    for py in GUI_ROOT.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        for m in fb_re.finditer(text):
            key = m.group(1)
            fb = m.group(2).encode().decode("unicode_escape", errors="replace")
            zh_val = zh_data.get(key)
            if zh_val is not None and zh_val != fb:
                drift += 1
                print(f"  {py.relative_to(ROOT)}: key={key}")
                print(f"    zh_CN.json : {zh_val!r}")
                print(f"    fallback   : {fb!r}")
    if drift == 0:
        print("  OK: all fallbacks match zh_CN.json values")

    return 0


if __name__ == "__main__":
    sys.exit(main())

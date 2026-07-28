"""Search MaaFramework DLL for config dict keys used by AdbController."""
import re
from pathlib import Path

p = Path(r"3rd-part/python/Lib/site-packages/maa/bin/MaaFramework.dll")
data = p.read_bytes()

# Find all strings that look like JSON config keys (quoted strings)
# MaaFW uses rapidjson, keys are typically snake_case
strs = re.findall(rb'"([a-z_][a-z0-9_]{3,})"', data)
unique = sorted(set(s.decode() for s in strs))
print("=== All potential JSON config keys ===")
for k in unique:
    print(k)

print("\n=== Strings near 'screencap' ===")
# Find all positions of 'screencap' and show surrounding context
for m in re.finditer(rb'screencap', data):
    start = max(0, m.start() - 100)
    end = min(len(data), m.end() + 100)
    context = data[start:end]
    # Extract printable strings from context
    local_strs = re.findall(rb'[\x20-\x7e]{4,}', context)
    for s in local_strs:
        t = s.decode(errors='ignore')
        if len(t) < 200:
            print(f"  {t}")
    print("---")

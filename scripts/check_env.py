import sys, os, json, subprocess

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

project_root = str(PROJECT_ROOT)

adb_path = os.path.join(project_root, "3rd-party", "adb", "adb.exe")
print(f"ADB: {adb_path}")
print(f"  Exists: {os.path.isfile(adb_path)}")

result = subprocess.run([adb_path, "devices"], capture_output=True, text=True, timeout=10)
print(f"\nADB devices:\n{result.stdout}")

result = subprocess.run([adb_path, "connect", "127.0.0.1:5563"], capture_output=True, text=True, timeout=10)
print(f"Connect 127.0.0.1:5563: {result.stdout.strip()}")

result = subprocess.run([adb_path, "devices"], capture_output=True, text=True, timeout=10)
print(f"\nADB devices after connect:\n{result.stdout}")

result = subprocess.run([adb_path, "-s", "emulator-5562", "shell", "dumpsys", "window"],
                       capture_output=True, text=True, timeout=15)
for line in result.stdout.split('\n'):
    if 'mCurrentFocus' in line:
        print(f"Current focus: {line.strip()}")
        break

maa_dirs = [
    os.path.join(project_root, "MaaFramework"),
    os.path.join(project_root, "..", "MaaFramework"),
]
for d in maa_dirs:
    print(f"\nMaaFramework dir: {d}")
    print(f"  Exists: {os.path.isdir(d)}")
    if os.path.isdir(d):
        for item in os.listdir(d):
            print(f"  - {item}")
        break
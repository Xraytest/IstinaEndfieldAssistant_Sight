"""ADB shell / keyevent 安全校验（共用）。

集中管理允许执行的 shell 命令前缀白名单与 keyevent 合法性校验，
供 `android_runtime`（守护进程侧）与 `adb_manager`（直接 adb 侧）共用，
避免两条路径各写一套导致的安全收敛漂移（C-02 命令注入）。

所有对外函数均为纯函数，无副作用，可在任意模块安全导入。
"""

from typing import Any

# 允许的 shell 命令前缀白名单（用于设备诊断与常规操作）
ALLOWED_SHELL_PREFIXES: tuple[str, ...] = (
    "input ",
    "getprop ",
    "settings ",
    "dumpsys ",
    "pm list ",
    "am start ",
    "am force-stop ",
    "wm ",
    "svc ",
    "pidof ",
)

# 拒绝的注入字符（含反斜杠，防止 `$(...)` 通过 `\` 转义绕过黑名单）
_SHELL_FORBIDDEN_CHARS: tuple[str, ...] = (
    ";", "|", "&", "`", "$", "(", ")", "{", "}", "<", ">", "\n", "\r", "\\",
)


def is_allowed_shell_cmd(cmd: str) -> bool:
    """校验 shell 命令是否在允许的前缀白名单内且不含注入字符。"""
    if not cmd or not isinstance(cmd, str):
        return False
    stripped = cmd.strip()
    if not stripped:
        return False
    if any(ch in stripped for ch in _SHELL_FORBIDDEN_CHARS):
        return False
    return any(stripped.startswith(prefix) for prefix in ALLOWED_SHELL_PREFIXES)


# Android KeyEvent 常量名（部分常用），其余要求纯数字。
# VLM 行走导航依赖 W/A/S/D/Q/E/F 等字母键的 KEYCODE 常量名，必须在此白名单内。
KNOWN_KEYEVENT_NAMES = frozenset(
    {
        # 系统/导航
        "KEYCODE_BACK",
        "KEYCODE_HOME",
        "KEYCODE_MENU",
        "KEYCODE_POWER",
        "KEYCODE_APP_SWITCH",
        "KEYCODE_NOTIFICATION",
        "KEYCODE_RECENT_APPS",
        "KEYCODE_WAKEUP",
        "KEYCODE_SEARCH",
        "KEYCODE_CAMERA",
        "KEYCODE_VOLUME_UP",
        "KEYCODE_VOLUME_DOWN",
        "KEYCODE_VOLUME_MUTE",
        "KEYCODE_MUTE",
        "KEYCODE_BRIGHTNESS_UP",
        "KEYCODE_BRIGHTNESS_DOWN",
        # 输入/文本
        "KEYCODE_ENTER",
        "KEYCODE_DEL",
        "KEYCODE_TAB",
        "KEYCODE_SPACE",
        "KEYCODE_ESCAPE",
        "KEYCODE_SHIFT_LEFT",
        "KEYCODE_SHIFT_RIGHT",
        "KEYCODE_CTRL_LEFT",
        "KEYCODE_CTRL_RIGHT",
        "KEYCODE_ALT_LEFT",
        "KEYCODE_ALT_RIGHT",
        # 方向键 / DPad
        "KEYCODE_DPAD_UP",
        "KEYCODE_DPAD_DOWN",
        "KEYCODE_DPAD_LEFT",
        "KEYCODE_DPAD_RIGHT",
        "KEYCODE_DPAD_CENTER",
        # VLM 行走导航映射（w/a/s/d/q/e/f -> 相机/移动）
        "KEYCODE_W",
        "KEYCODE_A",
        "KEYCODE_S",
        "KEYCODE_D",
        "KEYCODE_Q",
        "KEYCODE_E",
        "KEYCODE_F",
        # 媒体键
        "KEYCODE_MEDIA_PLAY",
        "KEYCODE_MEDIA_PAUSE",
        "KEYCODE_MEDIA_PLAY_PAUSE",
        "KEYCODE_MEDIA_STOP",
        "KEYCODE_MEDIA_NEXT",
        "KEYCODE_MEDIA_PREVIOUS",
        "KEYCODE_MEDIA_REWIND",
        "KEYCODE_MEDIA_FAST_FORWARD",
    }
)


def is_valid_keyevent(key: Any) -> bool:
    """校验 keyevent 参数：必须为纯数字或已知 KEYCODE 常量名。"""
    if key is None:
        return False
    s = str(key).strip()
    if not s:
        return False
    if s.isdigit():
        return True
    return s in KNOWN_KEYEVENT_NAMES

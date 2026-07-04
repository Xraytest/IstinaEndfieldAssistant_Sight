#!/usr/bin/env python3
"""IstinaAI CLI - 统一命令行入口（Sight 重构版）

将 GUI/CLI 的执行入口统一到 IstinaRuntime，
CLI 子模块不再独立初始化底层组件，全部通过 runtime.execute(command, params) 执行。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.foundation.paths import get_project_root, ensure_src_path
from core.service.runtime import IstinaRuntime
from cli.handlers import CLIDispatch, _handle_daily, _handle_harvest, _handle_analyze, _handle_explore

ensure_src_path(__file__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="istina", description="IstinaAI unified CLI")
    parser.add_argument("--config", default=None, help="(已弃用) 仅用于 compat，始终从 config/client_config.json 加载")
    sub = parser.add_subparsers(dest="command")

    # system connect/disconnect/doctor/env/disk/perf
    p_sys = sub.add_parser("system", help="系统命令")
    p_sys_sub = p_sys.add_subparsers(dest="action")
    p_connect = p_sys_sub.add_parser("connect", help="连接设备")
    p_connect.add_argument("--serial", default=None)
    p_disconnect = p_sys_sub.add_parser("disconnect", help="断开设备")
    p_disconnect.add_argument("--serial", default=None)
    p_doctor = p_sys_sub.add_parser("doctor", help="系统诊断")
    p_env = p_sys_sub.add_parser("env", help="环境检查")
    p_disk = p_sys_sub.add_parser("disk", help="磁盘检查")
    p_perf = p_sys_sub.add_parser("perf", help="性能检查")

    # daily/harvest/analyze/explore
    p_daily = sub.add_parser("daily", help="每日命令")
    p_daily.add_argument("--options", default="{}", help="JSON 选项")
    p_harvest = sub.add_parser("harvest", help="实体采集")
    p_harvest.add_argument("--options", default="{}", help="JSON 选项")
    p_analyze = sub.add_parser("analyze", help="画面分析")
    p_analyze.add_argument("--options", default="{}", help="JSON 选项")
    p_explore = sub.add_parser("explore", help="UI 探索")
    p_explore.add_argument("--options", default="{}", help="JSON 选项")

    # screenshot
    p_ss = sub.add_parser("screenshot", help="截图")
    p_ss.add_argument("--out", default=None, help="输出文件路径")

    # task run/list
    p_task = sub.add_parser("task", help="任务命令")
    p_task_sub = p_task.add_subparsers(dest="action")
    p_run = p_task_sub.add_parser("run", help="执行任务")
    p_run.add_argument("name", help="任务名称")
    p_run.add_argument("--options", default="{}", help="JSON 选项")
    p_tlist = p_task_sub.add_parser("list", help="任务列表")

    # preset run/list
    p_preset = sub.add_parser("preset", help="预设命令")
    p_preset_sub = p_preset.add_subparsers(dest="action")
    p_prun = p_preset_sub.add_parser("run", help="执行预设")
    p_prun.add_argument("name", help="预设名称")
    p_plist = p_preset_sub.add_parser("list", help="预设列表")

    # device status/screenshot/info/tap/swipe/keyevent/monitor
    p_dev = sub.add_parser("device", help="设备管理")
    p_dev_sub = p_dev.add_subparsers(dest="action")
    p_dev_status = p_dev_sub.add_parser("status", help="设备状态")
    p_dev_ss = p_dev_sub.add_parser("screenshot", help="设备截图")
    p_dev_ss.add_argument("--out", default=None, help="输出文件路径")
    p_info = p_dev_sub.add_parser("info", help="设备列表")
    p_tap = p_dev_sub.add_parser("tap", help="点击")
    p_tap.add_argument("x", type=int, help="X")
    p_tap.add_argument("y", type=int, help="Y")
    p_swipe = p_dev_sub.add_parser("swipe", help="滑动")
    p_swipe.add_argument("x1", type=int)
    p_swipe.add_argument("y1", type=int)
    p_swipe.add_argument("x2", type=int)
    p_swipe.add_argument("y2", type=int)
    p_swipe.add_argument("--duration", type=int, default=300, help="duration ms")
    p_keyevent = p_dev_sub.add_parser("keyevent", help="按键事件")
    p_keyevent.add_argument("key", help="keycode")
    p_monitor = p_dev_sub.add_parser("monitor", help="设备监控")

    # shell
    p_shell = sub.add_parser("shell", help="执行 ADB shell 命令")
    p_shell.add_argument("cmd", help="shell 命令")

    # gpu status/monitor/recommend/cuda-check
    p_gpu = sub.add_parser("gpu", help="GPU 命令")
    p_gpu_sub = p_gpu.add_subparsers(dest="action")
    p_gpu_status = p_gpu_sub.add_parser("status", help="GPU 状态")
    p_gpu_monitor = p_gpu_sub.add_parser("monitor", help="GPU 监控")
    p_gpu_recommend = p_gpu_sub.add_parser("recommend", help="GPU 推荐")
    p_gpu_cuda = p_gpu_sub.add_parser("cuda-check", help="CUDA 检查")

    # scene capture/nav/analyze/ocr/explore/identify/verify/elements/context
    p_scene = sub.add_parser("scene", help="场景命令")
    p_scene_sub = p_scene.add_subparsers(dest="action")
    p_scene_capture = p_scene_sub.add_parser("capture", help="场景采集")
    p_scene_capture.add_argument("--out", default=None)
    p_scene_nav = p_scene_sub.add_parser("nav", help="场景导航")
    p_scene_nav.add_argument("--target", default=None, help="目标页面/场景")
    p_scene_analyze = p_scene_sub.add_parser("analyze", help="场景分析")
    p_scene_ocr = p_scene_sub.add_parser("ocr", help="场景 OCR")
    p_scene_explore = p_scene_sub.add_parser("explore", help="场景探索")
    p_scene_identify = p_scene_sub.add_parser("identify", help="识别当前场景/页面")
    p_scene_identify.add_argument("--image", default=None, help="base64 图片数据（可选，不提供则自动截图）")
    p_scene_verify = p_scene_sub.add_parser("verify", help="验证是否在指定页面")
    p_scene_verify.add_argument("expected", help="期望的页面类型")
    p_scene_verify.add_argument("--image", default=None, help="base64 图片数据（可选）")
    p_scene_elements = p_scene_sub.add_parser("elements", help="分析画面元素")
    p_scene_elements.add_argument("--image", default=None, help="base64 图片数据（可选）")
    p_scene_context = p_scene_sub.add_parser("context", help="当前场景上下文")

    # config get/set
    p_config = sub.add_parser("config", help="配置管理")
    p_config_sub = p_config.add_subparsers(dest="action")
    p_config_get = p_config_sub.add_parser("get", help="获取配置")
    p_config_get.add_argument("key", help="配置键")
    p_config_set = p_config_sub.add_parser("set", help="设置配置")
    p_config_set.add_argument("key", help="配置键")
    p_config_set.add_argument("value", help="配置值")

    # auth status/login/logout
    p_auth = sub.add_parser("auth", help="认证管理")
    p_auth_sub = p_auth.add_subparsers(dest="action")
    p_auth_status = p_auth_sub.add_parser("status", help="认证状态")
    p_auth_login = p_auth_sub.add_parser("login", help="登录")
    p_auth_login.add_argument("--user", default=None)
    p_auth_login.add_argument("--key", default=None)
    p_auth_logout = p_auth_sub.add_parser("logout", help="登出")

    # model list/info/download/disk
    p_model = sub.add_parser("model", help="模型管理")
    p_model_sub = p_model.add_subparsers(dest="action")
    p_model_list = p_model_sub.add_parser("list", help="模型列表")
    p_model_info = p_model_sub.add_parser("info", help="模型信息")
    p_model_info.add_argument("name", help="模型名称")
    p_model_download = p_model_sub.add_parser("download", help="模型下载")
    p_model_download.add_argument("name", help="模型名称")
    p_model_disk = p_model_sub.add_parser("disk", help="模型磁盘占用")

    # llm prompt/status/start/stop
    p_llm = sub.add_parser("llm", help="LLM 命令")
    p_llm_sub = p_llm.add_subparsers(dest="action")
    p_llm_prompt = p_llm_sub.add_parser("prompt", help="发送 prompt")
    p_llm_prompt.add_argument("text", help="prompt 文本")
    p_llm_prompt.add_argument("--system", default=None, help="system prompt")
    p_llm_prompt.add_argument("--temperature", default=None, help="temperature")
    p_llm_prompt.add_argument("--max-tokens", default=None, help="max_tokens")
    p_llm_status = p_llm_sub.add_parser("status", help="llama-server 状态")
    p_llm_start = p_llm_sub.add_parser("start", help="预热启动 VLM 服务器")
    p_llm_stop = p_llm_sub.add_parser("stop", help="停止 VLM 服务器")

    # vlm analyze/status/start/stop
    p_vlm = sub.add_parser("vlm", help="VLM 命令")
    p_vlm_sub = p_vlm.add_subparsers(dest="action")
    p_vlm_analyze = p_vlm_sub.add_parser("analyze", help="VLM 场景分析")
    p_vlm_analyze.add_argument("--prompt", default="", help="自定义 prompt")
    p_vlm_analyze.add_argument("--image", default=None, help="base64 图片数据（可选）")
    p_vlm_status = p_vlm_sub.add_parser("status", help="VLM 服务器状态")
    p_vlm_start = p_vlm_sub.add_parser("start", help="预热启动 VLM 服务器")
    p_vlm_stop = p_vlm_sub.add_parser("stop", help="停止 VLM 服务器")

    # nav <target>
    p_nav = sub.add_parser("nav", help="导航到目标页面")
    p_nav.add_argument("target", help="目标页面")

    # nav2 coords/entity/where/list-entities/list-maps — scrcpy-based 3D world navigation
    p_nav2 = sub.add_parser("nav2", help="3D 场景导航 (scrcpy)")
    p_nav2_sub = p_nav2.add_subparsers(dest="action")
    p_n2c = p_nav2_sub.add_parser("to_coords", help="导航到坐标")
    p_n2c.add_argument("map_name", help="地图名 (map01/map02/base01)")
    p_n2c.add_argument("x", type=float, help="目标 X")
    p_n2c.add_argument("y", type=float, help="目标 Y")
    p_n2c.add_argument("--level", default=None, help="层级 (lv001 等)")
    p_n2c.add_argument("--zone", default=None, help="zone_id 覆盖")
    p_n2e = p_nav2_sub.add_parser("to_entity", help="导航到实体")
    p_n2e.add_argument("name", help="实体名称/关键字")
    p_n2e.add_argument("--limit", type=int, default=10, help="最大候选数")
    p_n2w = p_nav2_sub.add_parser("where", help="当前玩家位置")
    p_n2l = p_nav2_sub.add_parser("list_entities", help="列出实体")
    p_n2l.add_argument("--category", default=None, help="分类筛选")
    p_n2l.add_argument("--map", default=None, dest="map_name", help="地图筛选")
    p_n2l.add_argument("--name", default=None, help="名称筛选")
    p_n2l.add_argument("--limit", type=int, default=50, help="最大返回数")
    p_n2m = p_nav2_sub.add_parser("list_maps", help="列出可用地图")

    return parser


def _json_dumps(result: Any) -> str:
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runtime = IstinaRuntime()

    try:
        if args.command in ("llm", "vlm") and getattr(args, "action", None) in ("start", "stop"):
            pass
        else:
            _auto_warmup(runtime, args)

        dispatch = CLIDispatch(runtime)
        result = dispatch.dispatch(args)
    except Exception as exc:
        result = {"status": "error", "message": str(exc)}

    sys.stdout.buffer.write((_json_dumps(result) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0 if result.get("status") == "success" else 1


def _auto_warmup(runtime: IstinaRuntime, args: argparse.Namespace) -> None:
    """根据子命令自动预热对应的推理后端。"""
    cmd = args.command
    if cmd == "llm":
        runtime.warmup_llm()
    elif cmd == "vlm":
        runtime.warmup_vlm()
    elif cmd in ("scene", "analyze"):
        if getattr(args, "action", None) == "analyze" and hasattr(args, "prompt"):
            runtime.warmup_vlm()
    elif cmd in ("daily", "harvest", "explore", "preset", "task", "nav", "nav2", "system", "device", "shell"):
        pass


if __name__ == "__main__":
    sys.exit(main())

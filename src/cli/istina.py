#!/usr/bin/env python3
"""IstinaAI unified CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.foundation.logger import get_logger
from core.foundation.paths import ensure_src_path
from core.service.runtime import IstinaRuntime
from cli.handlers import CLIDispatch, _handle_daily, _handle_harvest, _handle_analyze, _handle_explore

__all__ = [
    "build_parser",
    "main",
    "_auto_warmup",
    "_handle_daily",
    "_handle_harvest",
    "_handle_analyze",
    "_handle_explore",
]

ensure_src_path(__file__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="istina", description="IstinaAI unified CLI")
    parser.add_argument(
        "--config",
        default=None,
        help="Optional config path; runtime still defaults to config/client_config.json.",
    )

    sub = parser.add_subparsers(dest="command")

    p_sys = sub.add_parser("system", help="system commands")
    p_sys_sub = p_sys.add_subparsers(dest="action")
    p_sys_sub.add_parser("connect", help="connect device").add_argument("--serial", default=None)
    p_sys_sub.add_parser("disconnect", help="disconnect device").add_argument("--serial", default=None)
    p_sys_sub.add_parser("doctor", help="system doctor")
    p_sys_sub.add_parser("env", help="environment check")
    p_sys_sub.add_parser("disk", help="disk usage")
    p_sys_sub.add_parser("perf", help="performance check")

    p_daily = sub.add_parser("daily", help="daily flow")
    p_daily.add_argument("--options", default="{}", help="JSON options")
    p_daily.add_argument("--serial", default=None, help="device serial")
    p_harvest = sub.add_parser("harvest", help="harvest flow")
    p_harvest.add_argument("--options", default="{}", help="JSON options")
    p_harvest.add_argument("--serial", default=None, help="device serial")
    p_analyze = sub.add_parser("analyze", help="analyze flow")
    p_analyze.add_argument("--options", default="{}", help="JSON options")
    p_analyze.add_argument("--serial", default=None, help="device serial")
    p_explore = sub.add_parser("explore", help="explore flow")
    p_explore.add_argument("--options", default="{}", help="JSON options")
    p_explore.add_argument("--serial", default=None, help="device serial")

    p_ss = sub.add_parser("screenshot", help="take screenshot")
    p_ss.add_argument("--out", default=None, help="output file path")

    p_task = sub.add_parser("task", help="task commands")
    p_task_sub = p_task.add_subparsers(dest="action")
    p_task_run = p_task_sub.add_parser("run", help="run task")
    p_task_run.add_argument("name", help="task name")
    p_task_run.add_argument("--options", default="{}", help="JSON options")
    p_task_run.add_argument("--serial", default=None, help="device serial")
    p_task_run.add_argument("--timeout", type=float, default=None, help="task timeout in seconds")
    p_task_list = p_task_sub.add_parser("list", help="list tasks")
    p_task_list.add_argument("--serial", default=None, help="device serial")

    p_preset = sub.add_parser("preset", help="preset commands")
    p_preset_sub = p_preset.add_subparsers(dest="action")
    p_preset_run = p_preset_sub.add_parser("run", help="run preset")
    p_preset_run.add_argument("name", help="preset name")
    p_preset_run.add_argument("--serial", default=None, help="device serial")
    p_preset_list = p_preset_sub.add_parser("list", help="list presets")
    p_preset_list.add_argument("--serial", default=None, help="device serial")

    p_meta = sub.add_parser("metadata", help="metadata commands")
    p_meta_sub = p_meta.add_subparsers(dest="action")
    p_meta_list = p_meta_sub.add_parser("list", help="list tasks and presets together")
    p_meta_list.add_argument("--serial", default=None, help="device serial")

    p_dev = sub.add_parser("device", help="device commands")
    p_dev_sub = p_dev.add_subparsers(dest="action")
    p_dev_sub.add_parser("status", help="device status")
    p_dev_ss = p_dev_sub.add_parser("screenshot", help="device screenshot")
    p_dev_ss.add_argument("--out", default=None, help="output file path")
    p_dev_sub.add_parser("info", help="device info")
    p_dev_tap = p_dev_sub.add_parser("tap", help="tap screen")
    p_dev_tap.add_argument("x", type=int)
    p_dev_tap.add_argument("y", type=int)
    p_dev_swipe = p_dev_sub.add_parser("swipe", help="swipe screen")
    p_dev_swipe.add_argument("x1", type=int)
    p_dev_swipe.add_argument("y1", type=int)
    p_dev_swipe.add_argument("x2", type=int)
    p_dev_swipe.add_argument("y2", type=int)
    p_dev_swipe.add_argument("--duration", type=int, default=300)
    p_dev_keyevent = p_dev_sub.add_parser("keyevent", help="send keyevent")
    p_dev_keyevent.add_argument("key", help="keycode")
    p_dev_sub.add_parser("monitor", help="device monitor")

    p_shell = sub.add_parser("shell", help="adb shell command")
    p_shell.add_argument("cmd", help="shell command")

    p_gpu = sub.add_parser("gpu", help="gpu commands")
    p_gpu_sub = p_gpu.add_subparsers(dest="action")
    p_gpu_sub.add_parser("status", help="gpu status")
    p_gpu_sub.add_parser("monitor", help="gpu monitor")
    p_gpu_sub.add_parser("recommend", help="gpu recommendation")
    p_gpu_sub.add_parser("cuda-check", help="cuda check")

    p_scene = sub.add_parser("scene", help="scene commands")
    p_scene_sub = p_scene.add_subparsers(dest="action")
    p_scene_capture = p_scene_sub.add_parser("capture", help="capture scene")
    p_scene_capture.add_argument("--out", default=None)
    p_scene_nav = p_scene_sub.add_parser("nav", help="scene navigation")
    p_scene_nav.add_argument("--target", default=None)
    p_scene_analyze = p_scene_sub.add_parser("analyze", help="scene analyze")
    p_scene_analyze.add_argument("--options", default="{}", help="JSON options")
    p_scene_sub.add_parser("ocr", help="scene ocr")
    p_scene_explore = p_scene_sub.add_parser("explore", help="scene explore")
    p_scene_explore.add_argument("--options", default="{}", help="JSON options")
    p_scene_identify = p_scene_sub.add_parser("identify", help="identify current scene")
    p_scene_identify.add_argument("--image", default=None, help="base64 image data")
    p_scene_verify = p_scene_sub.add_parser("verify", help="verify scene")
    p_scene_verify.add_argument("expected", help="expected scene/page")
    p_scene_verify.add_argument("--image", default=None, help="base64 image data")
    p_scene_elements = p_scene_sub.add_parser("elements", help="analyze UI elements")
    p_scene_elements.add_argument("--image", default=None, help="base64 image data")
    p_scene_sub.add_parser("context", help="scene context")

    p_config = sub.add_parser("config", help="config commands")
    p_config_sub = p_config.add_subparsers(dest="action")
    p_config_get = p_config_sub.add_parser("get", help="get config value")
    p_config_get.add_argument("key", help="config key")
    p_config_set = p_config_sub.add_parser("set", help="set config value")
    p_config_set.add_argument("key", help="config key")
    p_config_set.add_argument("value", help="config value")

    p_auth = sub.add_parser("auth", help="auth commands")
    p_auth_sub = p_auth.add_subparsers(dest="action")
    p_auth_sub.add_parser("status", help="auth status")
    p_auth_login = p_auth_sub.add_parser("login", help="login")
    p_auth_login.add_argument("--user", default=None)
    p_auth_login.add_argument("--key", default=None)
    p_auth_sub.add_parser("logout", help="logout")

    p_model = sub.add_parser("model", help="model commands")
    p_model_sub = p_model.add_subparsers(dest="action")
    p_model_sub.add_parser("list", help="list models")
    p_model_info = p_model_sub.add_parser("info", help="model info")
    p_model_info.add_argument("name", help="model name")
    p_model_download = p_model_sub.add_parser("download", help="download model")
    p_model_download.add_argument("name", help="model name")
    p_model_sub.add_parser("disk", help="model disk usage")

    p_llm = sub.add_parser("llm", help="llm commands")
    p_llm_sub = p_llm.add_subparsers(dest="action")
    p_llm_prompt = p_llm_sub.add_parser("prompt", help="send prompt")
    p_llm_prompt.add_argument("text", help="prompt text")
    p_llm_prompt.add_argument("--system", default=None, help="system prompt")
    p_llm_prompt.add_argument("--temperature", default=None, help="temperature")
    p_llm_prompt.add_argument("--max-tokens", default=None, help="max tokens")
    p_llm_prompt.add_argument("--image", default=None, help="base64 image data")
    p_llm_sub.add_parser("status", help="llama server status")
    p_llm_sub.add_parser("start", help="start llm server")
    p_llm_sub.add_parser("stop", help="stop llm server")

    p_nav = sub.add_parser("nav", help="navigate to target")
    p_nav.add_argument("target", help="target page")

    p_nav2 = sub.add_parser("nav2", help="3D navigation")
    p_nav2_sub = p_nav2.add_subparsers(dest="action")
    p_n2c = p_nav2_sub.add_parser("to_coords", help="navigate to coords")
    p_n2c.add_argument("map_name", help="map name")
    p_n2c.add_argument("x", type=float)
    p_n2c.add_argument("y", type=float)
    p_n2c.add_argument("--level", default=None, help="level id")
    p_n2c.add_argument("--zone", default=None, help="zone override")
    p_n2e = p_nav2_sub.add_parser("to_entity", help="navigate to entity")
    p_n2e.add_argument("name", help="entity name")
    p_n2e.add_argument("--limit", type=int, default=10)
    p_nav2_sub.add_parser("where", help="current location")
    p_n2l = p_nav2_sub.add_parser("list_entities", help="list entities")
    p_n2l.add_argument("--category", default=None)
    p_n2l.add_argument("--map", default=None, dest="map_name")
    p_n2l.add_argument("--name", default=None)
    p_n2l.add_argument("--limit", type=int, default=50)
    p_nav2_sub.add_parser("list_maps", help="list maps")


    p_nav3 = sub.add_parser("nav3", help="VLM-driven walking navigation")
    p_nav3_sub = p_nav3.add_subparsers(dest="action")
    p_n3w = p_nav3_sub.add_parser("walk", help="VLM walk to coordinates")
    p_n3w.add_argument("map_name", help="map name")
    p_n3w.add_argument("x", type=float)
    p_n3w.add_argument("y", type=float)
    p_n3w.add_argument("--level", default=None, help="level id")
    p_n3w.add_argument("--zone", default=None, help="zone override")
    p_n3w.add_argument("--max-steps", type=int, default=40)
    p_n3e = p_nav3_sub.add_parser("to_entity", help="VLM walk to entity")
    p_n3e.add_argument("name", help="entity name")
    p_n3e.add_argument("--max-steps", type=int, default=40)
    p_n3e.add_argument("--limit", type=int, default=10)
    p_nav3_sub.add_parser("status", help="VLM nav availability")
    return parser


def _json_dumps(result: Any) -> str:
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    original_stdout_fd: Optional[int] = None
    stdout_redirected = False
    try:
        sys.stdout.flush()
        original_stdout_fd = os.dup(sys.stdout.fileno())
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        stdout_redirected = True
    except Exception:
        original_stdout_fd = None
        stdout_redirected = False

    try:
        runtime = IstinaRuntime(config_path=args.config)
        if not (args.command == "llm" and getattr(args, "action", None) in ("start", "stop")):
            _auto_warmup(runtime, args)
        result = CLIDispatch(runtime).dispatch(args)
    except Exception as exc:
        result = {"status": "error", "message": str(exc)}
    finally:
        if stdout_redirected and original_stdout_fd is not None:
            try:
                sys.stdout.flush()
                os.dup2(original_stdout_fd, sys.stdout.fileno())
            finally:
                os.close(original_stdout_fd)

    sys.stdout.buffer.write((_json_dumps(result) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0 if isinstance(result, dict) and result.get("status") == "success" else 1


def _interactive_loop(parser: argparse.ArgumentParser) -> int:
    runtime = IstinaRuntime()
    buffer = ""
    self_logger = get_logger(__name__)
    while True:
        try:
            chunk = sys.stdin.read(1)
        except Exception as exc:
            self_logger.error("CLI 交互循环: stdin 读取异常", error=str(exc))
            break
        if not chunk:
            self_logger.info("CLI 交互循环: stdin EOF")
            break
        buffer += chunk
        if chunk == "\n":
            line = buffer.strip()
            buffer = ""
            if not line:
                continue
            self_logger.info("CLI 交互循环: 收到命令", command=line)
            result = None
            try:
                args = parser.parse_args(line.split())
                self_logger.info("CLI 交互循环: 解析成功", command=getattr(args, 'command', None), action=getattr(args, 'action', None))
                result = CLIDispatch(runtime).dispatch(args)
                self_logger.info("CLI 交互循环: 执行完成", status=result.get("status") if isinstance(result, dict) else None)
            except SystemExit:
                result = {"status": "error", "message": "invalid command"}
                self_logger.warning("CLI 交互循环: 参数解析失败", command=line)
            except Exception as exc:
                result = {"status": "error", "message": str(exc)}
                self_logger.error("CLI 交互循环: 执行异常", command=line, error=str(exc))
            try:
                sys.stdout.write(_json_dumps(result) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                self_logger.error("CLI 交互循环: stdout 写入异常", error=str(exc))
    return 0


def _auto_warmup(runtime: IstinaRuntime, args: argparse.Namespace) -> None:
    if args.command == "llm":
        runtime.warmup_llm()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        parser = build_parser()
        sys.exit(_interactive_loop(parser))
    sys.exit(main())

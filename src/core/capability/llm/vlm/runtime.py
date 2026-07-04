from __future__ import annotations

from typing import Any

from core.capability.llm.runtime import LlamaServerRuntime


class VlmServerRuntime(LlamaServerRuntime):
    """VLM（多模态 LLM）服务器运行时。

    继承 LlamaServerRuntime，覆盖：
    - __init__()         →  从 VLM 配置段读取端口
    - _get_llm_config()  →  读取 VLM 配置段
    - _build_args()      →  上下文固定 8k + 追加 --mmproj
    - _resolve_exe()     →  VLM 不做 MLA 优化判断
    """

    CONFIG_SECTION = "vlm"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        vlm_cfg = self._get_vlm_section()
        self._default_port = int(vlm_cfg.get("port", 9997))

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------

    def _get_llm_config(self) -> dict[str, Any]:
        cfg = self._get_vlm_section()
        cfg["context_size"] = 16384
        return cfg

    def _get_vlm_section(self) -> dict[str, Any]:
        if not isinstance(self._config, dict):
            return {}
        cfg = self._config.get(self.CONFIG_SECTION, {}).copy()
        llm_cfg = self._config.get("llm", {})
        for k, v in llm_cfg.items():
            cfg.setdefault(k, v)
        return cfg

    # ------------------------------------------------------------------
    # 命令行参数
    # ------------------------------------------------------------------

    def _build_args(self, exe: Any, model_path: str, llm_cfg: dict[str, Any], force_cpu: bool = False) -> list[str]:
        args = super()._build_args(exe, model_path, llm_cfg, force_cpu)
        vlm_cfg = self._get_vlm_section()
        mmproj = vlm_cfg.get("mmproj_path")
        if mmproj:
            args.extend(["--mmproj", mmproj])
        return args

    # ------------------------------------------------------------------
    # 可执行文件
    # ------------------------------------------------------------------

    def _resolve_exe(self) -> Any:
        vlm_cfg = self._get_vlm_section()
        custom = vlm_cfg.get("server_path")
        if custom:
            return custom
        return super()._resolve_exe()

"""
本地日志管理器

将日志写入本地文件，不依赖 IstinaPlatform。
替代云端 LogManager。
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: float
    level: str
    category: str
    message: str
    context: Dict[str, Any]
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class LocalLogManager:
    """本地日志管理器

    将日志写入本地文件，支持按类别和会话组织。
    """

    def __init__(self, log_dir: str, session_id: Optional[str] = None, user_id: Optional[str] = None):
        """初始化本地日志管理器

        Args:
            log_dir: 日志目录路径
            session_id: 会话 ID（可选）
            user_id: 用户 ID（可选）
        """
        self.log_dir = Path(log_dir)
        self.session_id = session_id
        self.user_id = user_id or "local_user"
        
        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 按类别的日志文件
        self._category_files: Dict[str, Path] = {}
        
        # 当前会话日志文件
        if session_id:
            self._session_log = self.log_dir / f"session_{session_id}.jsonl"
        else:
            self._session_log = self.log_dir / f"session_{int(time.time())}.jsonl"
        
        # 通用日志文件
        self._general_log = self.log_dir / "general.jsonl"

    def _get_category_file(self, category: str) -> Path:
        """获取类别日志文件"""
        if category not in self._category_files:
            safe_category = category.replace("/", "_").replace("\\", "_")
            self._category_files[category] = self.log_dir / f"{safe_category}.jsonl"
        return self._category_files[category]

    def log(self, level: str, category: str, message: str, context: Dict[str, Any] = None):
        """记录日志

        Args:
            level: 日志级别 (INFO/WARNING/ERROR/DEBUG)
            category: 日志类别
            message: 日志消息
            context: 上下文信息
        """
        entry = LogEntry(
            timestamp=time.time(),
            level=level,
            category=category,
            message=message,
            context=context or {},
            session_id=self.session_id,
            user_id=self.user_id,
        )

        # 写入会话日志
        with open(self._session_log, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")

        # 写入通用日志
        with open(self._general_log, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")

        # 写入类别日志
        category_file = self._get_category_file(category)
        with open(category_file, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")

    def info(self, category: str, message: str, context: Dict[str, Any] = None):
        """INFO 级别日志"""
        self.log("INFO", category, message, context)

    def warning(self, category: str, message: str, context: Dict[str, Any] = None):
        """WARNING 级别日志"""
        self.log("WARNING", category, message, context)

    def error(self, category: str, message: str, context: Dict[str, Any] = None):
        """ERROR 级别日志"""
        self.log("ERROR", category, message, context)

    def debug(self, category: str, message: str, context: Dict[str, Any] = None):
        """DEBUG 级别日志"""
        self.log("DEBUG", category, message, context)

    def get_logs(self, category: str = None, level: str = None, 
                 start_time: float = None, end_time: float = None) -> List[Dict[str, Any]]:
        """获取日志

        Args:
            category: 过滤类别
            level: 过滤级别
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            日志条目列表
        """
        logs = []
        
        # 读取会话日志
        if self._session_log.exists():
            with open(self._session_log, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
        
        # 过滤
        if category:
            logs = [l for l in logs if l.get("category") == category]
        if level:
            logs = [l for l in logs if l.get("level") == level]
        if start_time:
            logs = [l for l in logs if l.get("timestamp", 0) >= start_time]
        if end_time:
            logs = [l for l in logs if l.get("timestamp", 0) <= end_time]
        
        return logs

    def export_logs(self, output_path: str, format: str = "json"):
        """导出日志

        Args:
            output_path: 输出文件路径
            format: 导出格式 (json/jsonl)
        """
        logs = self.get_logs()
        
        if format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        else:  # jsonl
            with open(output_path, "w", encoding="utf-8") as f:
                for log in logs:
                    f.write(json.dumps(log, ensure_ascii=False) + "\n")

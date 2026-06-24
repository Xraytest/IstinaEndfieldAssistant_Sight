"""
配置管理器 - 支持动态配置和条件装饰器
参考 StarRailCopilot 的 Config 装饰器设计
"""
import json
import os
from typing import Any, Dict, Callable, Optional
from functools import wraps
from pathlib import Path

from core.foundation.logger import get_logger, LogCategory

logger = get_logger()


class ConfigManager:
    """
    配置管理器

    功能：
    - 加载 JSON 配置文件
    - 支持嵌套键访问（使用点号分隔）
    - 监听配置变更
    - 条件装饰器支持
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径（JSON）
        """
        self._config: Dict[str, Any] = {}
        self._listeners: Dict[str, Callable] = {}
        self.config_path = config_path

        if config_path and os.path.exists(config_path):
            self.load_from_file(config_path)

    def load_from_file(self, path: str) -> bool:
        """
        从文件加载配置

        Args:
            path: 文件路径

        Returns:
            bool: 是否成功
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            self.config_path = path
            self.logger.info(LogCategory.MAIN, "配置加载成功", path=path)
            return True
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "配置加载失败", path=path, error=str(e))
            return False

    def save_to_file(self, path: Optional[str] = None) -> bool:
        """
        保存配置到文件

        Args:
            path: 文件路径，None 表示使用原路径

        Returns:
            bool: 是否成功
        """
        save_path = path or self.config_path
        if not save_path:
            self.logger.error(LogCategory.MAIN, "保存配置失败：未指定路径")
            return False

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            self.logger.info(LogCategory.MAIN, "配置保存成功", path=save_path)
            return True
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "配置保存失败", path=save_path, error=str(e))
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键（支持点号分隔，如 'device.emulator.method'）
            default: 默认值

        Returns:
            配置值或默认值
        """
        keys = key.split('.')
        value = self._config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any, save: bool = False) -> bool:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
            save: 是否立即保存到文件

        Returns:
            bool: 是否成功
        """
        keys = key.split('.')
        config = self._config

        # 遍历到倒数第二层
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # 设置最终值
        old_value = config.get(keys[-1])
        config[keys[-1]] = value

        # 触发监听器
        self._notify_listeners(key, value, old_value)

        if save:
            self.save_to_file()

        return True

    def update(self, updates: Dict[str, Any], save: bool = False) -> None:
        """
        批量更新配置

        Args:
            updates: 更新字典（支持嵌套）
            save: 是否立即保存
        """
        self._deep_update(self._config, updates)
        if save:
            self.save_to_file()

    def _deep_update(self, target: Dict, source: Dict) -> None:
        """递归更新字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value

    def add_listener(self, key: str, callback: Callable[[str, Any, Any], None]) -> None:
        """
        添加配置变更监听器

        Args:
            key: 监听的配置键（支持通配符 '*'）
            callback: 回调函数(key, new_value, old_value)
        """
        if key not in self._listeners:
            self._listeners[key] = []
        self._listeners[key].append(callback)

    def remove_listener(self, key: str, callback: Callable) -> bool:
        """
        移除监听器

        Returns:
            bool: 是否成功移除
        """
        if key in self._listeners and callback in self._listeners[key]:
            self._listeners[key].remove(callback)
            return True
        return False

    def _notify_listeners(self, key: str, new_value: Any, old_value: Any) -> None:
        """通知所有监听器"""
        # 精确匹配
        if key in self._listeners:
            for callback in self._listeners[key]:
                try:
                    callback(key, new_value, old_value)
                except Exception as e:
                    logger.warning(LogCategory.MAIN, "配置监听器执行异常", key=key, error=str(e))

        # 通配符匹配
        for pattern, callbacks in self._listeners.items():
            if pattern == '*':
                for callback in callbacks:
                    try:
                        callback(key, new_value, old_value)
                    except Exception as e:
                        logger.warning(LogCategory.MAIN, "配置监听器执行异常", key=key, error=str(e))

    def as_dict(self) -> Dict[str, Any]:
        """返回配置字典的副本"""
        import copy
        return copy.deepcopy(self._config)

    def reload(self) -> bool:
        """重新从文件加载配置"""
        if self.config_path:
            return self.load_from_file(self.config_path)
        return False


# 条件装饰器（参考 StarRailCopilot 的 Config.when）
class ConfigCondition:
    """
    配置条件装饰器

    用法：
        @Config.when(DEVICE_OVER_HTTP=False)
        def some_method(self):
            ...
    """

    @staticmethod
    def when(condition: str):
        """
        条件装饰器工厂

        Args:
            condition: 条件表达式，如 "DEVICE_OVER_HTTP=False" 或 "self.config.get('screen.method') == 'scrcpy'"

        Returns:
            装饰器
        """
        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                # 评估条件
                try:
                    # 支持简单的属性检查
                    if '=' in condition:
                        left, right = condition.split('=', 1)
                        left = left.strip()
                        right = right.strip().strip("'\"")
                        
                        # 从 self 获取属性或配置
                        if hasattr(self, left):
                            actual = getattr(self, left)
                        elif hasattr(self, 'config') and callable(getattr(self.config, 'get', None)):
                            actual = self.config.get(left)
                        else:
                            logger.warning(LogCategory.MAIN, "条件评估失败：无法获取属性", attr=left)
                            return func(self, *args, **kwargs)

                        # 类型转换
                        if isinstance(actual, bool):
                            right = right.lower() in ('true', '1', 'yes')
                        elif isinstance(actual, int):
                            right = int(right)
                        elif isinstance(actual, float):
                            right = float(right)

                        condition_met = (actual == right)
                    else:
                        # 复杂条件，使用 eval（注意安全风险）
                        condition_met = eval(condition, {}, {'self': self})
                except Exception as e:
                    logger.warning(LogCategory.MAIN, "条件评估异常", error=str(e))
                    return func(self, *args, **kwargs)

                if condition_met:
                    return func(self, *args, **kwargs)
                else:
                    # 条件不满足，跳过执行
                    logger.debug(LogCategory.MAIN, "条件不满足，跳过方法", func=func.__name__, condition=condition)
                    return None

            return wrapper
        return decorator


# 全局配置实例（可选）
_global_config: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器"""
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager()
    return _global_config


def set_global_config(config: ConfigManager):
    """设置全局配置管理器"""
    global _global_config
    _global_config = config
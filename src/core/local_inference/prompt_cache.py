"""
Prompt缓存管理器 - 管理prompt和响应的缓存

使用LRU策略管理缓存，支持任务链完成后自动清除
"""
import hashlib
import json
import time
from typing import Any, Optional, Dict, OrderedDict as OrderedDictType
from collections import OrderedDict
from dataclasses import dataclass, field

# 尝试导入日志模块
from core.logger import get_logger, LogCategory
logger = get_logger()


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    def touch(self):
        """更新访问信息"""
        self.access_count += 1
        self.last_access = time.time()


class PromptCache:
    """
    Prompt缓存管理器
    
    职责:
    1. 缓存prompt和对应响应
    2. 管理缓存生命周期(LRU策略)
    3. 任务链完成后自动清除
    4. 提供缓存统计
    """
    
    def __init__(self, max_size: int = 100, namespace: str = "default"):
        """
        初始化缓存管理器
        
        Args:
            max_size: 最大缓存条目数
            namespace: 缓存命名空间，用于隔离不同任务链的缓存
        """
        self._max_size = max_size
        self._namespace = namespace
        self._cache: OrderedDictType[str, CacheEntry] = OrderedDict()
        self._hit_count = 0
        self._miss_count = 0
        self._set_count = 0
        self._evict_count = 0
        
    def _generate_key(self, prompt: str, image_hash: Optional[str] = None) -> str:
        """
        生成缓存键
        
        Args:
            prompt: prompt文本
            image_hash: 图像哈希值(可选)
            
        Returns:
            缓存键字符串
        """
        key_data = f"{self._namespace}:{prompt}"
        if image_hash:
            key_data += f":{image_hash}"
        
        # 使用SHA256生成固定长度的键
        return hashlib.sha256(key_data.encode('utf-8')).hexdigest()[:32]
    
    def get(self, prompt: str, image_hash: Optional[str] = None) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            prompt: prompt文本
            image_hash: 图像哈希值
            
        Returns:
            缓存的值，如果不存在返回None
        """
        key = self._generate_key(prompt, image_hash)
        
        if key in self._cache:
            entry = self._cache[key]
            entry.touch()
            
            # 移动到末尾（LRU）
            self._cache.move_to_end(key)
            
            self._hit_count += 1
            logger.debug(LogCategory.MAIN, "Prompt缓存命中", 
                        key=key[:8], access_count=entry.access_count)
            return entry.value
        
        self._miss_count += 1
        logger.debug(LogCategory.MAIN, "Prompt缓存未命中", key=key[:8])
        return None
    
    def set(self, prompt: str, value: Any, image_hash: Optional[str] = None) -> bool:
        """
        设置缓存值
        
        Args:
            prompt: prompt文本
            value: 要缓存的值
            image_hash: 图像哈希值
            
        Returns:
            是否成功设置
        """
        key = self._generate_key(prompt, image_hash)
        
        # 如果已存在，更新值并移动到末尾
        if key in self._cache:
            entry = self._cache[key]
            entry.value = value
            entry.touch()
            self._cache.move_to_end(key)
            logger.debug(LogCategory.MAIN, "Prompt缓存更新", key=key[:8])
            return True
        
        # 检查是否需要淘汰旧条目
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        
        # 添加新条目
        entry = CacheEntry(key=key, value=value)
        self._cache[key] = entry
        self._set_count += 1
        
        logger.debug(LogCategory.MAIN, "Prompt缓存设置", 
                    key=key[:8], cache_size=len(self._cache))
        return True
    
    def _evict_oldest(self):
        """淘汰最旧的缓存条目"""
        if not self._cache:
            return
        
        # 移除第一个条目（最旧的）
        oldest_key, oldest_entry = self._cache.popitem(last=False)
        self._evict_count += 1
        
        logger.debug(LogCategory.MAIN, "Prompt缓存淘汰", 
                    key=oldest_key[:8], 
                    age_seconds=time.time() - oldest_entry.timestamp)
    
    def clear(self):
        """清除所有缓存"""
        old_size = len(self._cache)
        self._cache.clear()
        
        logger.info(LogCategory.MAIN, "Prompt缓存已清除", 
                   cleared_entries=old_size, namespace=self._namespace)
    
    def clear_namespace(self, namespace: str):
        """清除指定命名空间的缓存"""
        keys_to_remove = [
            k for k in self._cache.keys() 
            if k.startswith(f"{namespace}:")
        ]
        
        for key in keys_to_remove:
            del self._cache[key]
        
        logger.info(LogCategory.MAIN, "Prompt命名空间缓存已清除", 
                   namespace=namespace, cleared_entries=len(keys_to_remove))
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        total_requests = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total_requests if total_requests > 0 else 0
        
        # 计算平均条目年龄
        current_time = time.time()
        if self._cache:
            avg_age = sum(
                current_time - entry.timestamp 
                for entry in self._cache.values()
            ) / len(self._cache)
        else:
            avg_age = 0
        
        return {
            "namespace": self._namespace,
            "size": len(self._cache),
            "max_size": self._max_size,
            "utilization": len(self._cache) / self._max_size,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "set_count": self._set_count,
            "evict_count": self._evict_count,
            "hit_rate": round(hit_rate, 4),
            "avg_entry_age_seconds": round(avg_age, 2),
        }
    
    def get_size(self) -> int:
        """获取当前缓存大小"""
        return len(self._cache)
    
    def is_full(self) -> bool:
        """检查缓存是否已满"""
        return len(self._cache) >= self._max_size
    
    def contains(self, prompt: str, image_hash: Optional[str] = None) -> bool:
        """检查是否包含指定prompt的缓存"""
        key = self._generate_key(prompt, image_hash)
        return key in self._cache
    
    def remove(self, prompt: str, image_hash: Optional[str] = None) -> bool:
        """移除指定缓存条目"""
        key = self._generate_key(prompt, image_hash)
        
        if key in self._cache:
            del self._cache[key]
            logger.debug(LogCategory.MAIN, "Prompt缓存条目已移除", key=key[:8])
            return True
        return False
    
    def get_all_keys(self) -> list:
        """获取所有缓存键（调试用）"""
        return list(self._cache.keys())


class TaskChainCacheManager:
    """
    任务链缓存管理器
    
    管理多个任务链的缓存，支持任务链完成后自动清理
    """
    
    def __init__(self, max_size_per_chain: int = 50):
        """
        初始化任务链缓存管理器
        
        Args:
            max_size_per_chain: 每个任务链的最大缓存条目数
        """
        self._max_size_per_chain = max_size_per_chain
        self._caches: Dict[str, PromptCache] = {}
        self._active_chain: Optional[str] = None
        
    def get_cache(self, chain_id: str) -> PromptCache:
        """获取或创建任务链的缓存"""
        if chain_id not in self._caches:
            self._caches[chain_id] = PromptCache(
                max_size=self._max_size_per_chain,
                namespace=chain_id
            )
            logger.info(LogCategory.MAIN, "创建任务链缓存", chain_id=chain_id)
        
        return self._caches[chain_id]
    
    def set_active_chain(self, chain_id: str):
        """设置当前活动的任务链"""
        self._active_chain = chain_id
        logger.debug(LogCategory.MAIN, "设置活动任务链", chain_id=chain_id)
    
    def get_active_cache(self) -> Optional[PromptCache]:
        """获取当前活动任务链的缓存"""
        if self._active_chain is None:
            return None
        return self.get_cache(self._active_chain)
    
    def clear_chain_cache(self, chain_id: str):
        """清除指定任务链的缓存"""
        if chain_id in self._caches:
            self._caches[chain_id].clear()
            logger.info(LogCategory.MAIN, "任务链缓存已清除", chain_id=chain_id)
    
    def remove_chain_cache(self, chain_id: str):
        """移除指定任务链的缓存（任务链完成后调用）"""
        if chain_id in self._caches:
            del self._caches[chain_id]
            logger.info(LogCategory.MAIN, "任务链缓存已移除", chain_id=chain_id)
    
    def clear_all(self):
        """清除所有任务链缓存"""
        for cache in self._caches.values():
            cache.clear()
        self._caches.clear()
        self._active_chain = None
        logger.info(LogCategory.MAIN, "所有任务链缓存已清除")
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有任务链的缓存统计"""
        return {
            chain_id: cache.get_cache_stats()
            for chain_id, cache in self._caches.items()
        }


# 便捷函数
def create_cache(max_size: int = 100, namespace: str = "default") -> PromptCache:
    """创建缓存实例"""
    return PromptCache(max_size=max_size, namespace=namespace)


def create_task_chain_manager(max_size_per_chain: int = 50) -> TaskChainCacheManager:
    """创建任务链缓存管理器"""
    return TaskChainCacheManager(max_size_per_chain=max_size_per_chain)


if __name__ == "__main__":
    # 测试Prompt缓存
    print("=" * 60)
    print("Prompt缓存测试")
    print("=" * 60)
    
    cache = PromptCache(max_size=5, namespace="test")
    
    # 测试设置和获取
    print("\n1. 测试基本设置和获取:")
    cache.set("prompt1", {"result": "response1"})
    cache.set("prompt2", {"result": "response2"})
    
    result1 = cache.get("prompt1")
    print(f"  prompt1: {result1}")
    
    result2 = cache.get("prompt2")
    print(f"  prompt2: {result2}")
    
    # 测试缓存命中
    print("\n2. 测试缓存命中:")
    result1_again = cache.get("prompt1")
    print(f"  prompt1 (第二次): {result1_again}")
    
    # 测试LRU淘汰
    print("\n3. 测试LRU淘汰:")
    for i in range(3, 8):
        cache.set(f"prompt{i}", {"result": f"response{i}"})
        print(f"  添加 prompt{i}")
    
    stats = cache.get_cache_stats()
    print(f"\n  缓存统计: size={stats['size']}, max_size={stats['max_size']}")
    
    # prompt1应该被淘汰了
    result1_after = cache.get("prompt1")
    print(f"  prompt1 (淘汰后): {result1_after}")
    
    # 测试统计
    print("\n4. 测试统计信息:")
    stats = cache.get_cache_stats()
    print(f"  命中次数: {stats['hit_count']}")
    print(f"  未命中次数: {stats['miss_count']}")
    print(f"  命中率: {stats['hit_rate']:.2%}")
    
    # 测试任务链缓存管理器
    print("\n5. 测试任务链缓存管理器:")
    manager = TaskChainCacheManager(max_size_per_chain=3)
    
    manager.set_active_chain("chain1")
    active_cache = manager.get_active_cache()
    active_cache.set("task1", {"action": "click"})
    active_cache.set("task2", {"action": "swipe"})
    
    print(f"  chain1缓存大小: {active_cache.get_size()}")
    
    manager.set_active_chain("chain2")
    active_cache2 = manager.get_active_cache()
    active_cache2.set("task1", {"action": "input"})
    
    print(f"  chain2缓存大小: {active_cache2.get_size()}")
    
    # 清除chain1缓存
    manager.clear_chain_cache("chain1")
    print(f"  chain1清除后大小: {manager.get_cache('chain1').get_size()}")
    
    print("\n" + "=" * 60)

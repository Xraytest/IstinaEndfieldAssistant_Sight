"""
异步推理工作线程 - 在后台线程中执行本地推理

使用PyQt6的QThread实现异步推理，不阻塞主事件循环
支持任务队列、取消任务、超时机制等功能
"""
import os
import sys
import time
import queue
import threading
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
from core.foundation.utils.paths import ensure_src_path

# 添加项目根目录到路径
ensure_src_path(__file__)

try:
    from PyQt6.QtCore import QThread, pyqtSignal, QObject, QMutex, QWaitCondition, Qt
except ImportError:
    # 用于非PyQt环境测试
    class QThread:
        pass
    class QObject:
        pass
    class QMutex:
        def lock(self): pass
        def unlock(self): pass
        def tryLock(self, timeout=0): return True
    class QWaitCondition:
        def wait(self, mutex, timeout=0): pass
        def wakeOne(self): pass
        def wakeAll(self): pass
    def pyqtSignal(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from core.foundation.logger import get_logger, LogCategory
logger = get_logger()


class TaskPriority(Enum):
    """任务优先级枚举"""
    CRITICAL = 0    # 关键任务，最高优先级
    HIGH = 1        # 高优先级
    NORMAL = 2      # 普通优先级
    LOW = 3         # 低优先级
    BACKGROUND = 4  # 后台任务，最低优先级


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = auto()      # 等待中
    RUNNING = auto()      # 运行中
    COMPLETED = auto()    # 已完成
    CANCELLED = auto()    # 已取消
    FAILED = auto()       # 失败
    TIMEOUT = auto()      # 超时


@dataclass
class InferenceTask:
    """推理任务数据类"""
    task_id: str
    image_data: str
    task_context: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: float = 60.0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    progress_percent: int = 0
    
    def __post_init__(self):
        """初始化后处理"""
        if isinstance(self.priority, int):
            self.priority = TaskPriority(self.priority)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "priority": self.priority.name,
            "status": self.status.name,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress_percent": self.progress_percent,
            "has_result": self.result is not None,
            "error_message": self.error_message
        }
    
    def is_expired(self) -> bool:
        """检查任务是否已超时"""
        if self.status != TaskStatus.RUNNING or self.started_at is None:
            return False
        elapsed = time.time() - self.started_at
        return elapsed > self.timeout_seconds


class AsyncInferenceWorker(QThread):
    """
    异步推理工作线程
    
    职责:
    1. 在后台线程中执行本地推理
    2. 管理推理任务队列
    3. 通过信号通知主线程结果
    4. 支持任务取消和超时
    5. 提供详细的进度反馈
    
    信号:
    - result_ready: 推理完成，返回结果
    - error_occurred: 推理出错
    - progress_updated: 进度更新
    - task_started: 任务开始
    - task_cancelled: 任务取消
    - queue_changed: 队列状态变化
    """
    
    # 定义信号
    result_ready = pyqtSignal(str, dict)  # task_id, result
    error_occurred = pyqtSignal(str, str)  # task_id, error_message
    progress_updated = pyqtSignal(str, int)  # task_id, progress_percent
    task_started = pyqtSignal(str)  # task_id
    task_cancelled = pyqtSignal(str)  # task_id
    queue_changed = pyqtSignal(int, int)  # queue_size, active_count
    worker_status_changed = pyqtSignal(str)  # status
    
    def __init__(self, local_engine: Any, parent: Optional[QObject] = None):
        """
        初始化异步推理工作线程
        
        Args:
            local_engine: 本地推理引擎实例
            parent: 父QObject
        """
        super().__init__(parent)
        
        self._local_engine = local_engine
        self._task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._current_task: Optional[InferenceTask] = None
        self._running = False
        self._paused = False
        
        # 任务管理
        self._tasks: Dict[str, InferenceTask] = {}
        self._cancelled_tasks: set = set()
        self._task_lock = threading.Lock()
        
        # 线程同步
        self._mutex = QMutex()
        self._wait_condition = QWaitCondition()
        
        # 统计信息
        self._stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "timeout_tasks": 0,
            "total_inference_time_ms": 0.0
        }
        
        # 配置
        self._max_concurrent = 1  # 当前只支持串行处理
        self._check_interval_ms = 100  # 检查间隔
        
        logger.info(LogCategory.MAIN, "异步推理工作线程初始化完成")
    
    def add_task(
        self,
        task_id: str,
        image_data: str,
        task_context: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_seconds: float = 60.0
    ) -> bool:
        """
        添加推理任务到队列
        
        Args:
            task_id: 任务唯一标识
            image_data: Base64编码的图像数据
            task_context: 任务上下文，包含prompt等信息
            priority: 任务优先级
            timeout_seconds: 超时时间（秒）
            
        Returns:
            是否添加成功
        """
        try:
            with self._task_lock:
                # 检查任务ID是否已存在
                if task_id in self._tasks:
                    existing_task = self._tasks[task_id]
                    if existing_task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                        logger.warning(LogCategory.INFERENCE, "任务已存在", task_id=task_id)
                        return False
                
                # 创建任务
                task = InferenceTask(
                    task_id=task_id,
                    image_data=image_data,
                    task_context=task_context,
                    priority=priority,
                    timeout_seconds=timeout_seconds
                )
                
                # 添加到任务字典
                self._tasks[task_id] = task
                
                # 添加到优先级队列 (priority, timestamp, task)
                # 使用timestamp保证相同优先级的FIFO顺序
                # 确保priority是TaskPriority枚举类型
                if isinstance(priority, TaskPriority):
                    priority_value = priority.value
                    priority_name = priority.name
                else:
                    # 如果是字符串或其他类型，转换为枚举
                    try:
                        if isinstance(priority, str):
                            priority_enum = TaskPriority[priority.upper()]
                        else:
                            priority_enum = TaskPriority(priority)
                        priority_value = priority_enum.value
                        priority_name = priority_enum.name
                    except (KeyError, ValueError):
                        # 转换失败，使用默认优先级
                        priority_value = TaskPriority.NORMAL.value
                        priority_name = TaskPriority.NORMAL.name
                
                self._task_queue.put((priority_value, time.time(), task))
                
                self._stats["total_tasks"] += 1
                
                # 确保priority是TaskPriority枚举类型用于日志记录
                if isinstance(priority, TaskPriority):
                    priority_name = priority.name
                else:
                    try:
                        if isinstance(priority, str):
                            priority_name = TaskPriority[priority.upper()].name
                        else:
                            priority_name = TaskPriority(priority).name
                    except (KeyError, ValueError):
                        priority_name = TaskPriority.NORMAL.name
                
                logger.info(LogCategory.INFERENCE, "任务已添加到队列",
                          task_id=task_id,
                          priority=priority_name,
                          queue_size=self._task_queue.qsize())
                
                # 通知队列变化
                self._emit_queue_changed()
                
                # 唤醒工作线程
                self._mutex.lock()
                self._wait_condition.wakeOne()
                self._mutex.unlock()
                
                return True
                
        except Exception as e:
            logger.exception(LogCategory.INFERENCE, "添加任务失败", 
                           task_id=task_id, error=str(e))
            return False
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消指定任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否取消成功
        """
        try:
            with self._task_lock:
                if task_id not in self._tasks:
                    logger.warning(LogCategory.INFERENCE, "任务不存在", task_id=task_id)
                    return False
                
                task = self._tasks[task_id]
                
                # 检查任务状态
                if task.status == TaskStatus.COMPLETED:
                    logger.info(LogCategory.INFERENCE, "任务已完成，无法取消", task_id=task_id)
                    return False
                
                if task.status == TaskStatus.CANCELLED:
                    logger.info(LogCategory.INFERENCE, "任务已取消", task_id=task_id)
                    return True
                
                # 标记为取消
                task.status = TaskStatus.CANCELLED
                self._cancelled_tasks.add(task_id)
                
                # 如果是当前运行的任务，需要中断
                if self._current_task and self._current_task.task_id == task_id:
                    logger.info(LogCategory.INFERENCE, "取消正在运行的任务", task_id=task_id)
                    # 注意：实际中断推理需要引擎支持，这里只是标记
                
                self._stats["cancelled_tasks"] += 1
                
                logger.info(LogCategory.INFERENCE, "任务已取消", task_id=task_id)
                
                # 发送取消信号
                self.task_cancelled.emit(task_id)
                self._emit_queue_changed()
                
                return True
                
        except Exception as e:
            logger.exception(LogCategory.INFERENCE, "取消任务失败", 
                           task_id=task_id, error=str(e))
            return False
    
    def cancel_all_tasks(self) -> int:
        """
        取消所有待处理和运行中的任务
        
        Returns:
            取消的任务数量
        """
        cancelled_count = 0
        
        with self._task_lock:
            for task_id, task in self._tasks.items():
                if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    task.status = TaskStatus.CANCELLED
                    self._cancelled_tasks.add(task_id)
                    cancelled_count += 1
                    self.task_cancelled.emit(task_id)
            
            # 清空队列
            while not self._task_queue.empty():
                try:
                    self._task_queue.get_nowait()
                except queue.Empty:
                    break
        
        self._stats["cancelled_tasks"] += cancelled_count
        self._emit_queue_changed()
        
        logger.info(LogCategory.INFERENCE, "已取消所有任务", count=cancelled_count)
        
        return cancelled_count
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态字典，任务不存在返回None
        """
        with self._task_lock:
            if task_id not in self._tasks:
                return None
            return self._tasks[task_id].to_dict()
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有任务状态
        
        Returns:
            任务状态列表
        """
        with self._task_lock:
            return [task.to_dict() for task in self._tasks.values()]
    
    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取待处理任务列表"""
        with self._task_lock:
            return [
                task.to_dict() 
                for task in self._tasks.values() 
                if task.status == TaskStatus.PENDING
            ]
    
    def get_running_task(self) -> Optional[Dict[str, Any]]:
        """获取当前运行任务"""
        with self._task_lock:
            if self._current_task:
                return self._current_task.to_dict()
            return None
    
    def pause(self):
        """暂停处理新任务"""
        self._paused = True
        self.worker_status_changed.emit("paused")
        logger.info(LogCategory.INFERENCE, "工作线程已暂停")
    
    def resume(self):
        """恢复处理任务"""
        self._paused = False
        self.worker_status_changed.emit("running")
        
        # 唤醒工作线程
        self._mutex.lock()
        self._wait_condition.wakeOne()
        self._mutex.unlock()
        
        logger.info(LogCategory.INFERENCE, "工作线程已恢复")
    
    def is_paused(self) -> bool:
        """检查是否暂停"""
        return self._paused
    
    def stop(self):
        """停止工作线程"""
        self._running = False
        
        # 取消所有任务
        self.cancel_all_tasks()
        
        # 唤醒工作线程以便退出
        self._mutex.lock()
        self._wait_condition.wakeAll()
        self._mutex.unlock()
        
        logger.info(LogCategory.INFERENCE, "工作线程停止中...")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        with self._task_lock:
            pending_count = sum(
                1 for t in self._tasks.values() 
                if t.status == TaskStatus.PENDING
            )
            running_count = 1 if self._current_task else 0
            
            return {
                **self._stats,
                "pending_count": pending_count,
                "running_count": running_count,
                "total_in_queue": self._task_queue.qsize(),
                "is_running": self._running,
                "is_paused": self._paused
            }
    
    def clear_completed_tasks(self) -> int:
        """
        清理已完成的任务
        
        Returns:
            清理的任务数量
        """
        with self._task_lock:
            completed_statuses = {
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
                TaskStatus.FAILED,
                TaskStatus.TIMEOUT
            }
            
            to_remove = [
                task_id 
                for task_id, task in self._tasks.items() 
                if task.status in completed_statuses
            ]
            
            for task_id in to_remove:
                del self._tasks[task_id]
            
            logger.info(LogCategory.INFERENCE, "已清理完成任务", count=len(to_remove))
            return len(to_remove)
    
    def _emit_queue_changed(self):
        """发送队列变化信号"""
        with self._task_lock:
            pending_count = sum(
                1 for t in self._tasks.values() 
                if t.status == TaskStatus.PENDING
            )
            running_count = 1 if self._current_task else 0
            self.queue_changed.emit(pending_count, running_count)
    
    def _update_task_progress(self, task_id: str, progress: int):
        """更新任务进度"""
        with self._task_lock:
            if task_id in self._tasks:
                self._tasks[task_id].progress_percent = progress
        
        self.progress_updated.emit(task_id, progress)
    
    def _process_task(self, task: InferenceTask) -> Dict[str, Any]:
        """
        处理单个推理任务
        
        Args:
            task: 推理任务
            
        Returns:
            推理结果
        """
        start_time = time.time()
        
        try:
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = start_time
            self._current_task = task
            
            logger.info(LogCategory.INFERENCE, "开始处理任务",
                       task_id=task.task_id,
                       timeout=task.timeout_seconds)
            
            self.task_started.emit(task.task_id)
            self._emit_queue_changed()
            
            # 检查是否已取消
            if task.task_id in self._cancelled_tasks:
                raise InterruptedError("任务已被取消")
            
            # 更新进度
            self._update_task_progress(task.task_id, 10)
            
            # 执行推理
            if not self._local_engine or not self._local_engine.is_available():
                raise RuntimeError("本地推理引擎不可用")
            
            self._update_task_progress(task.task_id, 30)
            
            # 准备推理参数
            prompt = task.task_context.get("prompt", "")
            generation_params = task.task_context.get("generation_params", {})
            use_cache = task.task_context.get("use_cache", True)
            
            # 执行推理（带超时检查）
            result = self._execute_with_timeout(
                task,
                lambda: self._local_engine.process_image(
                    image_base64=task.image_data,
                    prompt=prompt,
                    use_cache=use_cache,
                    generation_params=generation_params if generation_params else None
                )
            )
            
            self._update_task_progress(task.task_id, 100)
            
            # 更新任务状态
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result
            
            inference_time_ms = (task.completed_at - task.started_at) * 1000
            self._stats["completed_tasks"] += 1
            self._stats["total_inference_time_ms"] += inference_time_ms
            
            logger.info(LogCategory.INFERENCE, "任务处理完成",
                       task_id=task.task_id,
                       inference_time_ms=inference_time_ms)
            
            return result
            
        except TimeoutError as e:
            task.status = TaskStatus.TIMEOUT
            task.error_message = str(e)
            task.completed_at = time.time()
            self._stats["timeout_tasks"] += 1
            
            logger.error(LogCategory.INFERENCE, "任务超时",
                        task_id=task.task_id,
                        timeout=task.timeout_seconds)
            
            raise
            
        except InterruptedError as e:
            task.status = TaskStatus.CANCELLED
            task.error_message = str(e)
            task.completed_at = time.time()
            
            logger.info(LogCategory.INFERENCE, "任务被取消",
                       task_id=task.task_id)
            
            raise
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = time.time()
            self._stats["failed_tasks"] += 1
            
            logger.exception(LogCategory.INFERENCE, "任务处理失败",
                           task_id=task.task_id, error=str(e))
            
            raise
            
        finally:
            self._current_task = None
            self._emit_queue_changed()
    
    def _execute_with_timeout(
        self,
        task: InferenceTask,
        func: Callable
    ) -> Any:
        """
        带超时控制的函数执行
        
        Args:
            task: 当前任务
            func: 要执行的函数
            
        Returns:
            函数返回值
            
        Raises:
            TimeoutError: 任务超时
        """
        # 使用轮询方式检查超时
        # 注意：由于llama-cpp-python可能不支持中断，这里主要是监控
        result = None
        exception = None
        
        def worker():
            nonlocal result, exception
            try:
                result = func()
            except Exception as e:
                exception = e
        
        thread = threading.Thread(target=worker)
        thread.start()
        
        # 等待完成或超时
        start_time = time.time()
        check_interval = 0.1  # 100ms检查间隔
        
        while thread.is_alive():
            # 检查是否被取消
            if task.task_id in self._cancelled_tasks:
                # 无法真正中断线程，但可以标记
                raise InterruptedError("任务已被取消")
            
            # 检查超时
            elapsed = time.time() - start_time
            if elapsed > task.timeout_seconds:
                raise TimeoutError(f"任务执行超时 ({task.timeout_seconds}秒)")
            
            # 更新进度（模拟）
            progress = min(30 + int((elapsed / task.timeout_seconds) * 60), 90)
            self._update_task_progress(task.task_id, progress)
            
            thread.join(timeout=check_interval)
        
        if exception:
            raise exception
        
        return result
    
    def run(self):
        """主循环，处理任务队列"""
        self._running = True
        self.worker_status_changed.emit("running")
        
        logger.info(LogCategory.INFERENCE, "异步推理工作线程启动")
        
        while self._running:
            try:
                # 如果暂停，等待恢复
                if self._paused:
                    self._mutex.lock()
                    self._wait_condition.wait(self._mutex, 100)
                    self._mutex.unlock()
                    continue
                
                # 尝试获取任务
                try:
                    priority, timestamp, task = self._task_queue.get(timeout=0.5)
                except queue.Empty:
                    # 队列为空，等待
                    self._mutex.lock()
                    self._wait_condition.wait(self._mutex, 100)
                    self._mutex.unlock()
                    continue
                
                # 检查任务是否已被取消
                if task.task_id in self._cancelled_tasks:
                    logger.debug(LogCategory.INFERENCE, "跳过已取消的任务", 
                               task_id=task.task_id)
                    continue
                
                # 处理任务
                try:
                    result = self._process_task(task)
                    
                    # 发送结果
                    if task.status == TaskStatus.COMPLETED:
                        self.result_ready.emit(task.task_id, result)
                    
                except (TimeoutError, InterruptedError):
                    # 超时或取消，已处理
                    pass
                except Exception as e:
                    # 其他错误
                    self.error_occurred.emit(task.task_id, str(e))
                
            except Exception as e:
                logger.exception(LogCategory.INFERENCE, "工作线程异常", error=str(e))
                time.sleep(0.1)  # 短暂休息避免CPU占用过高
        
        self.worker_status_changed.emit("stopped")
        logger.info(LogCategory.INFERENCE, "异步推理工作线程已停止")


class AsyncInferenceManager(QObject):
    """
    异步推理管理器（主线程接口）
    
    提供线程安全的接口供主线程使用
    """
    
    # 转发信号
    result_ready = pyqtSignal(str, dict)
    error_occurred = pyqtSignal(str, str)
    progress_updated = pyqtSignal(str, int)
    task_started = pyqtSignal(str)
    task_cancelled = pyqtSignal(str)
    queue_changed = pyqtSignal(int, int)
    worker_status_changed = pyqtSignal(str)
    
    def __init__(self, local_engine: Any, parent: Optional[QObject] = None):
        """
        初始化异步推理管理器
        
        Args:
            local_engine: 本地推理引擎
            parent: 父对象
        """
        super().__init__(parent)
        
        self._worker = AsyncInferenceWorker(local_engine, parent=self)
        
        # 连接信号
        self._worker.result_ready.connect(self.result_ready)
        self._worker.error_occurred.connect(self.error_occurred)
        self._worker.progress_updated.connect(self.progress_updated)
        self._worker.task_started.connect(self.task_started)
        self._worker.task_cancelled.connect(self.task_cancelled)
        self._worker.queue_changed.connect(self.queue_changed)
        self._worker.worker_status_changed.connect(self.worker_status_changed)
        
        logger.info(LogCategory.MAIN, "异步推理管理器初始化完成")
    
    def start(self):
        """启动工作线程"""
        if not self._worker.isRunning():
            self._worker.start()
            logger.info(LogCategory.MAIN, "异步推理工作线程已启动")
    
    def stop(self):
        """停止工作线程"""
        self._worker.stop()
        self._worker.wait(5000)  # 等待最多5秒
        logger.info(LogCategory.MAIN, "异步推理工作线程已停止")
    
    def add_task(
        self,
        task_id: str,
        image_data: str,
        task_context: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_seconds: float = 60.0
    ) -> bool:
        """添加任务"""
        return self._worker.add_task(task_id, image_data, task_context, priority, timeout_seconds)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        return self._worker.cancel_task(task_id)
    
    def cancel_all_tasks(self) -> int:
        """取消所有任务"""
        return self._worker.cancel_all_tasks()
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self._worker.get_task_status(task_id)
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有任务"""
        return self._worker.get_all_tasks()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._worker.get_stats()
    
    def pause(self):
        """暂停"""
        self._worker.pause()
    
    def resume(self):
        """恢复"""
        self._worker.resume()
    
    def clear_completed_tasks(self) -> int:
        """清理已完成任务"""
        return self._worker.clear_completed_tasks()


# 便捷函数
def create_async_inference_manager(
    local_engine: Any,
    parent: Optional[QObject] = None
) -> AsyncInferenceManager:
    """创建异步推理管理器"""
    return AsyncInferenceManager(local_engine, parent)


if __name__ == "__main__":
    # 测试异步推理工作线程
    print("=" * 60)
    print("异步推理工作线程测试")
    print("=" * 60)
    
    # 测试任务数据类
    print("\n1. 测试任务数据类:")
    task = InferenceTask(
        task_id="test_001",
        image_data="base64_data",
        task_context={"prompt": "测试"},
        priority=TaskPriority.HIGH
    )
    print(f"  任务ID: {task.task_id}")
    print(f"  优先级: {task.priority.name}")
    print(f"  状态: {task.status.name}")
    print(f"  字典: {task.to_dict()}")
    
    # 测试优先级队列
    print("\n2. 测试优先级队列:")
    q = queue.PriorityQueue()
    q.put((TaskPriority.LOW.value, time.time(), "low_task"))
    q.put((TaskPriority.HIGH.value, time.time(), "high_task"))
    q.put((TaskPriority.NORMAL.value, time.time(), "normal_task"))
    
    while not q.empty():
        priority, ts, task_name = q.get()
        print(f"  取出: {task_name} (优先级: {priority})")
    
    print("\n" + "=" * 60)

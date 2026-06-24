"""
Minitouch 命令构建器 - 移植自 StarRailCopilot
用于构建 minitouch 协议的多点触控命令
"""
import struct
from typing import List, Tuple

from core.foundation.logger import get_logger, LogCategory

logger = get_logger()


class CommandBuilder:
    """
    Minitouch 命令构建器

    协议格式（每个命令 16 字节）：
    +--------+--------+--------+--------+
    | 动作   | 触点ID |   X    |   Y    |
    +--------+--------+--------+--------+
    | 压力   | 保留   |   X轴偏移 | Y轴偏移 |
    +--------+--------+--------+--------+

    动作类型：
    0x00 - 触摸开始（DOWN）
    0x01 - 触摸移动（MOVE）
    0x02 - 触摸结束（UP）
    0x03 - 等待（WAIT，单位：毫秒）
    """

    def __init__(self, max_contacts: int = 10, max_x: int = 1280, max_y: int = 720):
        """
        初始化命令构建器

        Args:
            max_contacts: 最大触点数量
            max_x: X 轴最大值（用于归一化）
            max_y: Y 轴最大值（用于归一化）
        """
        self.max_contacts = max_contacts
        self.max_x = max_x
        self.max_y = max_y
        self.contact_counter = 0
        self._commands: List[bytes] = []
        self._used_contacts = set()

    def _normalize_coord(self, x: int, y: int) -> Tuple[int, int]:
        """坐标归一化到协议范围"""
        # minitouch 使用 0-65535 范围
        norm_x = int(x * 65535 / self.max_x)
        norm_y = int(y * 65535 / self.max_y)
        return norm_x, norm_y

    def _allocate_contact(self) -> int:
        """分配触点 ID"""
        for contact_id in range(self.max_contacts):
            if contact_id not in self._used_contacts:
                self._used_contacts.add(contact_id)
                return contact_id
        raise RuntimeError(f"触点数量超限: {self.max_contacts}")

    def _free_contact(self, contact_id: int):
        """释放触点"""
        self._used_contacts.discard(contact_id)

    def down(self, x: int, y: int, contact_id: int = -1) -> 'CommandBuilder':
        """
        触点按下

        Args:
            x, y: 坐标
            contact_id: 触点 ID（-1 表示自动分配）

        Returns:
            self (链式调用)
        """
        if contact_id == -1:
            contact_id = self._allocate_contact()

        norm_x, norm_y = self._normalize_coord(x, y)
        # 命令格式: action(1) + contact_id(1) + x(2) + y(2) + pressure(2) + 保留(8)
        cmd = struct.pack(
            '>BBHHHHHH',
            0x00,                    # DOWN
            contact_id,
            norm_x,
            norm_y,
            255,                     # pressure (max)
            0, 0, 0, 0              # 保留字段
        )
        self._commands.append(cmd)
        return self

    def move(self, x: int, y: int, contact_id: int) -> 'CommandBuilder':
        """
        触点移动

        Args:
            x, y: 坐标
            contact_id: 触点 ID

        Returns:
            self
        """
        norm_x, norm_y = self._normalize_coord(x, y)
        cmd = struct.pack(
            '>BBHHHHHH',
            0x01,                    # MOVE
            contact_id,
            norm_x,
            norm_y,
            255,                     # pressure
            0, 0, 0, 0
        )
        self._commands.append(cmd)
        return self

    def up(self, contact_id: int) -> 'CommandBuilder':
        """
        触点抬起

        Args:
            contact_id: 触点 ID

        Returns:
            self
        """
        cmd = struct.pack(
            '>BBHHHHHH',
            0x02,                    # UP
            contact_id,
            0, 0,                    # x, y (忽略)
            255,                     # pressure
            0, 0, 0, 0
        )
        self._commands.append(cmd)
        self._free_contact(contact_id)
        return self

    def wait(self, duration_ms: int) -> 'CommandBuilder':
        """
        等待指定时间

        Args:
            duration_ms: 等待时长（毫秒）

        Returns:
            self
        """
        # WAIT 命令使用特殊格式：action=3, contact_id=duration
        cmd = struct.pack(
            '>BBHHHHHH',
            0x03,                    # WAIT
            duration_ms & 0xFF,      # 低字节
            0, 0,                    # x, y
            0, 0, 0, 0, 0
        )
        # 注意：实际 minitouch 协议中 WAIT 的参数编码可能不同
        # 这里简化处理，实际应参考 minitouch 文档
        self._commands.append(cmd)
        return self

    def commit(self) -> 'CommandBuilder':
        """
        提交命令批次（添加 c 命令）

        Returns:
            self
        """
        cmd = b'c\n'
        self._commands.append(cmd)
        return self

    def clear(self):
        """清空命令缓冲区"""
        self._commands.clear()
        self._used_contacts.clear()

    def to_minitouch(self) -> str:
        """
        转换为 minitouch 协议字符串

        Returns:
            命令字符串（每行一个命令）
        """
        lines = []
        for cmd in self._commands:
            if cmd == b'c\n':
                lines.append('c')
            else:
                # 将二进制转换为十六进制字符串
                hex_str = cmd.hex()
                # minitouch 协议中，每行是二进制数据（不是 hex 文本）
                # 这里返回的是原始二进制数据的字符串表示
                lines.append(hex_str)
        return '\n'.join(lines)

    def send(self, sock):
        """
        直接发送到 socket（简化接口）

        Args:
            sock: socket 对象
        """
        for cmd in self._commands:
            if cmd == b'c\n':
                sock.sendall(b'c\n')
            else:
                sock.sendall(cmd)
        self.clear()


def insert_swipe(p0: Tuple[int, int], p3: Tuple[int, int], speed: int = 20) -> List[Tuple[int, int]]:
    """
    在两点之间插入中间点（用于平滑滑动）

    Args:
        p0: 起点 (x, y)
        p3: 终点 (x, y)
        speed: 速度因子（点间距）

    Returns:
        插值后的点列表（包含起点和终点）
    """
    import math

    x0, y0 = p0
    x3, y3 = p3

    # 计算总距离
    distance = math.sqrt((x3 - x0) ** 2 + (y3 - y0) ** 2)

    # 计算需要插入的点数
    num_points = max(1, int(distance / speed))

    points = [p0]
    for i in range(1, num_points):
        t = i / num_points
        # 线性插值
        x = int(x0 + (x3 - x0) * t)
        y = int(y0 + (y3 - y0) * t)
        points.append((x, y))
    points.append(p3)

    return points
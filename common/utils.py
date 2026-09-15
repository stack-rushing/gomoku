from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Any, Optional


def current_timestamp() -> float:
    """返回当前 Unix 时间戳（秒）"""
    return time.time()


def current_datetime_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """返回格式化的当前日期时间字符串"""
    return datetime.now().strftime(fmt)


def format_timestamp(ts: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """将 Unix 时间戳格式化为日期时间字符串"""
    return datetime.fromtimestamp(ts).strftime(fmt)


def format_duration(seconds: float) -> str:
    """将秒数格式化为可读的时长字符串"""
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分钟")
    parts.append(f"{secs}秒")

    return "".join(parts)


def generate_room_id(length: int = 6) -> str:
    """生成随机数字房间号"""
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def is_valid_room_id(room_id: Any, min_len: int = 1, max_len: int = 32) -> bool:
    """验证房间号是否合法"""
    if not isinstance(room_id, str):
        return False
    if len(room_id) < min_len or len(room_id) > max_len:
        return False
    return all(c.isalnum() or c in "_-" for c in room_id)


def is_valid_player_name(name: Any, min_len: int = 1, max_len: int = 20) -> bool:
    """验证玩家名称是否合法"""
    if not isinstance(name, str):
        return False
    if len(name) < min_len or len(name) > max_len:
        return False
    return True


def is_valid_coordinate(row: Any, col: Any, board_size: int) -> bool:
    """验证坐标是否在棋盘范围内"""
    if not isinstance(row, int) or not isinstance(col, int):
        return False
    return 0 <= row < board_size and 0 <= col < board_size


def clamp(value: float, min_val: float, max_val: float) -> float:
    """限制数值在指定范围内"""
    return max(min_val, min(max_val, value))


def safe_int(value: Any, default: int = 0) -> int:
    """安全转换为 int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """安全转换为 str"""
    try:
        return str(value) if value is not None else default
    except Exception:
        return default

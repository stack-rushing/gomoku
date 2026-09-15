from __future__ import annotations

import json
from typing import Any, List, Optional, Tuple


def encode_message(message: dict) -> bytes:
    """将消息字典编码为 JSON + 换行符 的字节串"""
    return (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")


def decode_message(data: str) -> Optional[dict]:
    """将字符串解码为消息字典，失败返回 None"""
    try:
        return json.loads(data.strip())
    except (json.JSONDecodeError, ValueError):
        return None


class MessageBuffer:
    """TCP 粘包/拆包处理的接收缓冲区"""

    def __init__(self) -> None:
        self._buffer = b""

    def feed(self, data: bytes) -> None:
        """将收到的字节数据追加到缓冲区"""
        self._buffer += data

    def extract_messages(self) -> Tuple[List[dict], List[str]]:
        """
        从缓冲区提取完整消息。
        返回 (解析成功的消息列表, 解析失败的原始行列表)
        """
        if b"\n" not in self._buffer:
            return [], []

        lines = self._buffer.split(b"\n")
        self._buffer = lines[-1]

        messages: List[dict] = []
        failed_lines: List[str] = []

        for raw_line in lines[:-1]:
            if not raw_line.strip():
                continue
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                failed_lines.append(raw_line.decode("utf-8", errors="replace"))
                continue
            msg = decode_message(line)
            if msg is not None:
                messages.append(msg)
            else:
                failed_lines.append(line)

        return messages, failed_lines

    def clear(self) -> None:
        self._buffer = b""

    @property
    def is_empty(self) -> bool:
        return len(self._buffer) == 0


def build_join_room(room_id: str, player_name: str) -> dict:
    return {"type": "join_room", "room_id": room_id, "player_name": player_name}


def build_room_joined(room_id: str, player: str) -> dict:
    return {"type": "room_joined", "room_id": room_id, "player": player}


def build_room_full() -> dict:
    return {"type": "room_full"}


def build_game_start(black: str, white: str, current_player: str) -> dict:
    return {
        "type": "game_start",
        "black": black,
        "white": white,
        "current_player": current_player,
    }


def build_move(row: int, col: int) -> dict:
    return {"type": "move", "row": row, "col": col}


def build_move_result(row: int, col: int, player: str, next_player: str) -> dict:
    return {
        "type": "move_result",
        "row": row,
        "col": col,
        "player": player,
        "next_player": next_player,
    }


def build_invalid_move(reason: str) -> dict:
    return {"type": "invalid_move", "reason": reason}


def build_game_over(winner: str) -> dict:
    return {"type": "game_over", "winner": winner}


def build_draw() -> dict:
    return {"type": "draw"}


def build_restart_request() -> dict:
    return {"type": "restart_request"}


def build_restart_response(agreed: bool) -> dict:
    return {"type": "restart_response", "agreed": agreed}


def build_game_restart() -> dict:
    return {"type": "game_restart"}


def build_player_left() -> dict:
    return {"type": "player_left"}


def build_error(message: str, code: Optional[str] = None) -> dict:
    msg = {"type": "error", "message": message}
    if code is not None:
        msg["code"] = code
    return msg


def build_ping() -> dict:
    return {"type": "ping"}


def build_pong() -> dict:
    return {"type": "pong"}


def validate_message(msg: Any) -> bool:
    if not isinstance(msg, dict):
        return False
    return "type" in msg and isinstance(msg["type"], str)

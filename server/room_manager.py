from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from common.constants import (
    BLACK,
    MAX_PLAYERS_PER_ROOM,
    PLAYER_BLACK,
    PLAYER_WHITE,
    WHITE,
)
from server.config import BOARD_SIZE, EMPTY_ROOM_TTL
from server.game import GomokuGame
from server.logger import logger


@dataclass
class PlayerSession:
    session_id: str
    player_name: str
    side: int
    conn: Any
    addr: Tuple[str, int]
    last_ping: float = field(default_factory=time.time)
    restart_voted: bool = False
    connected: bool = True


@dataclass
class Room:
    room_id: str
    game: GomokuGame
    players: Dict[str, PlayerSession] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    game_started: bool = False
    game_started_at: Optional[float] = None
    game_ended: bool = False
    game_ended_at: Optional[float] = None
    result: Optional[str] = None
    game_id: Optional[int] = None
    restart_votes: int = 0

    def is_full(self) -> bool:
        return len(self.players) >= MAX_PLAYERS_PER_ROOM

    def is_empty(self) -> bool:
        return len(self.players) == 0

    def get_black_player(self) -> Optional[PlayerSession]:
        for p in self.players.values():
            if p.side == BLACK:
                return p
        return None

    def get_white_player(self) -> Optional[PlayerSession]:
        for p in self.players.values():
            if p.side == WHITE:
                return p
        return None

    def get_side(self, session_id: str) -> Optional[int]:
        p = self.players.get(session_id)
        return p.side if p else None

    def get_other_session(self, session_id: str) -> Optional[PlayerSession]:
        if session_id not in self.players:
            return None
        for sid, p in self.players.items():
            if sid != session_id:
                return p
        return None

    def is_in_room(self, session_id: str) -> bool:
        return session_id in self.players


class RoomManager:
    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}
        self._lock = threading.RLock()
        self._next_session_id = 0

    def _gen_session_id(self) -> str:
        self._next_session_id += 1
        return f"sess_{int(time.time()*1000)}_{self._next_session_id}"

    def create_room(self, room_id: str) -> Room:
        with self._lock:
            game = GomokuGame(board_size=BOARD_SIZE)
            room = Room(room_id=room_id, game=game)
            self._rooms[room_id] = room
            logger.info(f"[Room] 创建房间: {room_id}")
            return room

    def get_room(self, room_id: str) -> Optional[Room]:
        with self._lock:
            return self._rooms.get(room_id)

    def get_or_create_room(self, room_id: str) -> Room:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                room = self.create_room(room_id)
            return room

    def remove_room(self, room_id: str) -> None:
        with self._lock:
            if room_id in self._rooms:
                del self._rooms[room_id]
                logger.info(f"[Room] 删除房间: {room_id}")

    def list_rooms(self) -> List[Room]:
        with self._lock:
            return list(self._rooms.values())

    def get_room_count(self) -> int:
        with self._lock:
            return len(self._rooms)

    def get_active_game_count(self) -> int:
        with self._lock:
            return sum(1 for r in self._rooms.values() if r.game_started and not r.game_ended)

    def get_total_players(self) -> int:
        with self._lock:
            return sum(len(r.players) for r in self._rooms.values())

    def join_room(
        self,
        room_id: str,
        player_name: str,
        conn: Any,
        addr: Tuple[str, int],
    ) -> Tuple[Optional[PlayerSession], Optional[Room], bool]:
        with self._lock:
            room = self.get_or_create_room(room_id)

            if room.is_full():
                logger.warning(f"[Room] 房间已满: {room_id}, 玩家: {player_name}")
                return None, room, False

            session_id = self._gen_session_id()

            if len(room.players) == 0:
                side = BLACK
            else:
                side = WHITE

            player = PlayerSession(
                session_id=session_id,
                player_name=player_name,
                side=side,
                conn=conn,
                addr=addr,
            )
            room.players[session_id] = player

            side_str = PLAYER_BLACK if side == BLACK else PLAYER_WHITE
            logger.info(
                f"[Room] 玩家加入: room={room_id}, name={player_name}, "
                f"side={side_str}, total={len(room.players)}"
            )

            if room.is_full() and not room.game_started:
                room.game_started = True
                room.game_started_at = time.time()
                room.game_id = None
                room.game_ended = False
                room.game_ended_at = None
                room.result = None
                logger.info(f"[Room] 游戏开始: room={room_id}")
                return player, room, True

            return player, room, False

    def leave_room(self, room_id: str, session_id: str) -> Optional[Room]:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return None

            if session_id in room.players:
                player = room.players[session_id]
                logger.info(
                    f"[Room] 玩家离开: room={room_id}, name={player.player_name}"
                )
                del room.players[session_id]

            if room.is_empty():
                if time.time() - room.created_at > EMPTY_ROOM_TTL:
                    self.remove_room(room_id)
            return room

    def broadcast(self, room_id: str, message: dict, exclude_session_id: Optional[str] = None) -> None:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return
            self._broadcast_to_room(room, message, exclude_session_id)

    def _broadcast_to_room(
        self,
        room: Room,
        message: dict,
        exclude_session_id: Optional[str] = None,
    ) -> None:
        from common.protocol import encode_message
        from server.tcp_server import SafeConnection

        data = encode_message(message)
        for sid, player in room.players.items():
            if sid == exclude_session_id or not player.connected:
                continue
            try:
                SafeConnection.send_safe(player.conn, data)
            except Exception as e:
                logger.error(f"[Broadcast] 发送失败 sid={sid}: {e}")
                player.connected = False

    def send_to_player(self, room_id: str, session_id: str, message: dict) -> bool:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return False
            player = room.players.get(session_id)
            if player is None or not player.connected:
                return False

            from common.protocol import encode_message
            from server.tcp_server import SafeConnection

            try:
                SafeConnection.send_safe(player.conn, encode_message(message))
                return True
            except Exception as e:
                logger.error(f"[Send] 发送失败 sid={session_id}: {e}")
                player.connected = False
                return False

    def find_player_room(self, session_id: str) -> Optional[Room]:
        with self._lock:
            for room in self._rooms.values():
                if session_id in room.players:
                    return room
            return None

    def set_player_ping(self, session_id: str) -> None:
        with self._lock:
            for room in self._rooms.values():
                player = room.players.get(session_id)
                if player:
                    player.last_ping = time.time()
                    break

    def reset_restart_votes(self, room_id: str) -> None:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return
            room.restart_votes = 0
            for p in room.players.values():
                p.restart_voted = False

    def vote_restart(self, room_id: str, session_id: str) -> Tuple[int, int]:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return 0, 0
            player = room.players.get(session_id)
            if player is None or player.restart_voted:
                return room.restart_votes, len(room.players)

            player.restart_voted = True
            room.restart_votes += 1
            logger.info(
                f"[Room] 重开投票: room={room_id}, {room.restart_votes}/{len(room.players)}"
            )
            return room.restart_votes, len(room.players)

    def do_restart(self, room_id: str) -> Optional[Room]:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return None
            room.game.restart()
            room.game_ended = False
            room.game_ended_at = None
            room.result = None
            room.game_id = None
            room.game_started_at = time.time()
            room.restart_votes = 0
            for p in room.players.values():
                p.restart_voted = False
            logger.info(f"[Room] 游戏重新开始: room={room_id}")
            return room

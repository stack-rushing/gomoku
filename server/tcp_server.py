from __future__ import annotations

import socket
import threading
import time
from typing import Dict, Optional, Tuple

from common.constants import (
    BLACK,
    ERR_DUPLICATE_MOVE,
    ERR_GAME_ENDED,
    ERR_INVALID_COORDINATE,
    ERR_NOT_YOUR_TURN,
    PLAYER_BLACK,
    PLAYER_WHITE,
    RESULT_DRAW,
    RESULT_ONGOING,
    RESULT_WIN_BLACK,
    RESULT_WIN_WHITE,
)
from common.protocol import (
    MessageBuffer,
    build_draw,
    build_error,
    build_game_over,
    build_game_restart,
    build_game_start,
    build_invalid_move,
    build_move_result,
    build_pong,
    build_room_full,
    build_room_joined,
    build_player_left,
    build_restart_response,
    encode_message,
    validate_message,
)
from common.utils import is_valid_coordinate, is_valid_player_name, is_valid_room_id
from server.config import PING_INTERVAL, PING_TIMEOUT, SERVER_HOST, SERVER_PORT, BOARD_SIZE
from server.database import Database
from server.logger import logger
from server.room_manager import Room, RoomManager


class SafeConnection:
    _write_lock = threading.Lock()

    @classmethod
    def send_safe(cls, conn: socket.socket, data: bytes) -> None:
        try:
            with cls._write_lock:
                conn.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            raise


class ClientHandler:
    def __init__(
        self,
        server: "TCPServer",
        conn: socket.socket,
        addr: Tuple[str, int],
    ) -> None:
        self.server = server
        self.conn = conn
        self.addr = addr
        self.session_id: Optional[str] = None
        self.room_id: Optional[str] = None
        self.side: Optional[int] = None
        self.player_name: str = ""
        self.running = True
        self.buffer = MessageBuffer()
        self.last_recv = time.time()
        self._lock = threading.Lock()

    def send(self, message: dict) -> None:
        with self._lock:
            if not self.running:
                return
            try:
                SafeConnection.send_safe(self.conn, encode_message(message))
            except Exception as e:
                logger.warning(f"[TCP] 发送失败 {self.addr}: {e}")
                self.stop()

    def stop(self) -> None:
        with self._lock:
            if not self.running:
                return
            self.running = False
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass
        self._on_disconnect()

    def run(self) -> None:
        logger.info(f"[TCP] 客户端连接: {self.addr}")
        try:
            self.conn.settimeout(None)
            while self.running:
                try:
                    self.conn.settimeout(30)
                    data = self.conn.recv(8192)
                except socket.timeout:
                    if time.time() - self.last_recv > PING_TIMEOUT:
                        logger.warning(f"[TCP] 心跳超时: {self.addr}")
                        break
                    continue
                except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
                    logger.warning(f"[TCP] 连接异常 {self.addr}: {e}")
                    break

                if not data:
                    break

                self.last_recv = time.time()
                self.buffer.feed(data)
                messages, _ = self.buffer.extract_messages()
                for msg in messages:
                    self._handle_message(msg)
        except Exception as e:
            logger.exception(f"[TCP] 客户端处理异常 {self.addr}: {e}")
        finally:
            self.stop()
            logger.info(f"[TCP] 客户端断开: {self.addr}")

    def _handle_message(self, msg: dict) -> None:
        if not validate_message(msg):
            self.send(build_error("Invalid message format", "INVALID_FORMAT"))
            return

        msg_type = msg.get("type")

        if msg_type == "ping":
            self.send(build_pong())
            if self.session_id:
                self.server.room_manager.set_player_ping(self.session_id)
            return

        if msg_type == "pong":
            if self.session_id:
                self.server.room_manager.set_player_ping(self.session_id)
            return

        if msg_type == "join_room":
            self._handle_join_room(msg)
            return

        if self.session_id is None or self.room_id is None:
            self.send(build_error("Not joined a room", "NOT_IN_ROOM"))
            return

        if msg_type == "move":
            self._handle_move(msg)
        elif msg_type == "restart_request":
            self._handle_restart_request()
        else:
            self.send(build_error(f"Unknown message type: {msg_type}", "UNKNOWN_TYPE"))

    def _handle_join_room(self, msg: dict) -> None:
        room_id = msg.get("room_id", "")
        player_name = msg.get("player_name", "")

        if not is_valid_room_id(room_id):
            self.send(build_error("Invalid room_id", "INVALID_ROOM_ID"))
            return
        if not is_valid_player_name(player_name):
            self.send(build_error("Invalid player_name", "INVALID_PLAYER_NAME"))
            return

        rm = self.server.room_manager
        db = self.server.database

        player, room, game_started = rm.join_room(
            room_id, player_name, self.conn, self.addr
        )

        if player is None:
            self.send(build_room_full())
            return

        self.session_id = player.session_id
        self.room_id = room_id
        self.side = player.side
        self.player_name = player_name

        side_str = PLAYER_BLACK if player.side == BLACK else PLAYER_WHITE
        self.send(build_room_joined(room_id, side_str))
        self.server.register_session(player.session_id, self)

        if game_started:
            black = room.get_black_player()
            white = room.get_white_player()
            if black and white:
                game_id = db.create_game(
                    room_id, black.player_name, white.player_name, room.game_started_at
                )
                room.game_id = game_id
                start_msg = build_game_start(
                    black.player_name, white.player_name, PLAYER_BLACK
                )
                rm.broadcast(room_id, start_msg)

    def _handle_move(self, msg: dict) -> None:
        if self.session_id is None or self.room_id is None:
            return
        rm = self.server.room_manager
        room = rm.get_room(self.room_id)
        if room is None:
            self.send(build_error("Room not found", "ROOM_NOT_FOUND"))
            return

        try:
            row = int(msg.get("row", -1))
            col = int(msg.get("col", -1))
        except (ValueError, TypeError):
            self.send(build_invalid_move("Invalid coordinates"))
            return

        if not is_valid_coordinate(row, col, BOARD_SIZE):
            self.send(build_invalid_move(ERR_INVALID_COORDINATE))
            logger.warning(
                f"[Game] 非法坐标: room={self.room_id}, player={self.player_name}, "
                f"row={row}, col={col}"
            )
            return

        if not room.game_started:
            self.send(build_invalid_move("Game not started"))
            return

        if room.game_ended:
            self.send(build_invalid_move(ERR_GAME_ENDED))
            return

        if self.side != room.game.current_player:
            self.send(build_invalid_move(ERR_NOT_YOUR_TURN))
            logger.warning(
                f"[Game] 非自己回合: room={self.room_id}, player={self.player_name}"
            )
            return

        if not room.game.is_cell_empty(row, col):
            self.send(build_invalid_move(ERR_DUPLICATE_MOVE))
            logger.warning(
                f"[Game] 重复落子: room={self.room_id}, player={self.player_name}, "
                f"row={row}, col={col}"
            )
            return

        success = room.game.place(self.side, row, col)
        if not success:
            self.send(build_invalid_move("Move failed"))
            return

        logger.info(
            f"[Game] 落子: room={self.room_id}, player={self.player_name}, "
            f"side={PLAYER_BLACK if self.side == 1 else PLAYER_WHITE}, row={row}, col={col}"
        )

        next_player_str = room.game.get_current_player_str()
        current_side_str = PLAYER_BLACK if self.side == 1 else PLAYER_WHITE
        move_result = build_move_result(row, col, current_side_str, next_player_str)
        rm.broadcast(self.room_id, move_result)

        result = room.game.get_result()
        if result != RESULT_ONGOING:
            room.game_ended = True
            room.game_ended_at = time.time()
            room.result = result

            if result == RESULT_WIN_BLACK or result == RESULT_WIN_WHITE:
                winner_str = room.game.get_winner_str()
                logger.info(
                    f"[Game] 胜利: room={self.room_id}, winner={winner_str}"
                )
                rm.broadcast(self.room_id, build_game_over(winner_str))
            elif result == RESULT_DRAW:
                logger.info(f"[Game] 和棋: room={self.room_id}")
                rm.broadcast(self.room_id, build_draw())

            if room.game_id:
                self.server.database.end_game(
                    room.game_id,
                    result,
                    room.game.get_winner_str(),
                    room.game.move_history,
                    room.game_ended_at,
                )

    def _handle_restart_request(self) -> None:
        if self.session_id is None or self.room_id is None:
            return
        rm = self.server.room_manager
        room = rm.get_room(self.room_id)
        if room is None:
            return

        self.send(build_restart_response(True))

        votes, total = rm.vote_restart(self.room_id, self.session_id)
        if total > 0 and votes >= total:
            rm.do_restart(self.room_id)
            rm.broadcast(self.room_id, build_game_restart())
            room = rm.get_room(self.room_id)
            if room and room.game_started:
                black = room.get_black_player()
                white = room.get_white_player()
                if black and white:
                    game_id = self.server.database.create_game(
                        self.room_id,
                        black.player_name,
                        white.player_name,
                        room.game_started_at,
                    )
                    room.game_id = game_id
                    start_msg = build_game_start(
                        black.player_name, white.player_name, PLAYER_BLACK
                    )
                    rm.broadcast(self.room_id, start_msg)

    def _on_disconnect(self) -> None:
        if self.session_id:
            self.server.unregister_session(self.session_id)
        if self.room_id and self.session_id:
            rm = self.server.room_manager
            room = rm.leave_room(self.room_id, self.session_id)
            if room and not room.game_ended and not room.is_empty():
                rm.broadcast(self.room_id, build_player_left())
                if room.game_id and room.game.get_result() == RESULT_ONGOING:
                    winner_str = PLAYER_WHITE if self.side == 1 else PLAYER_BLACK
                    result = RESULT_WIN_WHITE if self.side == 1 else RESULT_WIN_BLACK
                    room.game_ended = True
                    room.game_ended_at = time.time()
                    room.result = result
                    self.server.database.end_game(
                        room.game_id,
                        result,
                        winner_str,
                        room.game.move_history,
                        room.game_ended_at,
                    )


class TCPServer:
    def __init__(
        self,
        room_manager: RoomManager,
        database: Database,
        host: str = SERVER_HOST,
        port: int = SERVER_PORT,
    ) -> None:
        self.room_manager = room_manager
        self.database = database
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.running = False
        self._sessions: Dict[str, ClientHandler] = {}
        self._sessions_lock = threading.Lock()
        self._started_at: Optional[float] = None

    def register_session(self, session_id: str, handler: ClientHandler) -> None:
        with self._sessions_lock:
            self._sessions[session_id] = handler

    def unregister_session(self, session_id: str) -> None:
        with self._sessions_lock:
            self._sessions.pop(session_id, None)

    def get_session_count(self) -> int:
        with self._sessions_lock:
            return len(self._sessions)

    def get_uptime(self) -> float:
        if self._started_at is None:
            return 0
        return time.time() - self._started_at

    def start(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(128)
        self.running = True
        self._started_at = time.time()
        logger.info(f"[TCP] 服务器启动: {self.host}:{self.port}")

        threading.Thread(target=self._accept_loop, daemon=True).start()

    def stop(self) -> None:
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def _accept_loop(self) -> None:
        assert self.sock is not None
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except OSError:
                break
            handler = ClientHandler(self, conn, addr)
            threading.Thread(target=handler.run, daemon=True).start()

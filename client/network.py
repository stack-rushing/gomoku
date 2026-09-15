from __future__ import annotations

import queue
import socket
import threading
import time
from typing import Optional

from common.constants import (
    MSG_ERROR,
    MSG_GAME_OVER,
    MSG_GAME_RESTART,
    MSG_GAME_START,
    MSG_JOIN_ROOM,
    MSG_MOVE,
    MSG_MOVE_RESULT,
    MSG_PING,
    MSG_PONG,
    MSG_PLAYER_LEFT,
    MSG_RESTART_REQUEST,
    MSG_ROOM_FULL,
    MSG_ROOM_JOINED,
    MSG_DRAW,
    MSG_INVALID_MOVE,
)
from common.protocol import (
    MessageBuffer,
    build_join_room,
    build_move,
    build_ping,
    build_restart_request,
    encode_message,
    validate_message,
)
from client.config import PING_INTERVAL, RECV_TIMEOUT


EVENT_CONNECTED = "connected"
EVENT_DISCONNECTED = "disconnected"
EVENT_ERROR = "network_error"
EVENT_MESSAGE = "message"


class NetworkClient:
    def __init__(self) -> None:
        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.running = False
        self._lock = threading.Lock()

        self.message_queue: "queue.Queue[dict]" = queue.Queue()
        self.event_queue: "queue.Queue[dict]" = queue.Queue()

        self._recv_thread: Optional[threading.Thread] = None
        self._ping_thread: Optional[threading.Thread] = None
        self._last_send_ping = 0.0
        self._buffer = MessageBuffer()

    def connect(self, host: str, port: int, timeout: float = 5.0) -> bool:
        self.disconnect()
        self._buffer.clear()
        self._drain_queue(self.message_queue)
        self._drain_queue(self.event_queue)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.settimeout(RECV_TIMEOUT)

            with self._lock:
                self.sock = sock
                self.connected = True
                self.running = True

            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()

            self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
            self._ping_thread.start()

            self._emit_event(EVENT_CONNECTED, {"host": host, "port": port})
            return True
        except (socket.error, OSError, TimeoutError) as e:
            self._emit_event(
                EVENT_ERROR,
                {"type": "connect_failed", "message": str(e)},
            )
            return False

    def disconnect(self) -> None:
        was_connected = False
        with self._lock:
            if self.running:
                self.running = False
                was_connected = self.connected
                self.connected = False
            sock = self.sock
            self.sock = None

        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

        if was_connected:
            self._emit_event(EVENT_DISCONNECTED, {})

    def send(self, message: dict) -> bool:
        if not validate_message(message):
            return False
        data = encode_message(message)
        with self._lock:
            sock = self.sock
            if sock is None or not self.running:
                return False
            try:
                sock.sendall(data)
                return True
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                self._emit_event(
                    EVENT_ERROR,
                    {"type": "send_failed", "message": str(e)},
                )
        self.disconnect()
        return False

    def join_room(self, room_id: str, player_name: str) -> bool:
        return self.send(build_join_room(room_id, player_name))

    def send_move(self, row: int, col: int) -> bool:
        return self.send(build_move(row, col))

    def send_restart_request(self) -> bool:
        return self.send(build_restart_request())

    def poll_messages(self) -> list:
        msgs = []
        try:
            while True:
                msgs.append(self.message_queue.get_nowait())
        except queue.Empty:
            pass
        return msgs

    def poll_events(self) -> list:
        events = []
        try:
            while True:
                events.append(self.event_queue.get_nowait())
        except queue.Empty:
            pass
        return events

    def _drain_queue(self, q: "queue.Queue") -> None:
        try:
            while True:
                q.get_nowait()
        except queue.Empty:
            pass

    def _emit_event(self, event_type: str, payload: dict) -> None:
        self.event_queue.put({"type": event_type, "payload": payload or {}})

    def _emit_message(self, msg: dict) -> None:
        self.message_queue.put(msg)

    def _recv_loop(self) -> None:
        while True:
            with self._lock:
                if not self.running or self.sock is None:
                    break
                sock = self.sock

            try:
                sock.settimeout(RECV_TIMEOUT)
                data = sock.recv(8192)
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                break

            if not data:
                break

            self._buffer.feed(data)
            messages, _ = self._buffer.extract_messages()
            for msg in messages:
                self._on_message(msg)

        self.disconnect()

    def _ping_loop(self) -> None:
        while True:
            with self._lock:
                if not self.running or not self.connected:
                    break

            now = time.time()
            if now - self._last_send_ping >= PING_INTERVAL:
                self.send(build_ping())
                self._last_send_ping = now

            time.sleep(1)

    def _on_message(self, msg: dict) -> None:
        msg_type = msg.get("type")

        if msg_type == MSG_PING:
            from common.protocol import build_pong

            self.send(build_pong())
            return

        if msg_type == MSG_PONG:
            return

        self._emit_message(msg)

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from common.protocol import (
    MessageBuffer,
    build_join_room,
    build_move,
    build_restart_request,
    decode_message,
    encode_message,
)
from client.network import NetworkClient
from server.database import Database
from server.logger import logger
from server.room_manager import RoomManager
from server.tcp_server import TCPServer

TEST_HOST = "127.0.0.1"
TEST_PORT = 18888


def _find_free_port(start: int) -> int:
    for p in range(start, start + 100):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            s.close()
            continue
    raise RuntimeError("No free port")


class TestClient:
    def __init__(self) -> None:
        self.sock: socket.socket | None = None
        self.buffer = MessageBuffer()
        self.lock = threading.Lock()
        self._pending: list = []

    def connect(self, host, port, timeout=3.0) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((host, port))
        self.sock.settimeout(2.0)

    def close(self) -> None:
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

    def send(self, msg: dict) -> None:
        self.sock.sendall(encode_message(msg))

    def _recv_once(self, wait: float) -> None:
        start = time.time()
        while time.time() - start < wait:
            try:
                data = self.sock.recv(8192)
            except socket.timeout:
                return
            if not data:
                return
            self.buffer.feed(data)
            msgs, _ = self.buffer.extract_messages()
            if msgs:
                self._pending.extend(msgs)
                return

    def recv_until_type(self, msg_type: str, timeout: float = 4.0) -> dict | None:
        start = time.time()
        while time.time() - start < timeout:
            for i, m in enumerate(self._pending):
                if m.get("type") == msg_type:
                    return self._pending.pop(i)
            self._recv_once(0.25)
        return None


class TestTCPServerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _find_free_port(TEST_PORT)
        cls.rm = RoomManager()
        cls.db = Database()
        cls.server = TCPServer(cls.rm, cls.db, host=TEST_HOST, port=cls.port)
        cls.server.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def test_client_connect_and_join_room(self) -> None:
        c = TestClient()
        c.connect(TEST_HOST, self.port)
        try:
            c.send(build_join_room("room_test1", "A"))
            msg = c.recv_until_type("room_joined", 3)
            self.assertIsNotNone(msg)
            self.assertEqual(msg["room_id"], "room_test1")
            self.assertEqual(msg["player"], "black")
        finally:
            c.close()

    def test_network_client_receives_room_joined(self) -> None:
        client = NetworkClient()
        try:
            self.assertTrue(client.connect(TEST_HOST, self.port))
            self.assertTrue(client.join_room("room_network_client", "NetworkClient"))
            deadline = time.time() + 3
            received = []
            while time.time() < deadline and not received:
                received.extend(client.poll_messages())
                time.sleep(0.02)
            self.assertTrue(
                any(message.get("type") == "room_joined" for message in received),
                f"messages={received}, events={client.poll_events()}, "
                f"received_bytes={client.last_received_bytes}, "
                f"receive_error={client.last_receive_error}",
            )
        finally:
            client.disconnect()

    def test_two_clients_same_room_game_starts(self) -> None:
        c1 = TestClient()
        c2 = TestClient()
        room_id = "room_test2"
        try:
            c1.connect(TEST_HOST, self.port)
            c1.send(build_join_room(room_id, "Alice"))
            self.assertIsNotNone(c1.recv_until_type("room_joined"))

            c2.connect(TEST_HOST, self.port)
            c2.send(build_join_room(room_id, "Bob"))
            msg2 = c2.recv_until_type("room_joined")
            self.assertIsNotNone(msg2)
            self.assertEqual(msg2["player"], "white")

            start_2 = c2.recv_until_type("game_start", 3)
            self.assertIsNotNone(start_2)
            self.assertEqual(start_2["black"], "Alice")
            self.assertEqual(start_2["white"], "Bob")
            self.assertEqual(start_2["current_player"], "black")
            self.assertEqual(start_2.get("your_side"), "white")

            start_1 = c1.recv_until_type("game_start", 3)
            self.assertIsNotNone(start_1)
            self.assertEqual(start_1.get("your_side"), "black")
        finally:
            c1.close()
            c2.close()

    def test_move_sync_between_clients(self) -> None:
        c1 = TestClient()
        c2 = TestClient()
        room = "room_test3"
        try:
            c1.connect(TEST_HOST, self.port)
            c1.send(build_join_room(room, "A1"))
            c1.recv_until_type("room_joined")
            c2.connect(TEST_HOST, self.port)
            c2.send(build_join_room(room, "B1"))
            c2.recv_until_type("game_start")
            c1.recv_until_type("game_start")

            c1.send(build_move(7, 7))
            m1 = c1.recv_until_type("move_result", 3)
            m2 = c2.recv_until_type("move_result", 3)
            self.assertIsNotNone(m1)
            self.assertIsNotNone(m2)
            self.assertEqual(m1["row"], 7)
            self.assertEqual(m1["col"], 7)
            self.assertEqual(m1["player"], "black")
            self.assertEqual(m1["next_player"], "white")
            self.assertEqual(m1, m2)
        finally:
            c1.close()
            c2.close()

    def test_invalid_move_rejected(self) -> None:
        c1 = TestClient()
        c2 = TestClient()
        room = "room_test4"
        try:
            c1.connect(TEST_HOST, self.port)
            c1.send(build_join_room(room, "A2"))
            c1.recv_until_type("room_joined")
            c2.connect(TEST_HOST, self.port)
            c2.send(build_join_room(room, "B2"))
            c2.recv_until_type("game_start")
            c1.recv_until_type("game_start")

            c1.send(build_move(7, 7))
            c1.recv_until_type("move_result")

            c1.send(build_move(7, 8))
            inv = c1.recv_until_type("invalid_move", 2)
            self.assertIsNotNone(inv)
        finally:
            c1.close()
            c2.close()

    def test_room_full_third_client_rejected(self) -> None:
        c1 = TestClient()
        c2 = TestClient()
        c3 = TestClient()
        room = "room_test5"
        try:
            c1.connect(TEST_HOST, self.port)
            c1.send(build_join_room(room, "A"))
            c1.recv_until_type("room_joined")
            c2.connect(TEST_HOST, self.port)
            c2.send(build_join_room(room, "B"))
            c2.recv_until_type("room_joined")

            c3.connect(TEST_HOST, self.port)
            c3.send(build_join_room(room, "C"))
            full = c3.recv_until_type("room_full", 3)
            self.assertIsNotNone(full)
        finally:
            c1.close()
            c2.close()
            c3.close()

    def test_game_over_win_detection(self) -> None:
        c1 = TestClient()
        c2 = TestClient()
        room = "room_test6"
        try:
            c1.connect(TEST_HOST, self.port)
            c1.send(build_join_room(room, "Winner"))
            c1.recv_until_type("room_joined")
            c2.connect(TEST_HOST, self.port)
            c2.send(build_join_room(room, "Loser"))
            c2.recv_until_type("game_start")
            c1.recv_until_type("game_start")

            moves = [
                (c1, 0, 0),
                (c2, 1, 0),
                (c1, 0, 1),
                (c2, 1, 1),
                (c1, 0, 2),
                (c2, 1, 2),
                (c1, 0, 3),
                (c2, 1, 3),
                (c1, 0, 4),
            ]
            for c, r, col in moves:
                c.send(build_move(r, col))
                r1 = c1.recv_until_type("move_result", 3)
                r2 = c2.recv_until_type("move_result", 3)
                self.assertIsNotNone(r1)
                self.assertIsNotNone(r2)
                self.assertEqual(r1["row"], r)
                self.assertEqual(r1["col"], col)
                self.assertEqual(r2["row"], r)
                self.assertEqual(r2["col"], col)

            over = c1.recv_until_type("game_over", 3)
            self.assertIsNotNone(over)
            self.assertEqual(over["winner"], "black")

            over2 = c2.recv_until_type("game_over", 3)
            self.assertIsNotNone(over2)
            self.assertEqual(over2["winner"], "black")
        finally:
            c1.close()
            c2.close()

    def test_player_left_disconnect_notified(self) -> None:
        c1 = TestClient()
        c2 = TestClient()
        room = "room_test7"
        try:
            c1.connect(TEST_HOST, self.port)
            c1.send(build_join_room(room, "P1"))
            c1.recv_until_type("room_joined")
            c2.connect(TEST_HOST, self.port)
            c2.send(build_join_room(room, "P2"))
            c2.recv_until_type("game_start")
            c1.recv_until_type("game_start")

            c1.close()
            left = c2.recv_until_type("player_left", 5)
            self.assertIsNotNone(left)
        finally:
            c2.close()

    def test_restart_both_agree(self) -> None:
        c1 = TestClient()
        c2 = TestClient()
        room = "room_test8"
        try:
            c1.connect(TEST_HOST, self.port)
            c1.send(build_join_room(room, "A"))
            c1.recv_until_type("room_joined")
            c2.connect(TEST_HOST, self.port)
            c2.send(build_join_room(room, "B"))
            c2.recv_until_type("game_start")
            c1.recv_until_type("game_start")

            c1.send(build_restart_request())
            c2.send(build_restart_request())

            restart = c1.recv_until_type("game_restart", 3)
            self.assertIsNotNone(restart)
            restart2 = c2.recv_until_type("game_restart", 3)
            self.assertIsNotNone(restart2)

            gs = c1.recv_until_type("game_start", 3)
            self.assertIsNotNone(gs)
        finally:
            c1.close()
            c2.close()


if __name__ == "__main__":
    unittest.main()

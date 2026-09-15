from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from common.constants import BLACK, WHITE
from server.room_manager import Room, RoomManager


def _fake_conn():
    c = MagicMock()
    c.sendall = MagicMock()
    return c


class TestRoom(unittest.TestCase):
    def test_empty_room(self) -> None:
        r = Room(room_id="100", game=MagicMock())
        self.assertTrue(r.is_empty())
        self.assertFalse(r.is_full())

    def test_is_full_after_two(self) -> None:
        r = Room(room_id="100", game=MagicMock())
        r.players["a"] = MagicMock(side=BLACK)
        self.assertFalse(r.is_full())
        r.players["b"] = MagicMock(side=WHITE)
        self.assertTrue(r.is_full())

    def test_get_black_white_player(self) -> None:
        r = Room(room_id="100", game=MagicMock())
        from server.room_manager import PlayerSession
        a = PlayerSession("a", "Alice", BLACK, _fake_conn(), ("127.0.0.1", 1))
        b = PlayerSession("b", "Bob", WHITE, _fake_conn(), ("127.0.0.1", 2))
        r.players["a"] = a
        r.players["b"] = b
        self.assertIs(r.get_black_player(), a)
        self.assertIs(r.get_white_player(), b)
        self.assertEqual(r.get_side("a"), BLACK)
        self.assertEqual(r.get_side("b"), WHITE)
        self.assertIsNone(r.get_side("z"))

    def test_get_other_session(self) -> None:
        r = Room(room_id="100", game=MagicMock())
        from server.room_manager import PlayerSession
        a = PlayerSession("a", "A", BLACK, _fake_conn(), ("1", 1))
        b = PlayerSession("b", "B", WHITE, _fake_conn(), ("2", 2))
        r.players["a"] = a
        r.players["b"] = b
        self.assertIs(r.get_other_session("a"), b)
        self.assertIs(r.get_other_session("b"), a)
        self.assertIsNone(r.get_other_session("z"))


class TestRoomManager(unittest.TestCase):
    def setUp(self) -> None:
        self.rm = RoomManager()

    def test_create_and_get_room(self) -> None:
        r = self.rm.create_room("R1")
        self.assertEqual(r.room_id, "R1")
        self.assertIs(self.rm.get_room("R1"), r)

    def test_get_room_not_exists(self) -> None:
        self.assertIsNone(self.rm.get_room("missing"))

    def test_get_or_create_room(self) -> None:
        r1 = self.rm.get_or_create_room("R2")
        r2 = self.rm.get_or_create_room("R2")
        self.assertIs(r1, r2)

    def test_remove_room(self) -> None:
        self.rm.create_room("R3")
        self.rm.remove_room("R3")
        self.assertIsNone(self.rm.get_room("R3"))

    def test_join_room_first_player_black(self) -> None:
        p, room, started = self.rm.join_room("R4", "Alice", _fake_conn(), ("1", 1))
        self.assertIsNotNone(p)
        self.assertEqual(p.side, BLACK)
        self.assertFalse(started)
        self.assertEqual(len(room.players), 1)

    def test_join_room_second_player_white_starts_game(self) -> None:
        self.rm.join_room("R5", "A", _fake_conn(), ("1", 1))
        p2, room, started = self.rm.join_room("R5", "B", _fake_conn(), ("2", 2))
        self.assertEqual(p2.side, WHITE)
        self.assertTrue(started)
        self.assertTrue(room.game_started)
        self.assertEqual(len(room.players), 2)

    def test_join_full_room_rejected(self) -> None:
        self.rm.join_room("R6", "A", _fake_conn(), ("1", 1))
        self.rm.join_room("R6", "B", _fake_conn(), ("2", 2))
        p, room, started = self.rm.join_room("R6", "C", _fake_conn(), ("3", 3))
        self.assertIsNone(p)
        self.assertEqual(len(room.players), 2)
        self.assertFalse(started)

    def test_leave_room(self) -> None:
        p1, room, _ = self.rm.join_room("R7", "A", _fake_conn(), ("1", 1))
        sid = p1.session_id
        self.rm.leave_room("R7", sid)
        self.assertNotIn(sid, room.players)

    def test_find_player_room(self) -> None:
        p, room, _ = self.rm.join_room("R8", "A", _fake_conn(), ("1", 1))
        self.assertIs(self.rm.find_player_room(p.session_id), room)
        self.assertIsNone(self.rm.find_player_room("no-such-id"))

    def test_list_rooms_and_count(self) -> None:
        self.rm.join_room("X1", "a", _fake_conn(), ("1", 1))
        self.rm.join_room("X2", "a", _fake_conn(), ("1", 1))
        self.assertEqual(self.rm.get_room_count(), 2)
        self.assertEqual(len(self.rm.list_rooms()), 2)

    def test_total_players(self) -> None:
        self.rm.join_room("Y1", "a", _fake_conn(), ("1", 1))
        self.rm.join_room("Y1", "b", _fake_conn(), ("2", 2))
        self.rm.join_room("Y2", "c", _fake_conn(), ("3", 3))
        self.assertEqual(self.rm.get_total_players(), 3)

    def test_active_game_count(self) -> None:
        self.rm.join_room("Z1", "a", _fake_conn(), ("1", 1))
        self.rm.join_room("Z1", "b", _fake_conn(), ("2", 2))
        self.rm.join_room("Z2", "c", _fake_conn(), ("3", 3))
        self.assertEqual(self.rm.get_active_game_count(), 1)

    def test_vote_restart_both(self) -> None:
        p1, room, _ = self.rm.join_room("V1", "a", _fake_conn(), ("1", 1))
        p2, room, _ = self.rm.join_room("V1", "b", _fake_conn(), ("2", 2))
        v, total = self.rm.vote_restart("V1", p1.session_id)
        self.assertEqual(v, 1)
        self.assertEqual(total, 2)
        v, total = self.rm.vote_restart("V1", p2.session_id)
        self.assertEqual(v, 2)
        self.assertEqual(total, 2)

    def test_double_vote_not_counted(self) -> None:
        p1, _, _ = self.rm.join_room("V2", "a", _fake_conn(), ("1", 1))
        self.rm.join_room("V2", "b", _fake_conn(), ("2", 2))
        self.rm.vote_restart("V2", p1.session_id)
        v, _ = self.rm.vote_restart("V2", p1.session_id)
        self.assertEqual(v, 1)

    def test_do_restart(self) -> None:
        _, room, _ = self.rm.join_room("V3", "a", _fake_conn(), ("1", 1))
        self.rm.join_room("V3", "b", _fake_conn(), ("2", 2))
        room.game.place(BLACK, 0, 0)
        room.game.place(WHITE, 0, 1)
        self.assertNotEqual(room.game.board[0][0], 0)
        self.rm.do_restart("V3")
        self.assertEqual(room.game.board[0][0], 0)
        self.assertEqual(room.game.current_player, BLACK)

    def test_thread_safety_many_joins(self) -> None:
        errors = []

        def worker(room_id, name):
            try:
                for _ in range(20):
                    self.rm.join_room(
                        room_id, name, _fake_conn(), ("127.0.0.1", 0)
                    )
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(8):
            t = threading.Thread(target=worker, args=(f"TS{i}", f"P{i}"))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()

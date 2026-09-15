from __future__ import annotations

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from common.protocol import (
    MessageBuffer,
    build_error,
    build_game_start,
    build_join_room,
    build_move,
    build_move_result,
    build_room_joined,
    decode_message,
    encode_message,
    validate_message,
)


class TestEncoding(unittest.TestCase):
    def test_encode_message_ends_with_newline(self) -> None:
        msg = {"type": "ping"}
        data = encode_message(msg)
        self.assertTrue(data.endswith(b"\n"))

    def test_encode_decode_roundtrip(self) -> None:
        msg = {"type": "join_room", "room_id": "123456", "player_name": "Alice"}
        data = encode_message(msg)
        decoded = decode_message(data.decode("utf-8"))
        self.assertEqual(decoded, msg)

    def test_decode_invalid_json(self) -> None:
        self.assertIsNone(decode_message("{ not json "))
        self.assertIsNone(decode_message(""))

    def test_decode_empty_or_whitespace(self) -> None:
        self.assertIsNone(decode_message("   \n   "))
        self.assertEqual(decode_message("{}"), {})


class TestMessageBuffer(unittest.TestCase):
    def test_extract_single_message(self) -> None:
        buf = MessageBuffer()
        buf.feed(b'{"type":"ping"}\n')
        msgs, failed = buf.extract_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["type"], "ping")
        self.assertEqual(len(failed), 0)

    def test_extract_multiple_messages(self) -> None:
        buf = MessageBuffer()
        buf.feed(b'{"a":1}\n{"b":2}\n{"c":3}\n')
        msgs, _ = buf.extract_messages()
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0]["a"], 1)
        self.assertEqual(msgs[1]["b"], 2)
        self.assertEqual(msgs[2]["c"], 3)

    def test_tcp_sticky_packet(self) -> None:
        buf = MessageBuffer()
        buf.feed(b'{"t":1}\n{"t":2}\n{"t":3}')
        msgs, _ = buf.extract_messages()
        self.assertEqual(len(msgs), 2)
        buf.feed(b"\n")
        msgs, _ = buf.extract_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["t"], 3)

    def test_tcp_split_packet(self) -> None:
        buf = MessageBuffer()
        buf.feed(b'{"type":"jo')
        msgs, _ = buf.extract_messages()
        self.assertEqual(len(msgs), 0)
        buf.feed(b'in","r":"123"}\n')
        msgs, _ = buf.extract_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["type"], "join")

    def test_buffer_preserves_remainder(self) -> None:
        buf = MessageBuffer()
        buf.feed(b'{"a":1}\n{')
        buf.extract_messages()
        buf.feed(b'"b":2}\n')
        msgs, _ = buf.extract_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["b"], 2)

    def test_empty_feed(self) -> None:
        buf = MessageBuffer()
        buf.feed(b"")
        msgs, _ = buf.extract_messages()
        self.assertEqual(len(msgs), 0)

    def test_empty_lines_ignored(self) -> None:
        buf = MessageBuffer()
        buf.feed(b"\n\n\n{\"a\":1}\n\n\n")
        msgs, failed = buf.extract_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(len(failed), 0)

    def test_invalid_lines_reported(self) -> None:
        buf = MessageBuffer()
        buf.feed(b'not json at all\n{"ok":1}\n')
        msgs, failed = buf.extract_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(len(failed), 1)
        self.assertIn("not json", failed[0])

    def test_clear_empties_buffer(self) -> None:
        buf = MessageBuffer()
        buf.feed(b'{"a":1}')
        self.assertFalse(buf.is_empty)
        buf.clear()
        self.assertTrue(buf.is_empty)

    def test_clear_preserves_byte_buffer_for_next_message(self) -> None:
        buf = MessageBuffer()
        buf.feed(b'{"stale":true}')
        buf.clear()
        buf.feed(b'{"type":"room_joined"}\n')
        messages, failed = buf.extract_messages()
        self.assertEqual(messages, [{"type": "room_joined"}])
        self.assertEqual(failed, [])

    def test_unicode_message(self) -> None:
        buf = MessageBuffer()
        buf.feed('{"name":"玩家黑"}'.encode("utf-8") + b"\n")
        msgs, _ = buf.extract_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["name"], "玩家黑")

    def test_unicode_message_split_inside_utf8_character(self) -> None:
        buf = MessageBuffer()
        data = '{"name":"玩家黑"}'.encode("utf-8") + b"\n"
        split_at = data.index("玩".encode("utf-8")) + 1
        buf.feed(data[:split_at])
        self.assertEqual(buf.extract_messages()[0], [])
        buf.feed(data[split_at:])
        messages, failed = buf.extract_messages()
        self.assertEqual(messages, [{"name": "玩家黑"}])
        self.assertEqual(failed, [])


class TestBuilders(unittest.TestCase):
    def test_build_join_room(self) -> None:
        m = build_join_room("999", "Bob")
        self.assertEqual(m["type"], "join_room")
        self.assertEqual(m["room_id"], "999")
        self.assertEqual(m["player_name"], "Bob")

    def test_build_room_joined(self) -> None:
        m = build_room_joined("999", "black")
        self.assertEqual(m["type"], "room_joined")
        self.assertEqual(m["player"], "black")

    def test_build_game_start(self) -> None:
        m = build_game_start("P1", "P2", "black")
        self.assertEqual(m["type"], "game_start")
        self.assertEqual(m["black"], "P1")
        self.assertEqual(m["white"], "P2")

    def test_build_move(self) -> None:
        m = build_move(3, 4)
        self.assertEqual(m["type"], "move")
        self.assertEqual(m["row"], 3)
        self.assertEqual(m["col"], 4)

    def test_build_move_result(self) -> None:
        m = build_move_result(1, 2, "black", "white")
        self.assertEqual(m["type"], "move_result")
        self.assertEqual(m["row"], 1)
        self.assertEqual(m["next_player"], "white")

    def test_build_error_with_code(self) -> None:
        m = build_error("oops", "ERR1")
        self.assertEqual(m["type"], "error")
        self.assertEqual(m["message"], "oops")
        self.assertEqual(m["code"], "ERR1")

    def test_build_error_without_code(self) -> None:
        m = build_error("oops")
        self.assertEqual(m["type"], "error")
        self.assertNotIn("code", m)


class TestValidate(unittest.TestCase):
    def test_valid_message(self) -> None:
        self.assertTrue(validate_message({"type": "ping"}))
        self.assertTrue(validate_message({"type": "move", "row": 1, "col": 2}))

    def test_invalid_message_no_type(self) -> None:
        self.assertFalse(validate_message({"a": 1}))

    def test_invalid_message_not_dict(self) -> None:
        self.assertFalse(validate_message([1, 2, 3]))
        self.assertFalse(validate_message("ping"))
        self.assertFalse(validate_message(None))

    def test_invalid_type_not_string(self) -> None:
        self.assertFalse(validate_message({"type": 123}))


if __name__ == "__main__":
    unittest.main()

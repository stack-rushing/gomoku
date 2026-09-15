from __future__ import annotations

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from client.ai import GomokuAI
from common.constants import BLACK, WHITE


class TestGomokuAI(unittest.TestCase):
    def test_ai_finds_immediate_win(self) -> None:
        board = [[0 for _ in range(15)] for _ in range(15)]
        for col in range(4):
            board[7][col] = BLACK

        ai = GomokuAI()
        move = ai.choose_move(board, BLACK, WHITE)

        self.assertEqual(move, (7, 4))

    def test_ai_blocks_opponent_win(self) -> None:
        board = [[0 for _ in range(15)] for _ in range(15)]
        for col in range(4):
            board[7][col] = WHITE

        ai = GomokuAI()
        move = ai.choose_move(board, BLACK, WHITE)

        self.assertEqual(move, (7, 4))

    def test_ai_extends_its_open_three(self) -> None:
        board = [[0 for _ in range(15)] for _ in range(15)]
        for col in range(7, 10):
            board[7][col] = BLACK

        ai = GomokuAI()
        move = ai.choose_move(board, BLACK, WHITE)

        self.assertEqual(move, (7, 6))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from common.constants import (
    BLACK,
    EMPTY,
    RESULT_DRAW,
    RESULT_ONGOING,
    RESULT_WIN_BLACK,
    RESULT_WIN_WHITE,
    WHITE,
)
from server.game import GomokuGame


class TestGomokuGame(unittest.TestCase):
    def setUp(self) -> None:
        self.game = GomokuGame(board_size=15)

    def test_initial_board_all_empty(self) -> None:
        for r in range(15):
            for c in range(15):
                self.assertEqual(self.game.board[r][c], EMPTY)

    def test_black_goes_first(self) -> None:
        self.assertEqual(self.game.current_player, BLACK)

    def test_valid_place_black(self) -> None:
        ok = self.game.place(BLACK, 7, 7)
        self.assertTrue(ok)
        self.assertEqual(self.game.board[7][7], BLACK)
        self.assertEqual(self.game.current_player, WHITE)

    def test_valid_place_white(self) -> None:
        self.game.place(BLACK, 7, 7)
        ok = self.game.place(WHITE, 7, 8)
        self.assertTrue(ok)
        self.assertEqual(self.game.board[7][8], WHITE)
        self.assertEqual(self.game.current_player, BLACK)

    def test_place_out_of_bound_row_neg(self) -> None:
        ok = self.game.place(BLACK, -1, 7)
        self.assertFalse(ok)

    def test_place_out_of_bound_col_too_big(self) -> None:
        ok = self.game.place(BLACK, 7, 15)
        self.assertFalse(ok)

    def test_place_duplicate(self) -> None:
        self.game.place(BLACK, 7, 7)
        ok = self.game.place(WHITE, 7, 7)
        self.assertFalse(ok)

    def test_not_your_turn_white_first(self) -> None:
        ok = self.game.place(WHITE, 7, 7)
        self.assertFalse(ok)
        self.assertEqual(self.game.board[7][7], EMPTY)

    def test_not_your_turn_double_black(self) -> None:
        self.game.place(BLACK, 7, 7)
        ok = self.game.place(BLACK, 7, 8)
        self.assertFalse(ok)

    def test_turns_alternate_correctly(self) -> None:
        self.assertEqual(self.game.current_player, BLACK)
        self.game.place(BLACK, 0, 0)
        self.assertEqual(self.game.current_player, WHITE)
        self.game.place(WHITE, 0, 1)
        self.assertEqual(self.game.current_player, BLACK)
        self.game.place(BLACK, 0, 2)
        self.assertEqual(self.game.current_player, WHITE)

    def test_horizontal_win_black(self) -> None:
        for i in range(4):
            self.game.place(BLACK, 0, i)
            self.game.place(WHITE, 1, i)
        self.game.place(BLACK, 0, 4)
        self.assertTrue(self.game.game_over)
        self.assertEqual(self.game.winner, BLACK)
        self.assertEqual(self.game.get_result(), RESULT_WIN_BLACK)

    def test_vertical_win_black(self) -> None:
        for i in range(4):
            self.game.place(BLACK, i, 0)
            self.game.place(WHITE, i, 1)
        self.game.place(BLACK, 4, 0)
        self.assertTrue(self.game.game_over)
        self.assertEqual(self.game.winner, BLACK)

    def test_diagonal_main_win_white(self) -> None:
        for i in range(4):
            self.game.place(BLACK, 0, i + 1)
            self.game.place(WHITE, i, i)
        self.game.place(BLACK, 0, 6)
        self.game.place(WHITE, 4, 4)
        self.assertTrue(self.game.game_over)
        self.assertEqual(self.game.winner, WHITE)
        self.assertEqual(self.game.get_result(), RESULT_WIN_WHITE)

    def test_diagonal_anti_win_black(self) -> None:
        for i in range(4):
            self.game.place(BLACK, i, 4 - i)
            self.game.place(WHITE, i, 0)
        self.game.place(BLACK, 4, 0)
        self.assertTrue(self.game.game_over)
        self.assertEqual(self.game.winner, BLACK)

    def test_win_more_than_five_horizontal(self) -> None:
        for i in range(6):
            if i > 0:
                self.game.place(WHITE, 10, i)
            self.game.place(BLACK, 5, i)
        self.assertTrue(self.game.game_over)
        self.assertEqual(self.game.winner, BLACK)

    def test_no_move_after_game_over(self) -> None:
        for i in range(4):
            self.game.place(BLACK, 0, i)
            self.game.place(WHITE, 1, i)
        self.game.place(BLACK, 0, 4)
        self.assertTrue(self.game.game_over)
        ok = self.game.place(WHITE, 2, 0)
        self.assertFalse(ok)

    def test_draw_board_full(self) -> None:
        phase = [0, 1, 1]
        last_r, last_c = 14, 14
        for r in range(15):
            p = phase[r % 3]
            for c in range(15):
                if r == last_r and c == last_c:
                    continue
                if (p + c) % 2 == 0:
                    self.game.board[r][c] = BLACK
                else:
                    self.game.board[r][c] = WHITE

        for r in range(15):
            for c in range(15):
                if r == last_r and c == last_c:
                    continue
                self.assertNotEqual(self.game.board[r][c], EMPTY)
        self.assertEqual(self.game.board[last_r][last_c], EMPTY)

        self.assertIsNone(self.game.winner)
        self.assertFalse(self.game.game_over)
        self.assertFalse(self.game._check_draw())

        p_last = phase[last_r % 3]
        last_player = BLACK if (p_last + last_c) % 2 == 0 else WHITE
        self.game.current_player = last_player
        ok = self.game.place(last_player, last_r, last_c)
        self.assertTrue(ok, "final place() failed")

        self.assertTrue(self.game.game_over,
                        f"Expected game_over, winner={self.game.winner} "
                        f"draw={self.game.is_draw} moves={self.game.move_history}")
        self.assertTrue(self.game.is_draw,
                        f"Expected is_draw=True, winner={self.game.winner}")
        self.assertIsNone(self.game.winner)
        self.assertEqual(self.game.get_result(), RESULT_DRAW)

    def test_result_ongoing_during_game(self) -> None:
        self.game.place(BLACK, 7, 7)
        self.assertEqual(self.game.get_result(), RESULT_ONGOING)

    def test_restart_clears_everything(self) -> None:
        for i in range(4):
            self.game.place(BLACK, 0, i)
            self.game.place(WHITE, 1, i)
        self.game.place(BLACK, 0, 4)
        self.assertTrue(self.game.game_over)
        self.game.restart()
        self.assertFalse(self.game.game_over)
        self.assertIsNone(self.game.winner)
        self.assertEqual(self.game.current_player, BLACK)
        for r in range(15):
            for c in range(15):
                self.assertEqual(self.game.board[r][c], EMPTY)

    def test_move_history_tracking(self) -> None:
        self.game.place(BLACK, 3, 4)
        self.game.place(WHITE, 5, 6)
        self.assertEqual(len(self.game.move_history), 2)
        self.assertEqual(self.game.move_history[0]["row"], 3)
        self.assertEqual(self.game.move_history[0]["col"], 4)
        self.assertEqual(self.game.move_history[0]["player"], "black")
        self.assertEqual(self.game.move_history[1]["player"], "white")

    def test_last_move_tracking(self) -> None:
        self.assertIsNone(self.game.last_move)
        self.game.place(BLACK, 1, 2)
        self.assertEqual(self.game.last_move, (1, 2))
        self.game.place(WHITE, 3, 4)
        self.assertEqual(self.game.last_move, (3, 4))


if __name__ == "__main__":
    unittest.main()

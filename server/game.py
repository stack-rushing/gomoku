from __future__ import annotations

from typing import List, Optional, Tuple

from common.constants import (
    BLACK,
    EMPTY,
    PLAYER_BLACK,
    PLAYER_WHITE,
    RESULT_DRAW,
    RESULT_ONGOING,
    RESULT_WIN_BLACK,
    RESULT_WIN_WHITE,
    WHITE,
)


DIRECTIONS = [
    (0, 1),
    (1, 0),
    (1, 1),
    (1, -1),
]


class GomokuGame:
    def __init__(self, board_size: int = 15) -> None:
        self.board_size = board_size
        self.board: List[List[int]] = []
        self.current_player: int = BLACK
        self.game_over: bool = False
        self.winner: Optional[int] = None
        self.is_draw: bool = False
        self.move_history: List[dict] = []
        self.last_move: Optional[Tuple[int, int]] = None
        self._reset_board()

    def _reset_board(self) -> None:
        self.board = [
            [EMPTY for _ in range(self.board_size)] for _ in range(self.board_size)
        ]
        self.current_player = BLACK
        self.game_over = False
        self.winner = None
        self.is_draw = False
        self.move_history = []
        self.last_move = None

    def restart(self) -> None:
        self._reset_board()

    def is_valid_position(self, row: int, col: int) -> bool:
        return 0 <= row < self.board_size and 0 <= col < self.board_size

    def is_cell_empty(self, row: int, col: int) -> bool:
        if not self.is_valid_position(row, col):
            return False
        return self.board[row][col] == EMPTY

    def can_place(self, player: int, row: int, col: int) -> bool:
        if self.game_over:
            return False
        if player != self.current_player:
            return False
        if not self.is_valid_position(row, col):
            return False
        if not self.is_cell_empty(row, col):
            return False
        return True

    def place(self, player: int, row: int, col: int) -> bool:
        if not self.can_place(player, row, col):
            return False

        self.board[row][col] = player
        self.last_move = (row, col)
        self.move_history.append(
            {
                "player": PLAYER_BLACK if player == BLACK else PLAYER_WHITE,
                "row": row,
                "col": col,
            }
        )

        if self._check_win(row, col, player):
            self.game_over = True
            self.winner = player
        elif self._check_draw():
            self.game_over = True
            self.is_draw = True
        else:
            self._switch_player()

        return True

    def _switch_player(self) -> None:
        self.current_player = WHITE if self.current_player == BLACK else BLACK

    def _count_direction(self, row: int, col: int, dr: int, dc: int, player: int) -> int:
        count = 0
        r, c = row + dr, col + dc
        while self.is_valid_position(r, c) and self.board[r][c] == player:
            count += 1
            r += dr
            c += dc
        return count

    def _check_win(self, row: int, col: int, player: int) -> bool:
        for dr, dc in DIRECTIONS:
            count = 1
            count += self._count_direction(row, col, dr, dc, player)
            count += self._count_direction(row, col, -dr, -dc, player)
            if count >= 5:
                return True
        return False

    def _check_draw(self) -> bool:
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] == EMPTY:
                    return False
        return True

    def get_result(self) -> str:
        if self.game_over:
            if self.winner == BLACK:
                return RESULT_WIN_BLACK
            elif self.winner == WHITE:
                return RESULT_WIN_WHITE
            elif self.is_draw:
                return RESULT_DRAW
        return RESULT_ONGOING

    def get_current_player_str(self) -> str:
        return PLAYER_BLACK if self.current_player == BLACK else PLAYER_WHITE

    def get_winner_str(self) -> Optional[str]:
        if self.winner == BLACK:
            return PLAYER_BLACK
        elif self.winner == WHITE:
            return PLAYER_WHITE
        return None

    def get_move_count(self) -> int:
        return len(self.move_history)

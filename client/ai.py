from __future__ import annotations

from typing import List, Optional, Tuple

from common.constants import BLACK, EMPTY, WHITE


class GomokuAI:
    def choose_move(
        self,
        board: List[List[int]],
        current_player: int,
        opponent_player: int,
    ) -> Optional[Tuple[int, int]]:
        for row in range(len(board)):
            for col in range(len(board[0])):
                if board[row][col] != EMPTY:
                    continue
                if self._would_win(board, row, col, current_player):
                    return row, col

        for row in range(len(board)):
            for col in range(len(board[0])):
                if board[row][col] != EMPTY:
                    continue
                if self._would_win(board, row, col, opponent_player):
                    return row, col

        best_move: Optional[Tuple[int, int]] = None
        best_score = -1
        center = len(board) // 2
        for row, col in self._candidate_moves(board):
            score = self._score_position(board, row, col, current_player)
            score += self._score_position(board, row, col, opponent_player) * 2
            score -= abs(row - center) + abs(col - center)
            if score > best_score:
                best_score = score
                best_move = row, col
        return best_move

    def _candidate_moves(self, board: List[List[int]]) -> List[Tuple[int, int]]:
        candidates = set()
        has_piece = False
        for row in range(len(board)):
            for col in range(len(board[0])):
                if board[row][col] == EMPTY:
                    continue
                has_piece = True
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        candidate_row = row + dr
                        candidate_col = col + dc
                        if (
                            0 <= candidate_row < len(board)
                            and 0 <= candidate_col < len(board[0])
                            and board[candidate_row][candidate_col] == EMPTY
                        ):
                            candidates.add((candidate_row, candidate_col))
        if not has_piece:
            center = len(board) // 2
            return [(center, center)]
        return sorted(candidates)

    def _score_position(
        self,
        board: List[List[int]],
        row: int,
        col: int,
        player: int,
    ) -> int:
        score = 0
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            forward, forward_open = self._line_info(board, row, col, dr, dc, player)
            backward, backward_open = self._line_info(board, row, col, -dr, -dc, player)
            pieces = 1 + forward + backward
            open_ends = int(forward_open) + int(backward_open)
            score += self._line_score(pieces, open_ends)
        return score

    def _line_info(
        self,
        board: List[List[int]],
        row: int,
        col: int,
        dr: int,
        dc: int,
        player: int,
    ) -> Tuple[int, bool]:
        count = 0
        row += dr
        col += dc
        while 0 <= row < len(board) and 0 <= col < len(board[0]) and board[row][col] == player:
            count += 1
            row += dr
            col += dc
        return count, 0 <= row < len(board) and 0 <= col < len(board[0]) and board[row][col] == EMPTY

    def _line_score(self, pieces: int, open_ends: int) -> int:
        if pieces >= 5:
            return 100_000
        if pieces == 4:
            return 10_000 if open_ends == 2 else 2_000
        if pieces == 3:
            return 1_000 if open_ends == 2 else 200
        if pieces == 2:
            return 100 if open_ends == 2 else 20
        return 5

    def _would_win(
        self,
        board: List[List[int]],
        row: int,
        col: int,
        player: int,
    ) -> bool:
        board[row][col] = player
        try:
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                count = 1
                count += self._count_direction(board, row, col, dr, dc, player)
                count += self._count_direction(board, row, col, -dr, -dc, player)
                if count >= 5:
                    return True
            return False
        finally:
            board[row][col] = EMPTY

    def _count_direction(
        self,
        board: List[List[int]],
        row: int,
        col: int,
        dr: int,
        dc: int,
        player: int,
    ) -> int:
        count = 0
        r = row + dr
        c = col + dc
        while 0 <= r < len(board) and 0 <= c < len(board[0]) and board[r][c] == player:
            count += 1
            r += dr
            c += dc
        return count

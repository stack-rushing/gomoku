from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Tuple

from client.config import (
    BLACK_COLOR,
    BOARD_COLOR,
    BOARD_SIZE,
    CANVAS_SIZE,
    CELL_SIZE,
    GRID_COLOR,
    HOVER_COLOR,
    LAST_MARK_COLOR,
    MARGIN,
    WHITE_COLOR,
)


class GomokuBoard(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        board_size: int = BOARD_SIZE,
        cell_size: int = CELL_SIZE,
        margin: int = MARGIN,
        on_move: Optional[Callable[[int, int], None]] = None,
        **kwargs,
    ) -> None:
        self.board_size = board_size
        self.cell_size = cell_size
        self.margin = margin

        canvas_size = (board_size - 1) * cell_size + margin * 2
        self.canvas_size = canvas_size

        super().__init__(
            master,
            width=canvas_size,
            height=canvas_size,
            bg=BOARD_COLOR,
            highlightthickness=2,
            highlightbackground=GRID_COLOR,
            **kwargs,
        )

        self._board: list[list[int]] = [
            [0 for _ in range(board_size)] for _ in range(board_size)
        ]
        self._last_move: Optional[Tuple[int, int]] = None
        self._on_move_cb = on_move
        self._enabled = True
        self._my_side: int = 0
        self._current_side: int = 1

        self._hover_row = -1
        self._hover_col = -1
        self._hover_enabled = True

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Motion>", self._on_mouse_move)
        self.bind("<Leave>", self._on_mouse_leave)
        self.bind("<Button-1>", self._on_click)

        self._draw_grid()

    def set_on_move(self, on_move: Callable[[int, int], None]) -> None:
        self._on_move_cb = on_move

    def set_my_side(self, side: int) -> None:
        self._my_side = side
        self._redraw()

    def set_current_side(self, side: int) -> None:
        self._current_side = side
        self._update_hover()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._hover_enabled = enabled
        self._redraw()

    def is_my_turn(self) -> bool:
        return self._enabled and self._my_side != 0 and self._my_side == self._current_side

    def place_piece(self, row: int, col: int, piece: int) -> bool:
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            return False
        if self._board[row][col] != 0:
            return False
        self._board[row][col] = piece
        self._last_move = (row, col)
        self._redraw()
        return True

    def clear_board(self) -> None:
        for r in range(self.board_size):
            for c in range(self.board_size):
                self._board[r][c] = 0
        self._last_move = None
        self._redraw()

    def get_piece(self, row: int, col: int) -> int:
        if 0 <= row < self.board_size and 0 <= col < self.board_size:
            return self._board[row][col]
        return 0

    def _draw_grid(self) -> None:
        self.delete("grid")
        size = self.canvas_size
        margin = self.margin
        cell = self.cell_size

        for i in range(self.board_size):
            x = margin + i * cell
            self.create_line(
                margin, x, size - margin, x, fill=GRID_COLOR, width=1, tags="grid"
            )
            self.create_line(
                x, margin, x, size - margin, fill=GRID_COLOR, width=1, tags="grid"
            )

        star_points = [
            (3, 3),
            (3, 11),
            (11, 3),
            (11, 11),
            (7, 7),
        ]
        for r, c in star_points:
            if r < self.board_size and c < self.board_size:
                x = margin + c * cell
                y = margin + r * cell
                self.create_oval(
                    x - 4, y - 4, x + 4, y + 4, fill=GRID_COLOR, tags="grid"
                )

        for i in range(self.board_size):
            x = margin - 16
            y = margin + i * cell
            self.create_text(
                x, y, text=str(self.board_size - i), fill=GRID_COLOR,
                font=("Arial", 10), tags="grid",
            )
            x = margin + i * cell
            y = size - margin + 16
            self.create_text(
                x, y, text=chr(65 + i), fill=GRID_COLOR,
                font=("Arial", 10), tags="grid",
            )

    def _draw_pieces(self) -> None:
        self.delete("pieces")
        margin = self.margin
        cell = self.cell_size
        radius = cell // 2 - 2

        for r in range(self.board_size):
            for c in range(self.board_size):
                p = self._board[r][c]
                if p == 0:
                    continue
                x = margin + c * cell
                y = margin + r * cell
                color = BLACK_COLOR if p == 1 else WHITE_COLOR
                outline = "#000000" if p == 1 else "#9ca3af"

                if p == 2:
                    self.create_oval(
                        x - radius - 1, y - radius - 1,
                        x + radius + 1, y + radius + 1,
                        fill="#d1d5db", outline="", tags="pieces",
                    )

                self.create_oval(
                    x - radius, y - radius,
                    x + radius, y + radius,
                    fill=color, outline=outline, width=1, tags="pieces",
                )

                if p == 1:
                    self.create_oval(
                        x - radius + 3, y - radius + 3,
                        x - radius + 8, y - radius + 8,
                        fill="#4b5563", outline="", tags="pieces",
                    )

    def _draw_last_move(self) -> None:
        self.delete("last_move")
        if self._last_move is None:
            return
        r, c = self._last_move
        x = self.margin + c * self.cell_size
        y = self.margin + r * self.cell_size
        size = 5
        self.create_rectangle(
            x - size, y - size, x + size, y + size,
            outline=LAST_MARK_COLOR, width=2, tags="last_move",
        )

    def _draw_hover(self) -> None:
        self.delete("hover")
        if not self._hover_enabled or self._hover_row < 0:
            return
        if self._board[self._hover_row][self._hover_col] != 0:
            return
        if not self.is_my_turn():
            return

        r, c = self._hover_row, self._hover_col
        x = self.margin + c * self.cell_size
        y = self.margin + r * self.cell_size
        radius = self.cell_size // 2 - 2
        color = BLACK_COLOR if self._current_side == 1 else WHITE_COLOR

        self.create_oval(
            x - radius, y - radius,
            x + radius, y + radius,
            fill=color, outline=HOVER_COLOR, width=2,
            stipple="gray50", tags="hover",
        )

    def _update_hover(self) -> None:
        self._draw_hover()

    def _redraw(self) -> None:
        self._draw_grid()
        self._draw_pieces()
        self._draw_last_move()
        self._draw_hover()

    def _xy_to_rc(self, x: int, y: int) -> Tuple[int, int]:
        c = round((x - self.margin) / self.cell_size)
        r = round((y - self.margin) / self.cell_size)
        return r, c

    def _is_valid_rc(self, r: int, c: int) -> bool:
        return 0 <= r < self.board_size and 0 <= c < self.board_size

    def _on_mouse_move(self, event: tk.Event) -> None:
        r, c = self._xy_to_rc(event.x, event.y)
        if (r, c) != (self._hover_row, self._hover_col):
            self._hover_row = r if self._is_valid_rc(r, c) else -1
            self._hover_col = c if self._is_valid_rc(r, c) else -1
            self._draw_hover()

    def _on_mouse_leave(self, event: tk.Event) -> None:
        if self._hover_row >= 0:
            self._hover_row = -1
            self._hover_col = -1
            self._draw_hover()

    def _on_click(self, event: tk.Event) -> None:
        if not self._enabled:
            return
        if not self.is_my_turn():
            return

        r, c = self._xy_to_rc(event.x, event.y)
        if not self._is_valid_rc(r, c):
            return
        if self._board[r][c] != 0:
            return

        if self._on_move_cb is not None:
            self._on_move_cb(r, c)

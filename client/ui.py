from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from client.ai import GomokuAI
from client.board import GomokuBoard
from client.config import (
    APP_TITLE,
    BLACK_COLOR,
    BOARD_SIZE,
    CANVAS_SIZE,
    UI_POLL_INTERVAL,
    WHITE_COLOR,
)
from client.network import (
    EVENT_CONNECTED,
    EVENT_DISCONNECTED,
    EVENT_ERROR,
    NetworkClient,
)
from common.constants import BLACK, WHITE
from server.game import GomokuGame


LOGIN_VIEW = "login"
GAME_VIEW = "game"


class GomokuClientUI:
    def __init__(self, root: tk.Tk, network: NetworkClient) -> None:
        self.root = root
        self.network = network

        self.root.title(APP_TITLE)
        self.root.geometry("760x820")
        self.root.minsize(720, 780)
        self.root.configure(bg="#f1f5f9")

        self._setup_style()

        self.room_id: str = ""
        self.player_name: str = ""
        self.my_side: int = 0
        self.ai_side: int = 0
        self.black_name: str = ""
        self.white_name: str = ""
        self.current_side: int = 1
        self.game_ended: bool = False
        self.restart_waiting: bool = False
        self.mode: str = "online"
        self.local_game: Optional[GomokuGame] = None
        self._ai_pending: bool = False
        self._ai_player = GomokuAI()
        self.current_view: str = LOGIN_VIEW
        self._last_network_event: str = "-"
        self._last_server_message: str = "-"

        self._login_vars: dict = {}
        self._build_login_view()
        self._build_game_view()

        self.container = tk.Frame(self.root, bg="#f1f5f9")
        self.container.pack(fill="both", expand=True)

        self.login_frame.place(in_=self.container, x=0, y=0, relwidth=1, relheight=1)
        self.game_frame.place(in_=self.container, x=0, y=0, relwidth=1, relheight=1)

        self._show_view(LOGIN_VIEW)

        self._on_quit_cb: Optional[Callable[[], None]] = None
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._start_ui_poll()

    def _setup_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "TLabel",
            background="#f1f5f9",
            foreground="#0f172a",
            font=("Microsoft YaHei", 10),
        )
        style.configure(
            "Title.TLabel",
            font=("Microsoft YaHei", 22, "bold"),
            foreground="#1e293b",
        )
        style.configure(
            "SubTitle.TLabel",
            font=("Microsoft YaHei", 11),
            foreground="#64748b",
        )
        style.configure(
            "Header.TLabel",
            font=("Microsoft YaHei", 14, "bold"),
            foreground="#0f172a",
        )
        style.configure(
            "Side.TLabel",
            font=("Microsoft YaHei", 11, "bold"),
            foreground="#0f172a",
        )
        style.configure(
            "Turn.TLabel",
            font=("Microsoft YaHei", 12, "bold"),
            background="#e0f2fe",
            foreground="#0369a1",
            padding=(12, 8),
        )
        style.configure(
            "TurnBlack.TLabel",
            background="#1e293b",
            foreground="#f8fafc",
        )
        style.configure(
            "TurnWhite.TLabel",
            background="#fef3c7",
            foreground="#92400e",
        )
        style.configure(
            "TButton",
            font=("Microsoft YaHei", 10, "bold"),
            padding=(16, 8),
        )
        style.configure(
            "Primary.TButton",
            background="#2563eb",
            foreground="#ffffff",
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8")],
        )
        style.configure(
            "Danger.TButton",
            background="#dc2626",
            foreground="#ffffff",
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#b91c1c")],
        )
        style.configure(
            "TEntry",
            padding=8,
        )
        style.configure(
            "Card.TFrame",
            background="#ffffff",
            relief="flat",
        )

    def _build_login_view(self) -> None:
        self.login_frame = ttk.Frame(self.root)
        self.login_frame.configure(style="Card.TFrame")

        outer = tk.Frame(self.login_frame, bg="#f1f5f9")
        outer.pack(fill="both", expand=True, padx=40, pady=40)

        card = tk.Frame(outer, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1")
        card.pack(fill="x", expand=False)

        title_frame = tk.Frame(card, bg="#ffffff")
        title_frame.pack(fill="x", padx=32, pady=(32, 24))
        ttk.Label(title_frame, text="五子棋联机版", style="Title.TLabel", background="#ffffff").pack(anchor="w")
        ttk.Label(title_frame, text="选择联机对战或 AI 对战", style="SubTitle.TLabel", background="#ffffff").pack(anchor="w", pady=(4, 0))

        form = tk.Frame(card, bg="#ffffff")
        form.pack(fill="both", expand=True, padx=32, pady=0)

        def add_field(parent, label, default, row, show=None):
            lbl = ttk.Label(parent, text=label, background="#ffffff")
            lbl.grid(row=row * 2, column=0, sticky="w", pady=(0, 4))
            entry = ttk.Entry(parent, width=36, font=("Microsoft YaHei", 11), show=show)
            entry.insert(0, default)
            entry.grid(row=row * 2 + 1, column=0, sticky="we", pady=(0, 16))
            return entry

        self._login_vars["host"] = add_field(form, "服务器地址", "127.0.0.1", 0)
        self._login_vars["port"] = add_field(form, "端口", "8888", 1)
        self._login_vars["name"] = add_field(form, "玩家名称", "Player", 2)
        self._login_vars["room"] = add_field(form, "房间号", "123456", 3)
        self._online_field_widgets = [
            widget
            for row in (0, 1, 2, 3, 6, 7)
            for widget in form.grid_slaves(row=row)
        ]

        mode_lbl = ttk.Label(form, text="对战方式", background="#ffffff")
        mode_lbl.grid(row=8, column=0, sticky="w", pady=(0, 4))
        self.mode_var = tk.StringVar(value="联机对战")
        self._login_vars["mode"] = ttk.Combobox(
            form,
            width=34,
            state="readonly",
            values=["联机对战", "AI 对战"],
            textvariable=self.mode_var,
            font=("Microsoft YaHei", 11),
        )
        self._login_vars["mode"].grid(row=9, column=0, sticky="we", pady=(0, 12))
        self._login_vars["mode"].bind("<<ComboboxSelected>>", lambda _event: self._sync_mode_ui())

        ai_side_lbl = ttk.Label(form, text="AI 角色", background="#ffffff")
        ai_side_lbl.grid(row=10, column=0, sticky="w", pady=(0, 4))
        self.ai_side_var = tk.StringVar(value="我执黑")
        self._login_vars["ai_side"] = ttk.Combobox(
            form,
            width=34,
            state="readonly",
            values=["我执黑", "我执白"],
            textvariable=self.ai_side_var,
            font=("Microsoft YaHei", 11),
        )
        self._login_vars["ai_side"].grid(row=11, column=0, sticky="we", pady=(0, 16))

        form.grid_columnconfigure(0, weight=1)

        btn_frame = tk.Frame(card, bg="#ffffff")
        btn_frame.pack(fill="x", padx=32, pady=(0, 32))

        self.join_btn = ttk.Button(
            btn_frame,
            text="开始匹配",
            style="Primary.TButton",
            command=self._on_join_room,
        )
        self.join_btn.pack(side="right")

        self._sync_mode_ui()

        self.status_label = ttk.Label(
            btn_frame,
            text="",
            style="SubTitle.TLabel",
            background="#ffffff",
            foreground="#dc2626",
        )
        self.status_label.pack(side="left")

    def _build_game_view(self) -> None:
        self.game_frame = tk.Frame(self.root, bg="#f1f5f9")

        top_bar = tk.Frame(self.game_frame, bg="#ffffff", height=72, highlightthickness=1, highlightbackground="#cbd5e1")
        top_bar.pack(fill="x", side="top")
        top_bar.pack_propagate(False)

        room_info = tk.Frame(top_bar, bg="#ffffff")
        room_info.pack(side="left", padx=24, pady=16)
        ttk.Label(room_info, text="房间：", background="#ffffff", style="SubTitle.TLabel").pack(side="left")
        self.room_label = ttk.Label(room_info, text="-", background="#ffffff", style="Header.TLabel")
        self.room_label.pack(side="left")

        btns = tk.Frame(top_bar, bg="#ffffff")
        btns.pack(side="right", padx=20, pady=12)

        self.restart_btn = ttk.Button(
            btns,
            text="重新开始",
            command=self._on_restart,
        )
        self.restart_btn.pack(side="right", padx=(8, 0))

        self.quit_btn = ttk.Button(
            btns,
            text="退出房间",
            style="Danger.TButton",
            command=self._on_quit_room,
        )
        self.quit_btn.pack(side="right")

        self.debug_btn = ttk.Button(
            btns,
            text="诊断",
            command=self._show_diagnostics,
        )
        self.debug_btn.pack(side="right", padx=(0, 8))

        body = tk.Frame(self.game_frame, bg="#f1f5f9")
        body.pack(fill="both", expand=True, padx=20, pady=20)

        board_wrap = tk.Frame(body, bg="#f1f5f9")
        board_wrap.pack(side="left", fill="y")

        self.board = GomokuBoard(
            board_wrap,
            board_size=BOARD_SIZE,
            on_move=self._on_board_move,
        )
        self.board.pack(padx=4, pady=4)

        side_panel = tk.Frame(body, bg="#f1f5f9", width=260)
        side_panel.pack(side="left", fill="both", expand=True, padx=(16, 0))
        side_panel.pack_propagate(False)

        info_card = tk.Frame(side_panel, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1")
        info_card.pack(fill="x")

        h = tk.Frame(info_card, bg="#ffffff")
        h.pack(fill="x", padx=16, pady=(16, 8))
        ttk.Label(h, text="玩家信息", style="Header.TLabel", background="#ffffff").pack(anchor="w")

        self.player_info_box = tk.Frame(info_card, bg="#ffffff")
        self.player_info_box.pack(fill="x", padx=16, pady=(0, 16))

        self._build_player_row(self.player_info_box, "黑方", 1, BLACK_COLOR)
        self._build_player_row(self.player_info_box, "白方", 2, WHITE_COLOR)

        turn_card = tk.Frame(side_panel, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1")
        turn_card.pack(fill="x", pady=(16, 0))

        h2 = tk.Frame(turn_card, bg="#ffffff")
        h2.pack(fill="x", padx=16, pady=(16, 8))
        ttk.Label(h2, text="当前状态", style="Header.TLabel", background="#ffffff").pack(anchor="w")

        self.turn_var = tk.StringVar(value="等待中...")
        self.turn_label = tk.Label(
            turn_card,
            textvariable=self.turn_var,
            bg="#e0f2fe",
            fg="#0369a1",
            font=("Microsoft YaHei", 12, "bold"),
            padx=16,
            pady=10,
        )
        self.turn_label.pack(fill="x", padx=16, pady=(0, 16))

        self.status_var = tk.StringVar(value="等待对手加入...")
        status_box = tk.Label(
            turn_card,
            textvariable=self.status_var,
            bg="#fef9c3",
            fg="#854d0e",
            font=("Microsoft YaHei", 10),
            padx=16,
            pady=10,
            justify="left",
            wraplength=230,
        )
        status_box.pack(fill="x", padx=16, pady=(0, 16))

        log_card = tk.Frame(side_panel, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1")
        log_card.pack(fill="both", expand=True, pady=(16, 0))

        h3 = tk.Frame(log_card, bg="#ffffff")
        h3.pack(fill="x", padx=16, pady=(16, 8))
        ttk.Label(h3, text="消息日志", style="Header.TLabel", background="#ffffff").pack(anchor="w")

        self.log_text = tk.Text(
            log_card,
            height=8,
            wrap="word",
            bg="#f8fafc",
            fg="#1e293b",
            font=("Microsoft YaHei", 9),
            relief="flat",
            state="disabled",
            padx=12,
            pady=8,
        )
        self.log_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _build_player_row(self, parent, title, side_int, dot_color):
        row = tk.Frame(parent, bg="#ffffff")
        row.pack(fill="x", pady=4)

        dot = tk.Label(row, text="", bg=dot_color, width=2, height=1)
        dot.pack(side="left")

        lbl = tk.Label(row, text=title + "：", bg="#ffffff", fg="#64748b", font=("Microsoft YaHei", 10))
        lbl.pack(side="left", padx=(10, 2))

        name_var = tk.StringVar(value="等待中")
        name_lbl = tk.Label(
            row,
            textvariable=name_var,
            bg="#ffffff",
            fg="#0f172a",
            font=("Microsoft YaHei", 10, "bold"),
        )
        name_lbl.pack(side="left")

        tag_var = tk.StringVar(value="")
        tag_lbl = tk.Label(
            row,
            textvariable=tag_var,
            bg="#ffffff",
            fg="#2563eb",
            font=("Microsoft YaHei", 9),
        )
        tag_lbl.pack(side="left", padx=(8, 0))

        if side_int == 1:
            self.black_name_var = name_var
            self.black_tag_var = tag_var
        else:
            self.white_name_var = name_var
            self.white_tag_var = tag_var

    def _show_view(self, view: str) -> None:
        self.current_view = view
        if view == LOGIN_VIEW:
            self.login_frame.lift()
        else:
            self.game_frame.lift()

    def set_on_quit(self, cb: Callable[[], None]) -> None:
        self._on_quit_cb = cb

    def _start_ui_poll(self) -> None:
        self._process_network_events()
        self.root.after(UI_POLL_INTERVAL, self._start_ui_poll)

    def _process_network_events(self) -> None:
        try:
            for ev in self.network.poll_events():
                self._handle_network_event(ev)

            for msg in self.network.poll_messages():
                self._handle_server_message(msg)
        except Exception as e:
            self._log(f"UI poll error: {e}")
            self._set_login_status(f"处理服务器消息失败: {e}")

    def _handle_network_event(self, event: dict) -> None:
        ev_type = event.get("type")
        payload = event.get("payload", {})
        self._last_network_event = f"{ev_type}: {payload}"

        if ev_type == EVENT_CONNECTED:
            host = payload.get("host", "")
            port = payload.get("port", 0)
            self._log(f"已连接服务器 {host}:{port}")
            self._do_join_room()
        elif ev_type == EVENT_DISCONNECTED:
            self._log("与服务器断开连接")
            if self.root.winfo_viewable():
                messagebox.showerror("网络错误", "与服务器断开连接，请重新加入房间。")
                self._return_to_login()
        elif ev_type == EVENT_ERROR:
            msg = payload.get("message", "未知错误")
            etype = payload.get("type", "")
            self._log(f"网络错误: {msg}")
            if etype == "connect_failed":
                self._set_login_status(f"无法连接服务器: {msg}")
                self._set_join_enabled(True)
            elif etype == "send_failed":
                self._set_login_status(f"发送匹配请求失败: {msg}")
                self._set_join_enabled(True)
            elif etype == "receive_failed":
                self._set_login_status(f"接收服务器消息失败: {msg}")

    def _handle_server_message(self, msg: dict) -> None:
        msg_type = msg.get("type")
        self._last_server_message = f"{msg_type}: {msg}"
        self._log(f"[Server] {msg_type}")

        if msg_type == "room_joined":
            self._on_room_joined(msg)
        elif msg_type == "room_full":
            self._on_room_full()
        elif msg_type == "game_start":
            self._on_game_start(msg)
        elif msg_type == "move_result":
            self._on_move_result(msg)
        elif msg_type == "invalid_move":
            self._on_invalid_move(msg)
        elif msg_type == "game_over":
            self._on_game_over(msg)
        elif msg_type == "draw":
            self._on_draw()
        elif msg_type == "restart_response":
            self._on_restart_response(msg)
        elif msg_type == "game_restart":
            self._on_game_restart()
        elif msg_type == "player_left":
            self._on_player_left()
        elif msg_type == "error":
            err_msg = msg.get("message", "未知错误")
            self._log(f"服务器错误: {err_msg}")
            messagebox.showwarning("服务器提示", err_msg)

    def _sync_mode_ui(self) -> None:
        is_ai = self.mode_var.get() == "AI 对战"
        for widget in self._online_field_widgets:
            if is_ai:
                widget.grid_remove()
            else:
                widget.grid()
        for key in ("host", "port"):
            widget = self._login_vars.get(key)
            if widget is not None:
                widget.configure(state="disabled" if is_ai else "normal")
        room_widget = self._login_vars.get("room")
        if room_widget is not None:
            room_widget.configure(state="disabled" if is_ai else "normal")
        ai_widget = self._login_vars.get("ai_side")
        if ai_widget is not None:
            ai_widget.configure(state="readonly" if is_ai else "disabled")
        if hasattr(self, "join_btn"):
            self.join_btn.config(text="开始 AI 对战" if is_ai else "开始匹配")

    def _on_join_room(self) -> None:
        mode = self.mode_var.get()
        if mode == "AI 对战":
            self._start_ai_game()
            return

        self._set_join_enabled(False)
        self._set_login_status("")

        host = self._login_vars["host"].get().strip() or "127.0.0.1"
        try:
            port = int(self._login_vars["port"].get().strip() or "8888")
        except ValueError:
            self._set_login_status("端口必须是数字")
            self._set_join_enabled(True)
            return

        name = self._login_vars["name"].get().strip()
        room = self._login_vars["room"].get().strip()

        if not name:
            self._set_login_status("请输入玩家名称")
            self._set_join_enabled(True)
            return
        if not room:
            self._set_login_status("请输入房间号")
            self._set_join_enabled(True)
            return
        if len(name) > 20:
            self._set_login_status("玩家名称过长 (最多20字符)")
            self._set_join_enabled(True)
            return

        self.player_name = name
        self.room_id = room
        self.mode = "online"

        self._prepare_online_match_view()

        self._log(f"开始匹配：连接服务器 {host}:{port}，房间={room}")
        self._set_login_status("正在连接服务器...")
        ok = self.network.connect(host, port)
        if not ok and not self.network.connected:
            self._set_join_enabled(True)
            self._return_to_login()

    def _prepare_online_match_view(self) -> None:
        self.my_side = 0
        self.black_name = ""
        self.white_name = ""
        self.current_side = BLACK
        self.game_ended = False
        self.restart_waiting = False
        self.room_label.config(text=self.room_id)
        self.black_name_var.set("等待中")
        self.white_name_var.set("等待中")
        self.black_tag_var.set("")
        self.white_tag_var.set("")
        self.board.clear_board()
        self.board.set_my_side(0)
        self.board.set_current_side(BLACK)
        self.board.set_enabled(False)
        self.turn_var.set("匹配中")
        self.status_var.set("正在匹配房间，请等待...")
        self._show_view(GAME_VIEW)

    def _start_ai_game(self) -> None:
        name = self._login_vars["name"].get().strip()
        if not name:
            self._set_login_status("请输入玩家名称")
            return
        if len(name) > 20:
            self._set_login_status("玩家名称过长 (最多20字符)")
            return

        self.mode = "ai"
        self.player_name = name
        self.room_id = "AI"
        self.my_side = BLACK if self.ai_side_var.get() == "我执黑" else WHITE
        self.ai_side = WHITE if self.my_side == BLACK else BLACK
        self.local_game = GomokuGame(board_size=BOARD_SIZE)
        self._ai_pending = False
        self.game_ended = False
        self.restart_waiting = False

        self.black_name = self.player_name if self.my_side == BLACK else "AI"
        self.white_name = "AI" if self.my_side == WHITE else self.player_name
        self.room_label.config(text="AI 对战")
        self.black_name_var.set(self.black_name)
        self.white_name_var.set(self.white_name)
        self.black_tag_var.set("（我）" if self.my_side == BLACK else "")
        self.white_tag_var.set("（我）" if self.my_side == WHITE else "")
        self.board.set_my_side(self.my_side)
        self.board.set_current_side(BLACK)
        self.board.set_enabled(self.my_side == BLACK)
        self.board.clear_board()
        self.turn_var.set("等待中")
        self.status_var.set("AI 对战已开始")
        self._show_view(GAME_VIEW)

        if self.ai_side == BLACK:
            self._schedule_ai_move()

    def _schedule_ai_move(self) -> None:
        if self.mode != "ai":
            return
        if self.local_game is None or self.local_game.game_over:
            return
        if self._ai_pending:
            return
        if self.local_game.current_player != self.ai_side:
            return
        self._ai_pending = True
        self.root.after(500, self._do_ai_move)

    def _do_ai_move(self) -> None:
        self._ai_pending = False
        if self.mode != "ai" or self.local_game is None or self.local_game.game_over:
            return
        if self.local_game.current_player != self.ai_side:
            return

        board = [row[:] for row in self.local_game.board]
        move = self._ai_player.choose_move(board, self.ai_side, self.my_side)
        if move is None:
            return

        row, col = move
        self._apply_local_move(row, col, self.ai_side)

    def _apply_local_move(self, row: int, col: int, player: int) -> bool:
        if self.local_game is None:
            return False
        ok = self.local_game.place(player, row, col)
        if not ok:
            return False

        self.board.place_piece(row, col, player)
        self.current_side = self.local_game.current_player
        self.board.set_current_side(self.current_side)
        self._update_turn_label()

        if self.local_game.game_over:
            self._finish_local_game()
            return True

        if self.mode == "ai":
            if self.local_game.current_player == self.ai_side:
                self.board.set_enabled(False)
                self._schedule_ai_move()
            else:
                self.board.set_enabled(self.my_side == self.local_game.current_player)
        return True

    def _finish_local_game(self) -> None:
        if self.local_game is None:
            return
        self.game_ended = True
        self.board.set_enabled(False)
        if self.local_game.is_draw:
            self.turn_var.set("游戏结束")
            self.status_var.set("和棋！")
            self._log("AI 对战结束：和棋")
            if self.root.winfo_viewable():
                messagebox.showinfo("和棋", "AI 对战和棋！")
            return

        winner_side = self.local_game.winner
        if winner_side == self.my_side:
            self.turn_var.set("游戏结束")
            self.status_var.set("你赢了！")
            self._log("AI 对战结束：你赢了")
            if self.root.winfo_viewable():
                messagebox.showinfo("胜利", "你赢了这局 AI 对战！")
        else:
            self.turn_var.set("游戏结束")
            self.status_var.set("AI 获胜")
            self._log("AI 对战结束：AI 获胜")
            if self.root.winfo_viewable():
                messagebox.showinfo("失败", "AI 获胜，本局结束。")

    def _on_board_move(self, row: int, col: int) -> None:
        if self.mode == "ai":
            if self.local_game is None:
                return
            if self.game_ended:
                return
            if self.local_game.current_player != self.my_side:
                return
            self._apply_local_move(row, col, self.my_side)
            return

        if self.game_ended:
            return
        side_str = "黑方" if self.my_side == 1 else "白方"
        self._log(f"落子 ({row},{col}) {side_str}")
        self.network.send_move(row, col)

    def _do_join_room(self) -> None:
        if not self.room_id or not self.player_name:
            return
        self._log(f"已连接服务器，正在匹配房间 {self.room_id}")
        self._set_login_status("正在发送匹配请求...")
        ok = self.network.join_room(self.room_id, self.player_name)
        if not ok:
            self._set_login_status("加入房间失败")
            self._set_join_enabled(True)

    def _on_room_joined(self, msg: dict) -> None:
        side = msg.get("player", "")
        self.my_side = 1 if side == "black" else 2
        self.room_label.config(text=self.room_id)

        side_name = "黑方" if self.my_side == 1 else "白方"
        self._log(f"加入成功！您是 {side_name}")

        if self.my_side == 1:
            self.black_name_var.set(self.player_name)
            self.black_tag_var.set("（我）")
        else:
            self.white_name_var.set(self.player_name)
            self.white_tag_var.set("（我）")

        self.status_var.set("已进入房间，正在等待另一名玩家匹配...")
        self.turn_var.set("匹配中")
        self.game_ended = False
        self.restart_waiting = False
        self.board.set_my_side(self.my_side)
        self.board.set_current_side(1)
        self.board.set_enabled(False)
        self.board.clear_board()
        self._set_join_enabled(True)
        self._show_view(GAME_VIEW)

    def _on_room_full(self) -> None:
        self._log("房间已满")
        self._set_login_status("房间已满，请换一个房间号")
        self._set_join_enabled(True)
        self.network.disconnect()

    def _on_game_start(self, msg: dict) -> None:
        if self.my_side not in (BLACK, WHITE):
            your_side = msg.get("your_side", "")
            if your_side == "black":
                self.my_side = BLACK
            elif your_side == "white":
                self.my_side = WHITE
            self.board.set_my_side(self.my_side)

        if self.my_side not in (BLACK, WHITE):
            self._log("收到开局消息，但尚未确认玩家棋色")
            self._set_login_status("匹配状态异常，请重新开始匹配")
            return

        self.black_name = msg.get("black", "")
        self.white_name = msg.get("white", "")
        self.black_name_var.set(self.black_name)
        self.white_name_var.set(self.white_name)
        self.black_tag_var.set("（我）" if self.my_side == BLACK else "")
        self.white_tag_var.set("（我）" if self.my_side == WHITE else "")
        cp = msg.get("current_player", "black")
        self.current_side = 1 if cp == "black" else 2
        self.game_ended = False
        self.restart_waiting = False

        self._log(f"匹配成功！黑方={self.black_name} 白方={self.white_name}")
        self.status_var.set("匹配成功，游戏开始")
        self.board.set_current_side(self.current_side)
        self.board.set_enabled(True)
        self._show_view(GAME_VIEW)
        self._update_turn_label()

    def _on_move_result(self, msg: dict) -> None:
        row = msg.get("row", -1)
        col = msg.get("col", -1)
        player_str = msg.get("player", "")
        next_player_str = msg.get("next_player", "")
        piece = 1 if player_str == "black" else 2
        self.board.place_piece(row, col, piece)

        self.current_side = 1 if next_player_str == "black" else 2
        self.board.set_current_side(self.current_side)
        self._update_turn_label()

    def _on_invalid_move(self, msg: dict) -> None:
        reason = msg.get("reason", "非法落子")
        self._log(f"非法落子: {reason}")
        self.status_var.set(f"非法落子：{reason}")

    def _on_game_over(self, msg: dict) -> None:
        winner = msg.get("winner", "")
        self.game_ended = True
        self.board.set_enabled(False)

        if (winner == "black" and self.my_side == 1) or (winner == "white" and self.my_side == 2):
            result_text = "恭喜你获胜！"
            title = "胜利"
            icon = "info"
        else:
            result_text = "很遗憾，你输了。"
            title = "失败"
            icon = "warning"

        winner_name = self.black_name if winner == "black" else self.white_name
        self.turn_var.set("游戏结束")
        self.status_var.set(f"{winner_name} 获胜！")
        self._log(f"游戏结束: {winner_name} 获胜")

        if self.root.winfo_viewable():
            messagebox.showinfo(title, f"{result_text}\n胜者：{winner_name}")

    def _on_draw(self) -> None:
        self.game_ended = True
        self.board.set_enabled(False)
        self.turn_var.set("游戏结束")
        self.status_var.set("和棋！")
        self._log("游戏结束：和棋")
        if self.root.winfo_viewable():
            messagebox.showinfo("和棋", "棋盘下满，双方和棋！")

    def _on_restart(self) -> None:
        if self.mode == "ai":
            self._restart_ai_game()
            return
        if self.restart_waiting:
            return
        self.restart_waiting = True
        self.status_var.set("已申请重开，等待对方同意...")
        self._log("发送重新开始请求")
        self.network.send_restart_request()

    def _restart_ai_game(self) -> None:
        self.local_game = GomokuGame(board_size=BOARD_SIZE)
        self._ai_pending = False
        self.game_ended = False
        self.restart_waiting = False
        self.current_side = BLACK
        self.board.clear_board()
        self.board.set_my_side(self.my_side)
        self.board.set_current_side(BLACK)
        self.board.set_enabled(self.my_side == BLACK)
        self.status_var.set("AI 对战已重新开始")
        self._log("AI 对战已重新开始")
        self._update_turn_label()
        if self.ai_side == BLACK:
            self._schedule_ai_move()

    def _on_restart_response(self, msg: dict) -> None:
        if msg.get("agreed"):
            self.status_var.set("已发送重开请求，等待对方...")

    def _on_game_restart(self) -> None:
        self.game_ended = False
        self.restart_waiting = False
        self.board.clear_board()
        self.current_side = 1
        self.board.set_current_side(1)
        self.board.set_enabled(True)
        self.turn_var.set("游戏进行中")
        self.status_var.set("游戏重新开始")
        self._log("游戏已重新开始")
        self._update_turn_label()

    def _on_player_left(self) -> None:
        self._log("对手离开房间")
        self.game_ended = True
        self.board.set_enabled(False)
        self.status_var.set("对手已离开房间")
        self.turn_var.set("等待中")
        if self.root.winfo_viewable():
            messagebox.showwarning("提示", "对手已离开房间。")

    def _on_quit_room(self) -> None:
        if messagebox.askyesno("确认", "确定要退出当前房间吗？"):
            self._return_to_login()

    def _return_to_login(self) -> None:
        self.network.disconnect()
        self.mode = "online"
        self.local_game = None
        self._ai_pending = False
        self.room_id = ""
        self.my_side = 0
        self.ai_side = 0
        self.black_name = ""
        self.white_name = ""
        self.current_side = 1
        self.game_ended = False
        self.restart_waiting = False
        self.mode_var.set("联机对战")
        self.ai_side_var.set("我执黑")
        self.black_name_var.set("等待中")
        self.white_name_var.set("等待中")
        self.black_tag_var.set("")
        self.white_tag_var.set("")
        self.turn_var.set("等待中...")
        self.status_var.set("等待对手加入...")
        self.board.clear_board()
        self.board.set_enabled(False)
        self._sync_mode_ui()
        self._set_login_status("")
        self._set_join_enabled(True)
        self._show_view(LOGIN_VIEW)

    def _on_close(self) -> None:
        if self._on_quit_cb:
            try:
                self._on_quit_cb()
            except Exception:
                pass
        self.network.disconnect()
        try:
            self.root.destroy()
        except Exception:
            pass

    def _set_join_enabled(self, enabled: bool) -> None:
        try:
            self.join_btn.config(state="normal" if enabled else "disabled")
        except Exception:
            pass

    def _set_login_status(self, text: str) -> None:
        try:
            self.status_label.config(text=text)
        except Exception:
            pass

    def _show_diagnostics(self) -> None:
        side_text = "未知"
        if self.my_side == BLACK:
            side_text = "黑方"
        elif self.my_side == WHITE:
            side_text = "白方"

        current_text = "黑方" if self.current_side == BLACK else "白方"
        info_lines = [
            f"当前页面: {self.current_view}",
            f"模式: {self.mode}",
            f"房间号: {self.room_id or '-'}",
            f"玩家名: {self.player_name or '-'}",
            f"我的棋色: {side_text}",
            f"当前回合: {current_text}",
            f"网络连接: {'已连接' if self.network.connected else '未连接'}",
            f"最近收到字节: {self.network.last_received_bytes or '-'}",
            f"最近收包时间: {time.strftime('%H:%M:%S', time.localtime(self.network.last_received_at)) if self.network.last_received_at else '-'}",
            f"接收线程错误: {self.network.last_receive_error or '-'}",
            f"最近网络事件: {self._last_network_event}",
            f"最近服务器消息: {self._last_server_message}",
        ]
        messagebox.showinfo("联机诊断信息", "\n".join(info_lines))

    def _update_turn_label(self) -> None:
        if self.game_ended:
            return
        if self.current_side == 1:
            self.turn_label.config(bg="#1e293b", fg="#f8fafc")
            self.turn_var.set("当前回合：黑方")
        else:
            self.turn_label.config(bg="#fef3c7", fg="#92400e")
            self.turn_var.set("当前回合：白方")

        if self.board.is_my_turn():
            self.status_var.set("轮到你下棋，请点击棋盘")
        else:
            other = "白方" if self.my_side == 1 else "黑方"
            self.status_var.set(f"等待对方落子（{other}）")

    def _log(self, message: str) -> None:
        try:
            self.log_text.config(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        except Exception:
            pass

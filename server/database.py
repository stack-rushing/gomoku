from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, List, Optional

from common.constants import (
    PLAYER_BLACK,
    PLAYER_NONE,
    PLAYER_WHITE,
    RESULT_DRAW,
    RESULT_ONGOING,
    RESULT_WIN_BLACK,
    RESULT_WIN_WHITE,
)
from server.config import DATA_DIR, DB_PATH
from server.logger import logger


class Database:
    _instance: "Database | None" = None
    _initialized = False

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._lock = threading.RLock()
        os.makedirs(DATA_DIR, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS games (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id TEXT NOT NULL,
                        black_name TEXT NOT NULL,
                        white_name TEXT NOT NULL,
                        start_time REAL NOT NULL,
                        end_time REAL,
                        winner TEXT,
                        result TEXT NOT NULL,
                        moves TEXT,
                        move_count INTEGER DEFAULT 0
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_games_room ON games(room_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_games_result ON games(result)"
                )
                conn.commit()
                logger.info("[DB] 数据库初始化完成")
            except Exception as e:
                logger.exception(f"[DB] 数据库初始化失败: {e}")
                raise
            finally:
                conn.close()

    def create_game(
        self,
        room_id: str,
        black_name: str,
        white_name: str,
        start_time: Optional[float] = None,
    ) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                if start_time is None:
                    start_time = time.time()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO games (room_id, black_name, white_name, start_time, result, moves)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (room_id, black_name, white_name, start_time, RESULT_ONGOING, "[]"),
                )
                conn.commit()
                game_id = cursor.lastrowid
                logger.info(f"[DB] 创建对局: game_id={game_id}, room={room_id}")
                return game_id
            except Exception as e:
                logger.exception(f"[DB] 创建对局失败: {e}")
                return 0
            finally:
                conn.close()

    def end_game(
        self,
        game_id: int,
        result: str,
        winner: Optional[str],
        moves: List[dict],
        end_time: Optional[float] = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                if end_time is None:
                    end_time = time.time()
                if winner is None:
                    winner = PLAYER_NONE
                moves_json = json.dumps(moves, ensure_ascii=False)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE games
                    SET end_time=?, winner=?, result=?, moves=?, move_count=?
                    WHERE id=?
                    """,
                    (
                        end_time,
                        winner,
                        result,
                        moves_json,
                        len(moves),
                        game_id,
                    ),
                )
                conn.commit()
                logger.info(
                    f"[DB] 结束对局: game_id={game_id}, result={result}, winner={winner}"
                )
                return cursor.rowcount > 0
            except Exception as e:
                logger.exception(f"[DB] 结束对局失败 game_id={game_id}: {e}")
                return False
            finally:
                conn.close()

    def get_game_count(self) -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM games")
                row = cursor.fetchone()
                return row[0] if row else 0
            except Exception as e:
                logger.exception(f"[DB] 查询对局数失败: {e}")
                return 0
            finally:
                conn.close()

    def get_game_by_id(self, game_id: int) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM games WHERE id=?", (game_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                data = dict(row)
                if data.get("moves"):
                    try:
                        data["moves"] = json.loads(data["moves"])
                    except (json.JSONDecodeError, ValueError):
                        data["moves"] = []
                return data
            except Exception as e:
                logger.exception(f"[DB] 查询对局失败 id={game_id}: {e}")
                return None
            finally:
                conn.close()

    def get_recent_games(self, limit: int = 20) -> List[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM games ORDER BY start_time DESC LIMIT ?", (limit,)
                )
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    data = dict(row)
                    if data.get("moves"):
                        try:
                            data["moves"] = json.loads(data["moves"])
                        except (json.JSONDecodeError, ValueError):
                            data["moves"] = []
                    results.append(data)
                return results
            except Exception as e:
                logger.exception(f"[DB] 查询最近对局失败: {e}")
                return []
            finally:
                conn.close()

    def get_statistics(self) -> dict:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM games")
                total = cursor.fetchone()[0] or 0

                cursor.execute(
                    "SELECT COUNT(*) FROM games WHERE result=?", (RESULT_WIN_BLACK,)
                )
                black_wins = cursor.fetchone()[0] or 0

                cursor.execute(
                    "SELECT COUNT(*) FROM games WHERE result=?", (RESULT_WIN_WHITE,)
                )
                white_wins = cursor.fetchone()[0] or 0

                cursor.execute(
                    "SELECT COUNT(*) FROM games WHERE result=?", (RESULT_DRAW,)
                )
                draws = cursor.fetchone()[0] or 0

                cursor.execute(
                    "SELECT COALESCE(SUM(move_count), 0) FROM games WHERE result != ?",
                    (RESULT_ONGOING,),
                )
                total_moves = cursor.fetchone()[0] or 0

                return {
                    "total_games": total,
                    "black_wins": black_wins,
                    "white_wins": white_wins,
                    "draws": draws,
                    "total_moves": total_moves,
                }
            except Exception as e:
                logger.exception(f"[DB] 查询统计失败: {e}")
                return {
                    "total_games": 0,
                    "black_wins": 0,
                    "white_wins": 0,
                    "draws": 0,
                    "total_moves": 0,
                }
            finally:
                conn.close()

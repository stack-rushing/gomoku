from __future__ import annotations

import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

from server.config import HTTP_HOST, HTTP_PORT, WEB_DIR
from server.database import Database
from server.logger import logger
from server.room_manager import RoomManager
from server.tcp_server import TCPServer


def _make_handler(
    tcp_server: TCPServer,
    room_manager: RoomManager,
    database: Database,
):
    class AdminHandler(BaseHTTPRequestHandler):
        server_version = "GomokuAdmin/1.0"

        def log_message(self, format: str, *args) -> None:
            logger.debug(f"[HTTP] {self.address_string()} - {format % args}")

        def _send_json(self, status: int, data: dict) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, path: str) -> None:
            full_path = os.path.join(WEB_DIR, path.lstrip("/"))
            if not os.path.isfile(full_path):
                self.send_error(404, "File not found")
                return

            ext = os.path.splitext(full_path)[1].lower()
            mime_map = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".svg": "image/svg+xml",
                ".ico": "image/x-icon",
            }
            mime = mime_map.get(ext, "application/octet-stream")

            try:
                with open(full_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                logger.error(f"[HTTP] 读取静态文件失败 {full_path}: {e}")
                self.send_error(500, "Internal error")

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/" or path == "":
                self._send_static("index.html")
                return

            if path.startswith("/api/"):
                self._handle_api(path)
                return

            self._send_static(path)

        def _handle_api(self, path: str) -> None:
            if path == "/api/status":
                self._api_status()
            elif path == "/api/rooms":
                self._api_rooms()
            elif path == "/api/players":
                self._api_players()
            elif path == "/api/stats":
                self._api_stats()
            elif path == "/api/recent":
                self._api_recent()
            else:
                self._send_json(404, {"error": "Not found", "path": path})

        def _api_status(self) -> None:
            uptime = tcp_server.get_uptime()
            days = int(uptime // 86400)
            hours = int((uptime % 86400) // 3600)
            minutes = int((uptime % 3600) // 60)
            seconds = int(uptime % 60)

            self._send_json(
                200,
                {
                    "status": "running",
                    "tcp_host": tcp_server.host,
                    "tcp_port": tcp_server.port,
                    "sessions": tcp_server.get_session_count(),
                    "rooms": room_manager.get_room_count(),
                    "active_games": room_manager.get_active_game_count(),
                    "total_history": database.get_game_count(),
                    "uptime_seconds": int(uptime),
                    "uptime_text": f"{days}天{hours}时{minutes}分{seconds}秒",
                },
            )

        def _api_rooms(self) -> None:
            rooms = room_manager.list_rooms()
            room_list = []
            for room in rooms:
                players = []
                for sid, p in room.players.items():
                    players.append(
                        {
                            "sid": sid,
                            "name": p.player_name,
                            "side": "black" if p.side == 1 else "white",
                            "connected": p.connected,
                        }
                    )
                result_state = "ongoing"
                if room.game_ended:
                    result_state = room.result or "ended"
                elif not room.game_started:
                    result_state = "waiting"

                room_list.append(
                    {
                        "room_id": room.room_id,
                        "players": players,
                        "player_count": len(room.players),
                        "game_started": room.game_started,
                        "game_ended": room.game_ended,
                        "state": result_state,
                        "moves": len(room.game.move_history),
                        "current_player": room.game.get_current_player_str(),
                        "created_at": int(room.created_at),
                    }
                )
            self._send_json(200, {"rooms": room_list, "count": len(room_list)})

        def _api_players(self) -> None:
            total_players = room_manager.get_total_players()
            player_list = []
            for room in room_manager.list_rooms():
                for sid, p in room.players.items():
                    player_list.append(
                        {
                            "sid": sid,
                            "name": p.player_name,
                            "room_id": room.room_id,
                            "side": "black" if p.side == 1 else "white",
                            "addr": p.addr[0] if p.addr else "",
                            "port": p.addr[1] if p.addr else 0,
                            "connected": p.connected,
                            "last_ping": int(p.last_ping),
                        }
                    )
            self._send_json(
                200,
                {"players": player_list, "total": total_players, "sessions": tcp_server.get_session_count()},
            )

        def _api_stats(self) -> None:
            stats = database.get_statistics()
            self._send_json(200, stats)

        def _api_recent(self) -> None:
            games = database.get_recent_games(30)
            for g in games:
                if "moves" in g:
                    g["move_count"] = len(g["moves"]) if isinstance(g["moves"], list) else 0
            self._send_json(200, {"games": games, "count": len(games)})

    return AdminHandler


class HTTPServer:
    def __init__(
        self,
        tcp_server: TCPServer,
        room_manager: RoomManager,
        database: Database,
        host: str = HTTP_HOST,
        port: int = HTTP_PORT,
    ) -> None:
        self.tcp_server = tcp_server
        self.room_manager = room_manager
        self.database = database
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        try:
            handler_cls = _make_handler(self.tcp_server, self.room_manager, self.database)
            self._server = ThreadingHTTPServer((self.host, self.port), handler_cls)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            logger.info(f"[HTTP] 管理服务启动: http://{self.host}:{self.port}")
        except OSError as e:
            logger.error(f"[HTTP] 启动失败 (端口{self.port}可能已被占用): {e}")
            raise

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            try:
                self._server.server_close()
            except Exception:
                pass

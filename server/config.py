from __future__ import annotations

import os

SERVER_HOST = os.environ.get("GOMOKU_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("GOMOKU_SERVER_PORT", "8888"))

HTTP_HOST = os.environ.get("GOMOKU_HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("GOMOKU_HTTP_PORT", "8080"))

BOARD_SIZE = int(os.environ.get("GOMOKU_BOARD_SIZE", "15"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
WEB_DIR = os.path.join(BASE_DIR, "web")

DB_PATH = os.path.join(DATA_DIR, "gomoku.db")
LOG_FILE = os.path.join(LOG_DIR, "server.log")

MAX_PLAYERS_PER_ROOM = 2
PING_INTERVAL = 30
PING_TIMEOUT = 60
EMPTY_ROOM_TTL = 300

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

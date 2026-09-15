from __future__ import annotations

import os
import signal
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from server.config import (
    HTTP_HOST,
    HTTP_PORT,
    SERVER_HOST,
    SERVER_PORT,
)
from server.database import Database
from server.http_server import HTTPServer
from server.logger import logger
from server.room_manager import RoomManager
from server.tcp_server import TCPServer


def main() -> int:
    logger.info("=" * 50)
    logger.info("五子棋联机服务器 启动中...")
    logger.info("=" * 50)

    try:
        database = Database()
    except Exception as e:
        logger.critical(f"数据库初始化失败: {e}")
        return 1

    room_manager = RoomManager()

    tcp_server = TCPServer(
        room_manager=room_manager,
        database=database,
        host=SERVER_HOST,
        port=SERVER_PORT,
    )
    try:
        tcp_server.start()
    except Exception as e:
        logger.critical(f"TCP 服务器启动失败 (端口 {SERVER_PORT}): {e}")
        return 1

    http_server = HTTPServer(
        tcp_server=tcp_server,
        room_manager=room_manager,
        database=database,
        host=HTTP_HOST,
        port=HTTP_PORT,
    )
    try:
        http_server.start()
    except Exception as e:
        logger.warning(f"HTTP 管理服务启动失败 (端口 {HTTP_PORT}): {e}")

    logger.info("服务器启动完成")
    logger.info(f"  TCP 监听: {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"  HTTP 管理: http://{HTTP_HOST}:{HTTP_PORT}")

    running = True

    def _signal_handler(signum, frame):
        nonlocal running
        logger.info(f"收到信号 {signum}，正在关闭...")
        running = False

    try:
        signal.signal(signal.SIGINT, _signal_handler)
    except Exception:
        pass
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        pass

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("键盘中断，正在关闭...")

    logger.info("正在关闭 TCP 服务器...")
    tcp_server.stop()
    logger.info("正在关闭 HTTP 服务...")
    http_server.stop()
    logger.info("服务器已关闭")
    return 0


if __name__ == "__main__":
    sys.exit(main())

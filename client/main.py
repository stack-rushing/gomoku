from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import tkinter as tk
from tkinter import messagebox

from client.network import NetworkClient
from client.ui import GomokuClientUI


def main() -> int:
    try:
        root = tk.Tk()
    except Exception as e:
        print(f"初始化 Tk 失败: {e}", file=sys.stderr)
        return 1

    network = NetworkClient()
    ui = GomokuClientUI(root, network)

    def _on_quit():
        try:
            network.disconnect()
        except Exception:
            pass

    ui.set_on_quit(_on_quit)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            network.disconnect()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

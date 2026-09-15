# 五子棋 (Gomoku)

一款基于 Python + Tkinter + 原生 TCP Socket 的 Windows 桌面五子棋游戏。
支持联机双人对战和本地 AI 对战，以及多房间、断线检测、胜负/和棋判定、SQLite 对局记录、HTTP 管理页面和 PyInstaller 打包。

---

## 一、项目简介

本项目同时提供联机与本地 AI 两种五子棋对战方式：

- **客户端**：Windows 原生桌面应用，使用 Tkinter + Canvas 绘制棋盘，支持鼠标点击落子。
- **服务器**：Python 原生 TCP Socket 多线程服务器，负责房间管理、落子验证、胜负判定、SQLite 存盘。
- **HTTP 管理服务**：内置 8080 端口管理页面，查看房间、玩家、历史对局、服务器运行状态。
- **本地 AI**：无需启动服务器，可选择执黑或执白；AI 会优先完成五连、阻止对方五连，并根据活四、活三等局面威胁选择落子位置。

## 二、项目功能

| 功能 | 说明 |
| --- | --- |
| 对战方式选择 | 客户端可选择联机双人对战或本地 AI 对战 |
| 房间号匹配 | 输入相同房间号进入同一房间 |
| 黑先白后 | 第一名玩家自动执黑，第二名执白 |
| 房间满员限制 | 每间房最多 2 人，第三人会收到 room_full |
| 多房间同时运行 | 可同时进行若干局互不同步的游戏 |
| 服务器权威判定 | 落子合法性 / 胜负 / 和棋全部由服务器判定 |
| 实时同步 | 任意一方落子后，通过服务器广播到双方 |
| 胜负判断 | 横、竖、主副对角线 4 方向五子连珠 |
| 和棋判断 | 棋盘 225 格全部填满无人胜利即和棋 |
| 重新开始 | 联机模式需双方确认；AI 模式立即在本地重置，并保留玩家执黑/执白选择 |
| AI 对战 | 无需服务器；支持玩家执黑或执白，AI 自动响应落子 |
| 断线检测 | 基于心跳 + Socket 断开事件检测 |
| 对手离开提示 | 对手断线/退出房间时弹窗提示 |
| SQLite 存盘 | 保存对局、玩家、开始/结束时间、落子序列 |
| HTTP 管理 | 浏览器访问 `http://服务器IP:8080/` 查看全部状态 |
| PyInstaller 打包 | 一键打包成两个 EXE：客户端 + 服务器 |

## 三、技术栈

- **语言**：Python 3.9+
- **GUI**：Tkinter（标准库自带，无需额外安装）
- **网络**：`socket` + `threading`（原生 TCP，无 WebSocket）
- **消息协议**：JSON + `\n` 换行符分隔（每条消息末尾一个换行）
- **数据库**：`sqlite3`（标准库）
- **日志**：`logging` + RotatingFileHandler
- **HTTP 服务**：`http.server.ThreadingHTTPServer`（标准库）
- **打包**：PyInstaller
- **测试**：`unittest`

## 四、项目架构

整体架构为 C/S 三层：

```
[客户端 Tk UI]  <--->  [client/network TCP]  <--+
                                                 |
                                            服务器 TCP 8888
                                                 |
[服务器 TCP] -> [RoomManager] -> [Game 游戏规则] -> [Database SQLite]
    |
    +---> [HTTP 8080 管理页面]

[客户端 Tk UI]  <--->  [client/ai 本地 AI]  <--->  [Game 游戏规则]
```

关键解耦点：

- **Game 层完全独立**：纯逻辑类，不依赖 Socket、Tk、SQL，可单独测试。
- **RoomManager 层**：仅管理房间 / 玩家、线程安全、广播消息。
- **TCPServer 层**：处理连接、粘包、转发消息。
- **GUI 层**：只通过 Queue 读取网络消息，不直接阻塞 recv。
- **网络线程**：只把消息推入 Queue，不直接改 Tk 控件。

## 五、项目目录结构

```
Gomoku/
├── client/                     # 客户端模块
│   ├── __init__.py
│   ├── main.py                 # 客户端入口：初始化 Tk、网络、UI
│   ├── ui.py                   # Tkinter GUI：登录界面 + 游戏界面
│   ├── ai.py                   # 本地 AI 落子策略：胜负判断、威胁评分、候选点选择
│   ├── board.py                # Canvas 棋盘绘制、鼠标点击、坐标换算
│   ├── network.py              # TCP 客户端 + 消息队列 + 粘包处理
│   ├── config.py               # 客户端常量（颜色、棋盘尺寸、默认 IP）
│   └── resources/
│       └── icon.ico            # （可选）客户端图标
├── server/                     # 服务器模块
│   ├── __init__.py
│   ├── main.py                 # 服务器入口：初始化全部模块并阻塞
│   ├── tcp_server.py           # TCP Server：连接管理、消息路由、鉴权
│   ├── room_manager.py         # 房间管理：创建/加入/离开/广播
│   ├── game.py                 # 纯五子棋游戏逻辑（无副作用，可测）
│   ├── database.py             # SQLite 封装：对局/胜负/落子记录
│   ├── http_server.py          # HTTP 管理服务：/api/* 与静态页面
│   ├── config.py               # 服务器配置（端口、路径、心跳间隔）
│   └── logger.py               # 日志封装（控制台 + logs/server.log）
├── common/                     # 客户端、服务器共用模块
│   ├── __init__.py
│   ├── protocol.py             # JSON 编解码 + TCP 粘包 MessageBuffer
│   ├── constants.py            # 全局常量（玩家方、消息类型、错误码）
│   └── utils.py                # 通用工具（房间号/时间戳/格式校验）
├── web/                        # HTTP 管理前端静态资源
│   ├── index.html              # 管理面板结构
│   ├── style.css               # 深色主题样式
│   └── app.js                  # 轮询 /api 并动态渲染
├── tests/                      # 单元 & 集成测试
│   ├── __init__.py
│   ├── test_game.py            # 纯游戏规则（14+ 用例）
│   ├── test_ai.py              # AI 直接获胜、阻止对手获胜、威胁延伸测试
│   ├── test_protocol.py        # 协议编解码 & 粘包拆包（15+ 用例）
│   ├── test_room.py            # 房间管理 & 线程安全（15+ 用例）
│   └── test_server.py          # TCP 端到端集成（8+ 用例）
├── build/                      # PyInstaller 打包脚本（双击 .bat）
│   ├── build_client.bat
│   └── build_server.bat
├── data/                       # SQLite 数据目录
│   └── .gitkeep
├── logs/                       # 日志目录
│   └── .gitkeep
├── requirements.txt
├── README.md
└── .gitignore
```

## 六、每个文件的作用

### 6.1 common（共用）

| 文件 | 作用 |
| --- | --- |
| `common/constants.py` | 统一常量：`BLACK/WHITE`、消息类型、错误码、胜负结果字符串 |
| `common/protocol.py` | `encode_message/decode_message`、`MessageBuffer`（处理粘包/拆包）、各类消息的 builder 函数 |
| `common/utils.py` | 时间戳、房间号生成/校验、坐标合法校验、数字转换等 |

### 6.2 server（服务器）

| 文件 | 作用 |
| --- | --- |
| `server/main.py` | 入口，组装 `Database + RoomManager + TCPServer + HTTPServer` 并阻塞等待信号 |
| `server/tcp_server.py` | `TCPServer`（accept 循环）+ `ClientHandler`（每个连接单独线程处理 recv + 路由） |
| `server/room_manager.py` | `Room` 数据类 + `RoomManager`：多房间 + `RLock` 线程安全 + 广播/重开投票 |
| `server/game.py` | `GomokuGame`：15×15 棋盘、落子、四方向胜负检查、和棋、重置、历史记录 |
| `server/database.py` | `Database` 单例：`create_game/end_game/get_game_count/get_recent/get_statistics` |
| `server/http_server.py` | `HTTPServer` + `AdminHandler`，提供 `/api/status|rooms|players|stats|recent` 并托管 `web/` 静态资源 |
| `server/config.py` | 默认端口、数据路径、心跳/空房间过期等 |
| `server/logger.py` | `ServerLogger` 单例：控制台 INFO + 文件 DEBUG 滚动 |

### 6.3 client（客户端）

| 文件 | 作用 |
| --- | --- |
| `client/main.py` | 入口：组装 NetworkClient + UI，`root.mainloop()` |
| `client/ui.py` | `GomokuClientUI`：选择联机或 AI 对战；负责登录、棋盘、AI 回合调度与联机消息轮询 |
| `client/ai.py` | `GomokuAI`：优先赢棋和防守，并结合连子数、开放端和中心位置评估候选落子 |
| `client/board.py` | `GomokuBoard`（继承 Canvas）：绘制棋盘/棋子/最后一步红框/鼠标悬停效果 |
| `client/network.py` | `NetworkClient`：TCP 连接、独立 recv 线程、ping 线程、消息队列、事件队列 |
| `client/config.py` | 棋盘颜色、尺寸、默认服务器地址等 |

## 七、Python 环境要求

- Python **3.9 及以上**（使用了 `from __future__ import annotations` 和类型提示）
- Tkinter：Windows 官方安装包默认自带。
- 无强制第三方依赖（仅打包时需要 PyInstaller）。

## 八、安装方法

```cmd
cd Gomoku
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

如果不打包，只需要有 Python 标准库即可运行（`pip install -r requirements.txt` 可跳过）。

## 九、服务器启动方法

### 9.1 源码启动

```cmd
cd Gomoku
python -m server.main
```

启动后你会看到：

```
[TCP] 服务器启动: 0.0.0.0:8888
[HTTP] 管理服务启动: http://0.0.0.0:8080
```

默认端口：
- 游戏 TCP：`8888`
- 管理 HTTP：`8080`

### 9.2 自定义端口（环境变量）

```cmd
set GOMOKU_SERVER_HOST=0.0.0.0
set GOMOKU_SERVER_PORT=9999
set GOMOKU_HTTP_PORT=9090
python -m server.main
```

### 9.3 EXE 启动（打包后）

双击 `dist\GomokuServer.exe` 即可（会打开黑底控制台窗口显示日志）。

## 十、客户端启动方法

### 10.1 源码启动

```cmd
cd Gomoku
python -m client.main
```

### 10.2 EXE 启动（打包后）

双击 `dist\Gomoku.exe` 即可（无黑底控制台）。

### 10.3 AI 对战

AI 对战不需要启动服务器：

1. 启动客户端并填写玩家名称。
2. 在「对战方式」中选择「AI 对战」。
3. 在「AI 角色」中选择「我执黑」或「我执白」。
4. 点击「开始 AI 对战」。
5. 玩家执黑时先手；玩家执白时，AI 会先落黑子。
6. 对局结束后点击「重新开始」会立即开始下一局，并保留所选执子方。

AI 当前采用局面评分策略：优先完成五连、阻止对手五连，并评估活四、冲四、活三等连续棋形。该模式的棋局仅在客户端本地运行，不会写入服务器 SQLite 历史记录。

## 十一、房间匹配方法

1. 启动服务器。
2. 两个客户端分别打开。
3. 两个客户端的「服务器地址」和「端口」都填同一个服务器地址。
4. 两个客户端的「房间号」填**完全相同**的字符串（比如 `123456`）。
5. 第一个点击「加入房间」的玩家自动执黑，第二个执白。
6. 两人都加入后服务器广播 `game_start`，游戏正式开始。

## 十二、局域网联机方法

假设服务器电脑 IP 为 `192.168.1.100`：

1. **服务器端**：启动 `GomokuServer.exe` 或 `python -m server.main`。
2. **Windows 防火墙提示**：勾选「专用网络（家庭或工作网络）」并允许访问。
   - 如不小心关闭，去「控制面板 → Windows Defender 防火墙 → 允许应用通过防火墙」，勾选 `python.exe` 或 `GomokuServer.exe`。
3. **客户端 A / B**：
   - 服务器地址：`192.168.1.100`
   - 端口：`8888`
   - 玩家名：自定义
   - 房间号：`123456`（两个客户端保持一致）
4. 加入后即可联机对战。

## 十三、互联网联机方法

采用经典 **中转服务器模式**（Client → Server → Client），**不能**两个客户端直连。

### 方案 A：VPS 部署

1. 买一台公网 VPS（阿里云 / 腾讯云 / 搬瓦工等均可），系统选 Windows。
2. 上传 `GomokuServer.exe`，启动。
3. 开放 **TCP 8888**（游戏端口）和 **TCP 8080**（管理页面）：
   - VPS 后台「安全组/防火墙」放行入站端口。
   - VPS 内部的 Windows 防火墙也放行（同局域网步骤）。
4. 客户端填 VPS 的公网 IP 即可联机。

### 方案 B：内网穿透（家用电脑做服务器）

使用 FRP / ngrok / 花生壳等把本地 `8888` 和 `8080` 映射到公网即可。

## 十四、TCP 通信协议

全部消息为 UTF-8 JSON 对象，末尾必须跟一个换行符 `\n`。一次 `send()` 可以发送多条，一次 `recv()` 也可能收到半条或多条。

### 14.1 典型消息一览

| 方向 | type | 关键字段 | 说明 |
| --- | --- | --- | --- |
| C→S | `join_room` | `room_id`, `player_name` | 加入房间 |
| S→C | `room_joined` | `room_id`, `player` (`black\|white`) | 加入成功 |
| S→C | `room_full` | — | 房间已满 |
| S→C | `game_start` | `black`, `white`, `current_player` | 双方到齐，游戏开始 |
| C→S | `move` | `row`, `col` | 请求落子 |
| S→C | `move_result` | `row`, `col`, `player`, `next_player` | 落子成功并广播 |
| S→C | `invalid_move` | `reason` | 拒绝落子原因 |
| S→C | `game_over` | `winner` | 有玩家胜利 |
| S→C | `draw` | — | 和棋 |
| C→S | `restart_request` | — | 申请重新开始 |
| S→C | `restart_response` | `agreed` | 已记录申请 |
| S→C | `game_restart` | — | 双方都同意，重置棋盘 |
| S→C | `player_left` | — | 对手离开/断线 |
| S→C / C→S | `ping` / `pong` | — | 心跳保活 |
| S→C | `error` | `message`, `code`? | 通用错误 |

### 14.2 粘包 / 拆包解决方案

`common/protocol.py` 中 `MessageBuffer` 的做法：

1. 内部维护字符串缓冲区。
2. 每次 `recv(bytes)` 追加到缓冲区。
3. 用 `\n` 切割字符串，最后一段留作下次拼接。
4. 逐段 `json.loads`：成功则加入消息列表，失败则加入失败行集合。

保证无论 TCP 如何分片都能正确还原 JSON 消息序列。

## 十五、五子棋胜负判断算法

`server/game.py → GomokuGame._check_win`：

- 枚举 **4 个方向**：横向 `(0,1)`、纵向 `(1,0)`、主对角线 `(1,1)`、副对角线 `(1,-1)`。
- 对每个方向：
  - 沿正方向 `(dr, dc)` 统计连续同色棋子数；
  - 沿反方向 `(-dr, -dc)` 统计连续同色棋子数；
  - 加上当前棋子本身共 `1 + 两边`。
- 任一方向总数 ≥ 5 即胜利。

这种算法比「只扫描 5 格固定窗口」更稳健，天然支持 6 连/7 连等场景。

和棋判定：遍历 15×15 棋盘，不存在空格且无人胜利即和棋。

## 十六、多线程设计

- **服务器端**：
  - 主线程：启动后阻塞等待信号。
  - TCP Accept 线程：`ThreadingHTTPServer` 的 accept 循环。
  - 每个客户端一条 `ClientHandler.run` 线程，处理 `recv + 路由`。
  - `RoomManager` 使用 `threading.RLock()` 保护共享字典，避免并发加房间/加玩家时数据损坏。
  - HTTP 管理服务用 `ThreadingHTTPServer`，每个请求一条线程。
- **客户端端**：
  - Tk 主线程：绘制界面、处理鼠标点击、`root.after(50ms)` 轮询两个 `queue.Queue`。
  - 网络线程 1：`_recv_loop` 阻塞 `recv`，把消息放入 `message_queue`。
  - 网络线程 2：`_ping_loop` 每 20 秒发一次 `ping`。
  - **严禁**网络线程直接调用 `canvas.create_oval` / `label.config`，一律通过 Queue 中转。

## 十七、SQLite 数据库设计

文件位置：`data/gomoku.db`（服务器首次启动自动创建）。

表 `games`：

| 列名 | 类型 | 说明 |
| --- | --- | --- |
| id | INTEGER PK | 对局 ID，自增 |
| room_id | TEXT | 房间号 |
| black_name | TEXT | 黑方玩家名 |
| white_name | TEXT | 白方玩家名 |
| start_time | REAL | 开始时间（Unix 秒） |
| end_time | REAL\|NULL | 结束时间（未结束为 NULL） |
| winner | TEXT\|NULL | `black` / `white` / `none` |
| result | TEXT | `ongoing` / `win_black` / `win_white` / `draw` |
| moves | TEXT | 落子 JSON：`[{"player":"black","row":7,"col":7}, ...]` |
| move_count | INTEGER | 落子数（冗余列，便于排序） |

提供的查询 API（`server/database.py`）：

- `create_game(room_id, black_name, white_name) -> game_id`
- `end_game(game_id, result, winner, moves)`
- `get_game_count() -> int`
- `get_game_by_id(id) -> dict`
- `get_recent_games(limit=20) -> list`
- `get_statistics() -> {total_games, black_wins, white_wins, draws, total_moves}`

## 十八、HTTP 管理页面

浏览器访问 `http://服务器IP:8080/`。

### 18.1 REST API

| 方法 | URL | 返回 |
| --- | --- | --- |
| GET | `/` | `web/index.html` 页面 |
| GET | `/style.css` `/app.js` | 静态资源 |
| GET | `/api/status` | 服务器状态、TCP/HTTP 端口、运行时长、会话数、房间数、历史对局数 |
| GET | `/api/rooms` | 全部房间详情（房间号、玩家列表、状态、落子数） |
| GET | `/api/players` | 全部在线玩家（名称、房间、执方、IP、是否在线） |
| GET | `/api/stats` | 黑胜数、白胜数、和棋数、总局数、总落子数 |
| GET | `/api/recent` | 最近 30 局列表（表格展示） |

管理页每 3 秒自动刷新一次。

## 十九、测试方法

使用 `unittest`：

```cmd
cd Gomoku
python -m unittest discover -s tests -v
```

或单独跑某个文件：

```cmd
python -m unittest tests.test_game -v
python -m unittest tests.test_protocol -v
python -m unittest tests.test_room -v
python -m unittest tests.test_server -v
```

测试覆盖点：

- `test_game.py`：正常落子、越界、重复、黑白交替、四方向胜负、和棋、结束后禁手、重开、历史记录（19+ 用例）。
- `test_protocol.py`：JSON 编解码、单/多条消息、TCP 粘包、TCP 拆包、半条消息、空消息、非法 JSON、Unicode（20+ 用例）。
- `test_room.py`：创建/加入/满员/踢出/查找/活跃游戏计数/重开投票 + 8 线程并发压力（15+ 用例）。
- `test_server.py`：真实起 TCP 端口，双客户端加入、开始、同步落子、非法落子、第三人被拒、胜利、断线通知、双权重开（8+ 端到端）。

## 二十、PyInstaller 打包方法

### 20.1 一键脚本（推荐）

在项目根目录下：

```cmd
build\build_client.bat
build\build_server.bat
```

脚本会：
1. 自动检测并安装 PyInstaller。
2. `--add-data common;common` 把 common 模块打包进 EXE（避免 ImportError）。
3. 客户端 `--windowed`（无黑底控制台），服务器保持控制台。
4. 产物分别为 `dist/Gomoku.exe` 与 `dist/GomokuServer.exe`。

### 20.2 手动打包

```cmd
:: 客户端
pyinstaller --onefile --windowed --name Gomoku ^
    --add-data "common;common" ^
    --add-data "client;client" ^
    client/main.py

:: 服务器
pyinstaller --onefile --name GomokuServer ^
    --add-data "common;common" ^
    --add-data "server;server" ^
    --add-data "web;web" ^
    server/main.py
```

> 注：Windows 下 PyInstaller 的 `--add-data` 分隔符是 **分号 `;`**，Linux/macOS 是冒号 `:`。

## 二十一、EXE 使用方法

### 服务器

1. 把 `GomokuServer.exe` 放到任意目录。
2. 在 exe 同级目录手动建两个子文件夹：
   ```
   某目录/
   ├── GomokuServer.exe
   ├── data/          (自动生成 gomoku.db)
   └── logs/          (自动生成 server.log)
   ```
   如果不手动创建，脚本中已使用 `os.makedirs(..., exist_ok=True)` 自动创建。
3. 双击 exe。
4. 管理页面浏览器访问 `http://本机IP:8080/`。

### 客户端

1. 把 `Gomoku.exe` 发给两个玩家。
2. 打开后填写服务器 IP / 端口 / 昵称 / 房间号。
3. 加入即可开玩。

## 二十二、Windows 防火墙设置

TCP 8888 和 TCP 8080 必须放行，否则别人连不上。

**方法 A（首次启动时）**：Windows 会弹出「是否允许此应用通过防火墙」：
- 勾选「专用网络（家庭或工作网络）」（局域网用）。
- 如果是 VPS 或公网，再勾选「公用网络」。
- 点「允许访问」。

**方法 B（漏掉了 A）**：

1. Win + R → 输入 `wf.msc` 回车，打开「高级安全 Windows Defender 防火墙」。
2. 左侧「入站规则」→ 右侧「新建规则」。
3. 规则类型选 **端口** → TCP → 特定本地端口：`8888, 8080` → 允许连接 → 全选 3 个场景 → 命名为 `Gomoku Server`。
4. 同样方法给 `python.exe` 或 `GomokuServer.exe` 新建「程序入站规则」（可选）。

## 二十三、常见问题

### Q1：客户端提示「无法连接服务器」

1. 确认服务器已启动、没被关闭。
2. 防火墙是否放行。
3. `服务器地址` 填写正确：本机测试用 `127.0.0.1`，局域网用对方 IPv4，公网用 VPS IP。
4. 使用 `telnet 服务器IP 8888` 或 PowerShell `Test-NetConnection 服务器IP -Port 8888` 验证端口是否通。

### Q2：两个客户端加入同一个房间号却不一起开始

检查房间号是否完全一致（大小写 / 前后空格），以及双方是否连到同一个服务器 IP。

### Q3：EXE 双击一闪而过

服务器 EXE 可以先开 `cmd` 进入目录再运行：
```cmd
GomokuServer.exe
```
查看报错。客户端可以临时改 `build_client.bat` 去掉 `--windowed` 复现黑底排查。

### Q4：ImportError: No module named 'common'

原因是没有在项目根目录启动。请 `cd Gomoku` 后再 `python -m client.main`。PyInstaller 脚本已使用 `--add-data` 规避此问题。

### Q5：测试 `test_server.py` 报端口被占用

说明前一次测试进程没退出。手动把占用 `18888` 的 Python 进程杀掉，或在任务管理器结束 python.exe。

### Q6：Windows 家庭中文版 / 单语言版本缺少 Tkinter？

官方 Python 安装包（python.org 下载）默认都带 Tkinter，若真没有就重新安装并确保勾选 "Tcl/Tk and IDLE"。

### Q7：客户端启动时 `RuntimeError: Too early to create image`

请确保 `root = tk.Tk()` 放在**最前**、任何 Canvas / PhotoImage 创建之后再执行。本项目代码已正确排序，如自行改动请留意。

---

## 二十四、最终运行流程回顾

1. 选择「AI 对战」时，客户端本地创建棋局；AI 执白或执黑并自动响应，棋局结束后可立即重开。
2. 选择「联机对战」时，运行服务器（TCP 监听 8888，HTTP 监听 8080）。
3. 两个客户端填写服务器地址、端口、昵称、相同房间号，点「加入房间」。
4. 第一个玩家拿到 `black`，第二个玩家拿到 `white`，服务器广播 `game_start`。
5. 任何一方点击棋盘，客户端发送 `{"type":"move","row":x,"col":y}` 到服务器。
6. 服务器检查：在房间？已开始？自己回合？坐标合法？空位置？→ 拒绝返回 `invalid_move`。
7. 合法则服务器落子 → 判断胜负/和棋 → 切换回合 → 广播 `move_result` 给两个客户端。
8. 若胜负决出：服务器广播 `game_over/draw`，并写入 SQLite（结束时间、胜者、完整 moves）。
9. 联机模式下双方可随时点「重新开始」，服务器累计 2 票后重置棋盘并广播 `game_restart` + `game_start`。
10. 任一客户端断开，服务器从 Socket 读到 EOF，清理玩家并向对方广播 `player_left`，同时把未结束对局记为「对方胜」。
11. 管理面板每 3 秒刷新一次，管理员能看到全部房间/玩家/对局统计。

---
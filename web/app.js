(function () {
    "use strict";

    const API_BASE = "/api";

    function formatTime(ts) {
        if (!ts) return "-";
        const d = new Date(ts * 1000);
        const pad = (n) => String(n).padStart(2, "0");
        return (
            d.getFullYear() +
            "-" + pad(d.getMonth() + 1) +
            "-" + pad(d.getDate()) +
            " " + pad(d.getHours()) +
            ":" + pad(d.getMinutes()) +
            ":" + pad(d.getSeconds())
        );
    }

    function resultText(r) {
        if (!r) return "进行中";
        if (r === "ongoing") return "进行中";
        if (r === "win_black") return "黑方胜";
        if (r === "win_white") return "白方胜";
        if (r === "draw") return "和棋";
        if (r === "ended") return "已结束";
        return r;
    }

    function resultClass(r) {
        if (!r) return "result-ongoing";
        if (r.startsWith("win_") || r === "draw") return "result-" + r;
        return "result-ongoing";
    }

    function $(id) { return document.getElementById(id); }

    async function getJSON(url) {
        const resp = await fetch(url, { method: "GET", cache: "no-store" });
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        return await resp.json();
    }

    async function loadStatus() {
        const data = await getJSON(API_BASE + "/status");
        $("statusValue").textContent = data.status === "running" ? "运行中" : data.status;
        $("tcpAddr").textContent = (data.tcp_host || "") + ":" + (data.tcp_port || "");
        $("sessionsCount").textContent = data.sessions || 0;
        $("roomsCount").textContent = data.rooms || 0;
        $("activeGames").textContent = data.active_games || 0;
        $("historyCount").textContent = data.total_history || 0;
        $("uptimeText").textContent = data.uptime_text || "-";
    }

    async function loadStats() {
        const data = await getJSON(API_BASE + "/stats");
        $("blackWins").textContent = data.black_wins || 0;
        $("whiteWins").textContent = data.white_wins || 0;
        $("draws").textContent = data.draws || 0;
        $("totalGames").textContent = data.total_games || 0;
        $("totalMoves").textContent = data.total_moves || 0;
    }

    async function loadRooms() {
        const data = await getJSON(API_BASE + "/rooms");
        const list = $("roomsList");
        const badge = $("roomsBadge");
        const rooms = data.rooms || [];
        badge.textContent = rooms.length;

        if (rooms.length === 0) {
            list.innerHTML = '<p class="empty">暂无房间</p>';
            return;
        }

        const html = rooms.map(function (r) {
            const players = (r.players || []).map(function (p) {
                return (
                    '<span class="player-chip side-' + p.side + '">' +
                    '<span class="dot"></span>' +
                    (p.name || "匿名") +
                    (p.connected ? "" : "（离线）") +
                    "</span>"
                );
            }).join("");

            return (
                '<div class="room-item">' +
                    '<div class="room-top">' +
                        '<span class="room-id">' + r.room_id + '</span>' +
                        '<span class="state-tag ' + r.state + '">' + resultText(r.state) + '</span>' +
                    '</div>' +
                    '<div class="room-info">' +
                        '<span>玩家数：' + r.player_count + '/2</span>' +
                        '<span>落子数：' + (r.moves || 0) + '</span>' +
                    '</div>' +
                    (players ? '<div class="players-mini">' + players + '</div>' : "") +
                '</div>'
            );
        }).join("");
        list.innerHTML = html;
    }

    async function loadPlayers() {
        const data = await getJSON(API_BASE + "/players");
        const list = $("playersList");
        const badge = $("playersBadge");
        const players = data.players || [];
        badge.textContent = players.length;

        if (players.length === 0) {
            list.innerHTML = '<p class="empty">暂无玩家</p>';
            return;
        }

        const html = players.map(function (p) {
            const sideText = p.side === "black" ? "黑棋" : "白棋";
            return (
                '<div class="player-item">' +
                    '<div class="pi-left">' +
                        '<span class="pi-name">' + (p.name || "匿名") + '</span>' +
                        '<span class="pi-meta">房间: ' + (p.room_id || "-") +
                            ' | ' + sideText +
                            ' | ' + (p.addr || "-") + ':' + (p.port || "-") +
                        '</span>' +
                    '</div>' +
                    (p.connected ? "" : '<span class="state-tag ended">离线</span>') +
                '</div>'
            );
        }).join("");
        list.innerHTML = html;
    }

    async function loadRecent() {
        const data = await getJSON(API_BASE + "/recent");
        const tbody = $("gamesBody");
        const games = data.games || [];

        if (games.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">暂无对局记录</td></tr>';
            return;
        }

        const html = games.map(function (g) {
            return (
                "<tr>" +
                    "<td>" + g.id + "</td>" +
                    "<td>" + (g.room_id || "-") + "</td>" +
                    "<td>" + (g.black_name || "-") + "</td>" +
                    "<td>" + (g.white_name || "-") + "</td>" +
                    "<td>" + formatTime(g.start_time) + "</td>" +
                    "<td>" + (g.move_count || 0) + "</td>" +
                    '<td class="' + resultClass(g.result) + '">' + resultText(g.result) + "</td>" +
                "</tr>"
            );
        }).join("");
        tbody.innerHTML = html;
    }

    async function refreshAll() {
        try {
            await Promise.all([
                loadStatus(),
                loadStats(),
                loadRooms(),
                loadPlayers(),
                loadRecent(),
            ]);
            const now = new Date();
            $("lastUpdate").textContent = now.toLocaleString();
        } catch (err) {
            console.error(err);
            $("statusValue").textContent = "连接失败";
        }
    }

    refreshAll();
    setInterval(refreshAll, 3000);
})();

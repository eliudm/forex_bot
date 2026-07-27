from flask import Flask, jsonify, send_from_directory, request
import json, os, re, time
from datetime import datetime, date

app = Flask(__name__, static_folder='.')

LOG_DIR      = "logs"
STATE_FILE   = "logs/loss_detector_state.json"
SIGNAL_FILE  = "logs/latest_signals.json"
CONTROL_FILE = "logs/bot_control.json"


def read_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}


def bot_is_alive():
    """Check if bot wrote to log file in last 10 minutes."""
    today = date.today().strftime("%Y%m%d")
    log_file = os.path.join(LOG_DIR, f"bot_{today}.log")
    if os.path.exists(log_file):
        age = time.time() - os.path.getmtime(log_file)
        return age < 600
    # Also check if signals file was updated recently
    if os.path.exists(SIGNAL_FILE):
        age = time.time() - os.path.getmtime(SIGNAL_FILE)
        return age < 600
    return False


def read_signals():
    if os.path.exists(SIGNAL_FILE):
        try:
            with open(SIGNAL_FILE, encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}


@app.route("/api/status")
def api_status():
    state = read_state()
    alive = bot_is_alive()

    if state:
        status = state.get("status", "NORMAL")
        reason = state.get("status_reason", "Bot is running")
    elif alive:
        status = "NORMAL"
        reason = "Bot is running. Scanning markets every 5 minutes."
    else:
        status = "OFFLINE"
        reason = "Bot not detected. Run start_bot.bat to start it."

    return jsonify({
        "status":          status,
        "status_reason":   reason,
        "current_balance": state.get("current_balance", 10000),
        "peak_balance":    state.get("peak_balance",    10000),
        "loss_streak":     state.get("loss_streak", 0),
        "win_streak":      state.get("win_streak",  0),
        "retrain_needed":  state.get("retrain_needed", False),
        "saved_at":        state.get("saved_at", datetime.now().isoformat()),
    })


@app.route("/api/stats")
def api_stats():
    state  = read_state()
    trades = state.get("trade_history", [])
    today  = date.today().isoformat()
    today_trades = [t for t in trades if t.get("time", "").startswith(today)]
    wins      = [t for t in today_trades if t.get("profit", 0) > 0]
    losses    = [t for t in today_trades if t.get("profit", 0) <= 0]
    total_pnl = sum(t.get("profit", 0) for t in today_trades)
    balance   = state.get("current_balance", 10000)
    initial   = 10000
    ret_pct   = ((balance - initial) / initial * 100) if initial else 0
    return jsonify({
        "balance":      round(balance, 2),
        "total_pnl":    round(total_pnl, 2),
        "return_pct":   round(ret_pct, 2),
        "total_trades": len(today_trades),
        "wins":         len(wins),
        "losses":       len(losses),
        "win_rate":     round(len(wins) / len(today_trades) * 100, 1) if today_trades else 0,
        "open_trades":  0,
    })


@app.route("/api/signals")
def api_signals():
    return jsonify(read_signals())


@app.route("/api/equity")
def api_equity():
    state   = read_state()
    trades  = state.get("trade_history", [])
    balance = state.get("current_balance", 10000)
    start   = balance - sum(t.get("profit", 0) for t in trades[-50:])
    curve   = [{"t": "Start", "v": round(start, 2)}]
    running = start
    for i, t in enumerate(trades[-50:], 1):
        running += t.get("profit", 0)
        curve.append({"t": f"#{i}", "v": round(running, 2)})
    return jsonify(curve)


@app.route("/api/log")
def api_log():
    lines = []
    try:
        # Try today first, then yesterday
        for delta in [0, 1]:
            from datetime import timedelta
            d = (date.today() - timedelta(days=delta)).strftime("%Y%m%d")
            log_file = os.path.join(LOG_DIR, f"bot_{d}.log")
            if os.path.exists(log_file):
                with open(log_file, encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
                lines = [l.strip() for l in all_lines[-100:] if l.strip()]
                if lines:
                    break
        # Also add recent signals as log entries
        if os.path.exists(SIGNAL_FILE):
            import json as _json
            sigs = _json.load(open(SIGNAL_FILE, encoding="utf-8"))
            for sym, s in sigs.items():
                act = s.get("action", "WAIT")
                conf = s.get("confidence", 0)
                reg = s.get("regime", "")
                ts = s.get("timestamp", "")[:19] if s.get("timestamp") else ""
                lines.append(f"{ts} | {sym}: {act} (conf:{conf:.0%}) | {reg}")
    except Exception as e:
        lines = [f"Log error: {str(e)}"]
    return jsonify(lines[-100:])


@app.route("/api/control/start", methods=["POST"])
def ctrl_start():
    os.makedirs(LOG_DIR, exist_ok=True)
    ctrl = {}
    if os.path.exists(CONTROL_FILE):
        try:
            ctrl = json.load(open(CONTROL_FILE))
        except:
            pass
    ctrl["running"]    = True
    ctrl["updated_at"] = datetime.now().isoformat()
    json.dump(ctrl, open(CONTROL_FILE, "w"), indent=2)
    return jsonify({"ok": True})


@app.route("/api/control/stop", methods=["POST"])
def ctrl_stop():
    os.makedirs(LOG_DIR, exist_ok=True)
    ctrl = {}
    if os.path.exists(CONTROL_FILE):
        try:
            ctrl = json.load(open(CONTROL_FILE))
        except:
            pass
    ctrl["running"]    = False
    ctrl["updated_at"] = datetime.now().isoformat()
    json.dump(ctrl, open(CONTROL_FILE, "w"), indent=2)
    return jsonify({"ok": True})


@app.route("/api/control/mode", methods=["POST"])
def ctrl_mode():
    data = request.get_json() or {}
    mode = data.get("mode", "SEMI_AUTO")
    ctrl = {}
    if os.path.exists(CONTROL_FILE):
        try:
            ctrl = json.load(open(CONTROL_FILE))
        except:
            pass
    ctrl["mode"]       = mode
    ctrl["updated_at"] = datetime.now().isoformat()
    json.dump(ctrl, open(CONTROL_FILE, "w"), indent=2)
    settings = "config/settings.py"
    if os.path.exists(settings):
        s = open(settings, encoding="utf-8").read()
        s = re.sub(r'EXECUTION_MODE\s*=\s*[^\n]+', f'EXECUTION_MODE = "{mode}"', s)
        open(settings, "w", encoding="utf-8").write(s)
    return jsonify({"ok": True, "mode": mode})


@app.route("/api/control/status")
def ctrl_status():
    if os.path.exists(CONTROL_FILE):
        try:
            return jsonify(json.load(open(CONTROL_FILE)))
        except:
            pass
    return jsonify({"running": True, "mode": "FULL_AUTO"})


@app.route("/api/performance")
def api_performance():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from ai_engine.performance_tracker import PerformanceTracker
        tracker = PerformanceTracker()
        days    = int(request.args.get("days", 30))
        report  = tracker.get_report(days=days)
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e), "total_trades": 0})


@app.route("/report")
def report_page():
    return send_from_directory(".", "report.html")


@app.route("/")
def index():
    return send_from_directory(".", "dashboard2.html")


if __name__ == "__main__":
    print("")
    print("=" * 50)
    print("  Dashboard server running!")
    print("  Open browser at: http://localhost:5000")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    print("")
    app.run(host="0.0.0.0", port=5000, debug=False)

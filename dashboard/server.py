from flask import Flask, jsonify, send_from_directory, request
import json, os, re, time
from datetime import datetime, date

app = Flask(__name__, static_folder='.')

# Always resolve paths relative to the repo root, regardless of cwd
_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR      = os.path.join(_ROOT, "logs")
STATE_FILE   = os.path.join(_ROOT, "logs", "loss_detector_state.json")
SIGNAL_FILE  = os.path.join(_ROOT, "logs", "latest_signals.json")
CONTROL_FILE = os.path.join(_ROOT, "logs", "bot_control.json")


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

    # Use heartbeat timestamp (updated every scan) if available,
    # fall back to state file saved_at (only updates on trade close)
    heartbeat_file = os.path.join(LOG_DIR, "bot_heartbeat.json")
    last_updated = state.get("saved_at", datetime.now().isoformat())
    if os.path.exists(heartbeat_file):
        try:
            hb = json.load(open(heartbeat_file))
            last_updated = hb.get("last_scan", last_updated)
        except Exception:
            pass

    return jsonify({
        "status":          status,
        "status_reason":   reason,
        "current_balance": state.get("current_balance", 10000),
        "peak_balance":    state.get("peak_balance",    10000),
        "loss_streak":     state.get("loss_streak", 0),
        "win_streak":      state.get("win_streak",  0),
        "retrain_needed":  state.get("retrain_needed", False),
        "saved_at":        last_updated,
    })


def _count_open_trades():
    """Count open trades from live MT5 positions; fall back to tracker file."""
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            positions = mt5.positions_get()
            mt5.shutdown()
            if positions is not None:
                return len(positions)
    except Exception:
        pass
    # Fallback: read from performance tracker file
    tracker_file = os.path.join(_ROOT, "logs", "performance_tracker.json")
    try:
        if os.path.exists(tracker_file):
            with open(tracker_file, encoding="utf-8") as f:
                data = json.load(f)
            return len(data.get("open_trades", {}))
    except Exception:
        pass
    return 0


def _read_mt5_balance():
    """Try to get live balance from MT5; fall back to state file."""
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            acct = mt5.account_info()
            if acct:
                balance = acct.balance
                equity  = acct.equity
                mt5.shutdown()
                return balance, equity
            mt5.shutdown()
    except Exception:
        pass
    return None, None


@app.route("/api/stats")
def api_stats():
    state = read_state()
    today = date.today().isoformat()

    # Read closed trades from performance tracker (most accurate source —
    # updated whenever a trade closes regardless of whether bot was running)
    tracker_file = os.path.join(_ROOT, "logs", "performance_tracker.json")
    today_trades = []
    try:
        if os.path.exists(tracker_file):
            with open(tracker_file, encoding="utf-8") as f:
                tdata = json.load(f)
            history = tdata.get("history", [])
            today_trades = [
                t for t in history
                if t.get("close_time", t.get("time", "")).startswith(today)
            ]
    except Exception:
        pass

    # Fallback to loss detector state if tracker is empty
    if not today_trades:
        fallback = state.get("trade_history", [])
        today_trades = [t for t in fallback if t.get("time", "").startswith(today)]

    wins      = [t for t in today_trades if t.get("profit", 0) > 0]
    losses    = [t for t in today_trades if t.get("profit", 0) <= 0]
    total_pnl = sum(t.get("profit", 0) for t in today_trades)

    # Try live MT5 balance first, fall back to state file
    live_balance, live_equity = _read_mt5_balance()
    balance  = live_balance  if live_balance  is not None else state.get("current_balance", 10000)
    initial  = 10000
    ret_pct  = ((balance - initial) / initial * 100) if initial else 0

    return jsonify({
        "balance":      round(balance, 2),
        "equity":       round(live_equity, 2) if live_equity is not None else round(balance, 2),
        "total_pnl":    round(total_pnl, 2),
        "return_pct":   round(ret_pct, 2),
        "total_trades": len(today_trades),
        "wins":         len(wins),
        "losses":       len(losses),
        "win_rate":     round(len(wins) / len(today_trades) * 100, 1) if today_trades else 0,
        "open_trades":  _count_open_trades(),
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


def _trade_analytics(p, current_price, tracker_trades, mt5):
    """Compute health metrics for one open MT5 position."""
    direction  = "BUY" if p.type == 0 else "SELL"
    entry      = p.price_open
    sl         = p.sl
    tp         = p.tp
    profit     = p.profit

    # Pull original SL from tracker for accurate R calculation
    tracked     = tracker_trades.get(str(p.ticket), {})
    orig_sl     = tracked.get("sl", sl)
    orig_entry  = tracked.get("entry", entry)
    r_distance  = abs(orig_entry - orig_sl) if orig_sl and orig_entry else 0

    # R-multiple: how many R units is current profit worth
    r_multiple = round(profit / r_distance, 2) if r_distance > 0 else 0

    # Progress toward TP (0–100 %)
    if tp and r_distance > 0:
        tp_distance = abs(tp - orig_entry)
        if direction == "BUY":
            moved = current_price - orig_entry
        else:
            moved = orig_entry - current_price
        progress_pct = round(min(max(moved / tp_distance * 100, 0), 100), 1)
    else:
        progress_pct = 0

    # Distance remaining to SL as % of original SL distance
    if sl and r_distance > 0:
        if direction == "BUY":
            to_sl = current_price - sl
        else:
            to_sl = sl - current_price
        sl_buffer_pct = round(min(max(to_sl / r_distance * 100, 0), 200), 1)
    else:
        sl_buffer_pct = 100

    # Is SL at breakeven (entry)?
    be_set = (direction == "BUY"  and sl >= orig_entry * 0.9999) or \
             (direction == "SELL" and sl > 0 and sl <= orig_entry * 1.0001)

    # Health status
    if be_set and profit > 0:
        status = "PROTECTED"
        status_color = "blue"
    elif sl_buffer_pct <= 15:
        status = "DANGER"
        status_color = "red"
    elif sl_buffer_pct <= 40:
        status = "AT RISK"
        status_color = "yellow"
    elif profit > 0:
        status = "IN CONTROL"
        status_color = "green"
    else:
        status = "WATCH"
        status_color = "yellow"

    # Hold time
    open_dt   = datetime.fromtimestamp(p.time)
    held_min  = int((datetime.now() - open_dt).total_seconds() // 60)
    held_str  = f"{held_min // 60}h {held_min % 60}m" if held_min >= 60 else f"{held_min}m"

    # Expected profit at TP — use MT5's own calculator for exact $ value
    expected_tp_profit = None
    risk_amount        = None
    rr_ratio           = None
    try:
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        if tp:
            expected_tp_profit = mt5.order_calc_profit(order_type, p.symbol, p.volume, entry, tp)
            if expected_tp_profit is not None:
                expected_tp_profit = round(expected_tp_profit, 2)
        if orig_sl:
            risk_amount = mt5.order_calc_profit(order_type, p.symbol, p.volume, entry, orig_sl)
            if risk_amount is not None:
                risk_amount = round(abs(risk_amount), 2)
        if expected_tp_profit is not None and risk_amount and risk_amount > 0:
            rr_ratio = round(expected_tp_profit / risk_amount, 2)
    except Exception:
        pass

    # Remaining profit needed to reach TP
    remaining_to_tp = round(expected_tp_profit - profit, 2) if expected_tp_profit is not None else None

    return {
        "status":             status,
        "status_color":       status_color,
        "r_multiple":         r_multiple,
        "progress_pct":       progress_pct,
        "sl_buffer_pct":      sl_buffer_pct,
        "breakeven_set":      be_set,
        "held":               held_str,
        "confidence":         round(tracked.get("confidence", 0) * 100, 0),
        "strategy":           tracked.get("strategy", "—"),
        "expected_tp_profit": expected_tp_profit,
        "risk_amount":        risk_amount,
        "rr_ratio":           rr_ratio,
        "remaining_to_tp":    remaining_to_tp,
    }


@app.route("/api/positions")
def api_positions():
    """Live open positions with floating P&L and trade analytics from MT5."""
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return jsonify([])

        # Load tracker for R-distance and metadata
        tracker_trades = {}
        tracker_file = os.path.join(_ROOT, "logs", "performance_tracker.json")
        try:
            if os.path.exists(tracker_file):
                with open(tracker_file, encoding="utf-8") as f:
                    tracker_trades = json.load(f).get("open_trades", {})
        except Exception:
            pass

        positions = mt5.positions_get()
        result = []
        if positions:
            for p in positions:
                tick    = mt5.symbol_info_tick(p.symbol)
                current = tick.bid if p.type == 1 else tick.ask if tick else p.price_open
                analytics = _trade_analytics(p, current, tracker_trades, mt5)
                result.append({
                    "ticket":      p.ticket,
                    "symbol":      p.symbol,
                    "direction":   "BUY" if p.type == 0 else "SELL",
                    "lot":         p.volume,
                    "open_price":  p.price_open,
                    "current":     round(current, 5) if current else 0,
                    "sl":          p.sl,
                    "tp":          p.tp,
                    "profit":      round(p.profit, 2),
                    "swap":        round(p.swap, 2),
                    "open_time":   datetime.fromtimestamp(p.time).strftime("%H:%M %d/%m"),
                    "magic":       p.magic,
                    **analytics,
                })
        mt5.shutdown()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/positions/close", methods=["POST"])
def api_close_position():
    """Close a specific position by ticket."""
    try:
        import MetaTrader5 as mt5
        data   = request.get_json() or {}
        ticket = int(data.get("ticket", 0))
        if not ticket:
            return jsonify({"ok": False, "error": "No ticket"}), 400
        if not mt5.initialize():
            return jsonify({"ok": False, "error": "MT5 not connected"}), 500
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            mt5.shutdown()
            return jsonify({"ok": False, "error": "Position not found"}), 404
        pos  = positions[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        info = mt5.symbol_info(pos.symbol)
        fill = mt5.ORDER_FILLING_FOK
        if info and (info.filling_mode & 4):
            fill = mt5.ORDER_FILLING_RETURN
        req = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       pos.volume,
            "type":         mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
            "position":     ticket,
            "price":        tick.bid if pos.type == 0 else tick.ask,
            "deviation":    20,
            "magic":        pos.magic,
            "comment":      "DASHBOARD_CLOSE",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": fill,
        }
        result = mt5.order_send(req)
        mt5.shutdown()
        if result and result.retcode == 10009:
            return jsonify({"ok": True, "profit": round(pos.profit, 2)})
        code = result.retcode if result else "None"
        return jsonify({"ok": False, "error": f"retcode={code}"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/control/settings", methods=["GET", "POST"])
def ctrl_settings():
    settings_file = os.path.join(_ROOT, "config", "settings.py")
    if request.method == "POST":
        data = request.get_json() or {}
        if "max_open_trades" in data:
            val = int(data["max_open_trades"])
            val = max(1, min(50, val))  # clamp 1-50
            s = open(settings_file, encoding="utf-8").read()
            s = re.sub(r'MAX_OPEN_TRADES\s*=\s*\d+', f'MAX_OPEN_TRADES       = {val}', s)
            open(settings_file, "w", encoding="utf-8").write(s)
        if "risk_per_trade_pct" in data:
            val = float(data["risk_per_trade_pct"])
            val = max(0.001, min(0.05, val))  # clamp 0.1%-5%
            s = open(settings_file, encoding="utf-8").read()
            s = re.sub(r'RISK_PER_TRADE_PCT\s*=\s*[\d.]+', f'RISK_PER_TRADE_PCT    = {val:.3f}', s)
            open(settings_file, "w", encoding="utf-8").write(s)
        if "daily_loss_limit_pct" in data:
            val = float(data["daily_loss_limit_pct"])
            val = max(0.01, min(0.20, val))  # clamp 1%-20%
            s = open(settings_file, encoding="utf-8").read()
            s = re.sub(r'DAILY_LOSS_LIMIT_PCT\s*=\s*[\d.]+', f'DAILY_LOSS_LIMIT_PCT  = {val:.2f}', s)
            open(settings_file, "w", encoding="utf-8").write(s)
        return jsonify({"ok": True})
    # GET — read current values
    try:
        s = open(settings_file, encoding="utf-8").read()
        m_max  = re.search(r'MAX_OPEN_TRADES\s*=\s*(\d+)', s)
        m_risk = re.search(r'RISK_PER_TRADE_PCT\s*=\s*([\d.]+)', s)
        m_loss = re.search(r'DAILY_LOSS_LIMIT_PCT\s*=\s*([\d.]+)', s)
        return jsonify({
            "max_open_trades":      int(m_max.group(1))   if m_max  else 10,
            "risk_per_trade_pct":   float(m_risk.group(1)) if m_risk else 0.01,
            "daily_loss_limit_pct": float(m_loss.group(1)) if m_loss else 0.03,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/control/status")
def ctrl_status():
    if os.path.exists(CONTROL_FILE):
        try:
            return jsonify(json.load(open(CONTROL_FILE)))
        except:
            pass
    return jsonify({"running": True, "mode": "FULL_AUTO"})


def _native(obj):
    """Recursively convert numpy/non-serializable types to plain Python."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_native(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float) and (obj != obj or obj == float('inf') or obj == float('-inf')):
        return 0.0  # NaN / inf → 0
    return obj


@app.route("/api/performance")
def api_performance():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from ai_engine.performance_tracker import PerformanceTracker
        tracker = PerformanceTracker()
        days    = int(request.args.get("days", 30))
        report  = tracker.get_report(days=days)
        return jsonify(_native(report))
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

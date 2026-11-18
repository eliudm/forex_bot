"""
One-time script: syncs performance_tracker.json with actual MT5 positions.
Removes closed trades from open_trades and adds them to history.
Run once from C:\forex_bot: python sync_tracker.py
"""
import json, os, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 not installed — run this on the bot machine.")
    sys.exit(1)

TRACKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "performance_tracker.json")

if not mt5.initialize():
    print(f"MT5 init failed: {mt5.last_error()}")
    sys.exit(1)

# Load tracker
with open(TRACKER, encoding="utf-8") as f:
    data = json.load(f)

open_trades = data.get("open_trades", {})
history     = data.get("history", [])

# Get real open positions
live_positions = mt5.positions_get() or []
live_tickets   = {str(p.ticket) for p in live_positions}

print(f"\nLive MT5 positions : {len(live_tickets)} — {live_tickets}")
print(f"Tracker open trades: {len(open_trades)} — {set(open_trades.keys())}")

stale = set(open_trades.keys()) - live_tickets
print(f"\nStale (closed) tickets to reconcile: {stale}")

# Pull deal history for the last 7 days to find actual close prices/profits
from_date = datetime.now() - timedelta(days=7)
deals = mt5.history_deals_get(from_date, datetime.now()) or []
deal_map = {}  # position_id → closing deal
for d in deals:
    if d.entry == 1:  # entry=1 means OUT (closing deal)
        deal_map[str(d.position_id)] = d

moved = 0
for ticket in stale:
    trade = open_trades.pop(ticket)
    # Check history already has this ticket
    if any(str(h.get("ticket")) == ticket for h in history):
        print(f"  #{ticket} ({trade['symbol']}) — already in history, just removed from open_trades")
        moved += 1
        continue

    deal = deal_map.get(ticket)
    if deal:
        profit     = round(deal.profit + deal.swap + deal.commission, 2)
        close_time = datetime.fromtimestamp(deal.time).isoformat()
        exit_price = deal.price
    else:
        profit     = round(trade.get("profit", 0), 2)
        close_time = datetime.now().isoformat()
        exit_price = 0

    result = "WIN" if profit > 0 else "LOSS"
    try:
        open_dt = datetime.fromisoformat(str(trade.get("open_time", "")))
        close_dt = datetime.fromisoformat(close_time)
        hold_min = int((close_dt - open_dt).total_seconds() // 60)
    except Exception:
        hold_min = 0

    history.append({
        **trade,
        "exit":         exit_price,
        "profit":       profit,
        "result":       result,
        "close_time":   close_time,
        "hold_minutes": hold_min,
        "status":       "CLOSED",
    })
    print(f"  #{ticket} ({trade['symbol']}) → history  profit=${profit:+.2f}  result={result}")
    moved += 1

data["open_trades"] = open_trades
data["history"]     = history

with open(TRACKER, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

mt5.shutdown()
print(f"\nDone. Moved {moved} stale trades to history.")
print(f"Tracker now has {len(open_trades)} open trades and {len(history)} history entries.")

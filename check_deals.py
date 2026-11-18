"""Check last 20 deals in MT5 history to see magic numbers on closures."""
import MetaTrader5 as mt5, sys, os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv; load_dotenv()

if not mt5.initialize():
    print(f"init failed: {mt5.last_error()}"); sys.exit(1)

since = datetime.now() - timedelta(days=2)
deals = mt5.history_deals_get(since, datetime.now())
if not deals:
    print("No deals found"); mt5.shutdown(); sys.exit(0)

print(f"{'Ticket':>14} {'Position':>14} {'Symbol':<22} {'Type':>5} {'Entry':>5} "
      f"{'Magic':>10} {'Profit':>8}")
print("-" * 85)
for d in sorted(deals, key=lambda x: x.time)[-30:]:
    entry_lbl = {0: "IN", 1: "OUT", 2: "INOUT", 3: "STATE"}.get(d.entry, str(d.entry))
    type_lbl  = {0: "BUY", 1: "SELL"}.get(d.type, str(d.type))
    print(f"{d.ticket:>14} {d.position_id:>14} {d.symbol:<22} {type_lbl:>5} {entry_lbl:>5} "
          f"{d.magic:>10} {d.profit:>8.2f}")

mt5.shutdown()

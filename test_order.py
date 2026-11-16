"""Quick diagnostic — places a minimum-lot market order using the correct fill type."""
import MetaTrader5 as mt5, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv; load_dotenv()
login    = int(os.environ.get("MT5_LOGIN", "0"))
password = os.environ.get("MT5_PASSWORD", "")
server   = os.environ.get("MT5_SERVER", "Deriv-Demo")

print(f"Connecting as {login} on {server}...")
if not mt5.initialize():
    print(f"initialize() failed: {mt5.last_error()}")
    sys.exit(1)

info = mt5.terminal_info()
print(f"Terminal: build {info.build} | trade_allowed={info.trade_allowed} | connected={info.connected}")

acct = mt5.account_info()
print(f"Account: {acct.login} | balance={acct.balance} | trade_allowed={acct.trade_allowed}")

# Try symbols in order of preference
for candidate in ["Boom 500 Index", "Volatility 10 Index", "EURUSD"]:
    tick = mt5.symbol_info_tick(candidate)
    if tick is not None:
        sym = candidate
        break
else:
    print("Cannot get tick for any test symbol"); sys.exit(1)

sinfo = mt5.symbol_info(sym)
vol   = sinfo.volume_min
price = tick.ask

# Determine supported filling types from the symbol's filling_mode bitmask
# bit0=FOK(1), bit1=IOC(2), bit2=RETURN(4)
fills = []
if sinfo.filling_mode & 1: fills.append(("FOK",    mt5.ORDER_FILLING_FOK))
if sinfo.filling_mode & 2: fills.append(("IOC",    mt5.ORDER_FILLING_IOC))
if sinfo.filling_mode & 4: fills.append(("RETURN", mt5.ORDER_FILLING_RETURN))
if not fills:               fills = [("FOK", mt5.ORDER_FILLING_FOK)]  # fallback

print(f"\nTest symbol: {sym} | ask={price} | min_lot={vol} | filling_mode={sinfo.filling_mode}")

for name, fill in fills:
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       sym,
        "volume":       vol,
        "type":         mt5.ORDER_TYPE_BUY,
        "price":        price,
        "sl":           0.0,
        "tp":           0.0,
        "magic":        99999,
        "comment":      f"test_{name}",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": fill,
    }
    result = mt5.order_send(req)
    code   = result.retcode if result else "None"
    ok     = code == 10009
    print(f"  {name:6}: retcode={code}  {'✅ PLACED' if ok else '❌ FAILED'}")
    if ok:
        mt5.Close(sym)
        break

mt5.shutdown()
print("\nDone.")

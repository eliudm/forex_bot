"""
Backtest runner — run with: python backtest/run_backtest.py
Uses simulated data if MT5 is not connected.
"""
import sys, os, numpy as np, pandas as pd, logging
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
logging.basicConfig(level=logging.WARNING)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtester import Backtester

def generate_sample_data(n=800, symbol="XAUUSD"):
    # Seed per-symbol (not a fixed constant) — otherwise every symbol gets
    # the exact same relative random walk, just scaled by its start price,
    # and every "per-symbol" backtest below produces identical results.
    rng = np.random.default_rng(abs(hash(symbol)) % (2 ** 32))
    prices = {"XAUUSD":1900,"EURUSD":1.08,"GBPUSD":1.27,"Volatility 75 Index":500,"Boom 1000 Index":8000}
    start  = prices.get(symbol, 1.0)
    close  = [start]
    for i in range(1, n):
        phase = (i // 80) % 4
        drift = 0.0003 if phase < 2 else (-0.0002 if phase == 2 else 0.0)
        close.append(close[-1] * (1 + rng.normal(drift, 0.004)))
    close = np.array(close)
    spread = close * 0.0005
    dates = pd.date_range("2023-01-01", periods=n, freq="h")
    return pd.DataFrame({"time":dates,"open":np.roll(close,1),"high":close+np.abs(rng.normal(0,spread)),
                         "low":close-np.abs(rng.normal(0,spread)),"close":close,
                         "volume":rng.integers(100,5000,n).astype(float)})

symbols = ["XAUUSD","EURUSD","GBPUSD","Volatility 75 Index","Boom 1000 Index"]
results_all = []
print("\n" + "="*60)
print("  BACKTEST SUITE - FOREX AI BOT (Simulated Data)")
print("="*60)
for sym in symbols:
    print(f"\n  Testing {sym}...")
    df = generate_sample_data(800, sym)
    bt = Backtester(symbol=sym, initial_balance=500, risk_pct=0.01)
    bt.load_data(df)
    r = bt.run(train_pct=0.70)
    if "error" not in r:
        bt.print_report(r)
        results_all.append(r)
    else:
        print(f"  [!] {r['error']} (model wasn't confident enough on this run - expected sometimes on synthetic data)")

if results_all:
    print("\n" + "="*60)
    print("  SUMMARY")
    print(f"  {'Symbol':<25} {'Win%':>6} {'PF':>6} {'Return%':>9} {'MaxDD%':>7}")
    print("  " + "─"*55)
    for r in results_all:
        print(f"  {r['symbol']:<25} {r['win_rate']:>5.1f}% {r['profit_factor']:>6.2f} {r['total_return_pct']:>+8.1f}% {r['max_drawdown_pct']:>6.1f}%")
    print("="*60)

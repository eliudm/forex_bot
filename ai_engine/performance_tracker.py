"""
=============================================================
  PERFORMANCE TRACKER
=============================================================
  Records every trade and generates detailed reports.
  After 4 weeks of demo trading, this tells you whether
  the bot is ready for live money.

  METRICS TRACKED:
  - Win rate per symbol
  - Win rate per strategy
  - Win rate per session (London/NY/Asian)
  - Win rate per market regime
  - Profit factor
  - Sharpe ratio
  - Maximum drawdown
  - Average hold time
  - Best/worst trades
  - Weekly P&L trend
=============================================================
"""

import json
import os
import logging
from datetime import datetime, date, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

TRACKER_FILE = "logs/performance_tracker.json"


class PerformanceTracker:
    """
    Records every trade and calculates detailed statistics.

    HOW TO USE:
        tracker = PerformanceTracker()

        # When a trade opens:
        tracker.record_open(ticket=12345, symbol="XAUUSD",
                           direction="BUY", entry=1920.5,
                           sl=1910.0, tp=1941.0,
                           lot=0.05, confidence=0.78,
                           strategy="TREND_FOLLOW",
                           regime="STRONG_TREND")

        # When a trade closes:
        tracker.record_close(ticket=12345, exit_price=1938.0,
                            profit=18.50, result="WIN")

        # Get report:
        report = tracker.get_report()
        tracker.print_report(report)
    """

    def __init__(self):
        self.trades     = {}   # Open trades keyed by ticket
        self.history    = []   # All closed trades
        self._load()

    # ─────────────────────────────────────────
    #  RECORD TRADE OPEN
    # ─────────────────────────────────────────
    def record_open(self, ticket: int, symbol: str, direction: str,
                    entry: float, sl: float, tp: float, lot: float,
                    confidence: float = 0, strategy: str = "N/A",
                    regime: str = "N/A"):
        hour = datetime.now().hour
        if 7 <= hour <= 16:
            session = "London"
        elif 12 <= hour <= 16:
            session = "Overlap"
        elif 13 <= hour <= 21:
            session = "New York"
        else:
            session = "Asian"

        self.trades[str(ticket)] = {
            "ticket":     ticket,
            "symbol":     symbol,
            "direction":  direction,
            "entry":      entry,
            "sl":         sl,
            "tp":         tp,
            "lot":        lot,
            "confidence": confidence,
            "strategy":   strategy,
            "regime":     regime,
            "session":    session,
            "open_time":  datetime.now().isoformat(),
            "status":     "OPEN"
        }
        self._save()
        logger.info(f"[TRACKER] Trade opened: {symbol} {direction} @ {entry} | Ticket: {ticket}")

    # ─────────────────────────────────────────
    #  RECORD TRADE CLOSE
    # ─────────────────────────────────────────
    def record_close(self, ticket: int, exit_price: float,
                     profit: float, result: str = None):
        key = str(ticket)
        if key not in self.trades:
            logger.warning(f"[TRACKER] Ticket {ticket} not found in open trades")
            return

        trade = self.trades.pop(key)

        if result is None:
            result = "WIN" if profit > 0 else "LOSS"

        close_time   = datetime.now()
        open_time    = datetime.fromisoformat(trade["open_time"])
        hold_minutes = (close_time - open_time).seconds // 60

        trade.update({
            "exit":         exit_price,
            "profit":       round(profit, 2),
            "result":       result,
            "close_time":   close_time.isoformat(),
            "hold_minutes": hold_minutes,
            "status":       "CLOSED"
        })

        self.history.append(trade)
        self._save()

        emoji = "[WIN]" if profit > 0 else "[LOSS]"
        logger.info(f"[TRACKER] {emoji} Trade closed: {trade['symbol']} "
                    f"${profit:+.2f} | Hold: {hold_minutes}min | Ticket: {ticket}")

    # ─────────────────────────────────────────
    #  GENERATE FULL REPORT
    # ─────────────────────────────────────────
    def get_report(self, days: int = 30) -> dict:
        """Generate a comprehensive performance report for the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        trades = [t for t in self.history
                  if datetime.fromisoformat(t['close_time']) >= cutoff]

        if not trades:
            return {"error": f"No closed trades in the last {days} days"}

        # ── BASIC STATS ─────────────────────────────────────────
        wins    = [t for t in trades if t['profit'] > 0]
        losses  = [t for t in trades if t['profit'] <= 0]
        profits = [t['profit'] for t in trades]

        win_rate      = len(wins) / len(trades) * 100
        total_pnl     = sum(profits)
        avg_win       = sum(t['profit'] for t in wins)   / len(wins)   if wins   else 0
        avg_loss      = sum(t['profit'] for t in losses) / len(losses) if losses else 0
        profit_factor = abs(sum(t['profit'] for t in wins)) / abs(sum(t['profit'] for t in losses)) \
                        if losses and sum(t['profit'] for t in losses) != 0 else float('inf')

        # ── DRAWDOWN ────────────────────────────────────────────
        peak, trough, max_dd = 0, 0, 0
        running = 0
        for p in profits:
            running += p
            peak   = max(peak, running)
            trough = min(trough, running - peak)
            max_dd = min(max_dd, trough)

        # ── SHARPE RATIO ────────────────────────────────────────
        import numpy as np
        if len(profits) > 1:
            sharpe = (np.mean(profits) / (np.std(profits) + 1e-10)) * (252 ** 0.5)
        else:
            sharpe = 0

        # ── BY SYMBOL ───────────────────────────────────────────
        by_symbol = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0})
        for t in trades:
            s = t['symbol']
            by_symbol[s]["trades"] += 1
            by_symbol[s]["wins"]   += 1 if t['profit'] > 0 else 0
            by_symbol[s]["pnl"]    += t['profit']
        for s in by_symbol:
            n = by_symbol[s]["trades"]
            w = by_symbol[s]["wins"]
            by_symbol[s]["win_rate"] = round(w / n * 100, 1) if n else 0
            by_symbol[s]["pnl"] = round(by_symbol[s]["pnl"], 2)

        # ── BY STRATEGY ─────────────────────────────────────────
        by_strategy = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0})
        for t in trades:
            s = t.get('strategy', 'N/A')
            by_strategy[s]["trades"] += 1
            by_strategy[s]["wins"]   += 1 if t['profit'] > 0 else 0
            by_strategy[s]["pnl"]    += t['profit']
        for s in by_strategy:
            n = by_strategy[s]["trades"]
            by_strategy[s]["win_rate"] = round(by_strategy[s]["wins"] / n * 100, 1) if n else 0
            by_strategy[s]["pnl"] = round(by_strategy[s]["pnl"], 2)

        # ── BY SESSION ──────────────────────────────────────────
        by_session = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0})
        for t in trades:
            s = t.get('session', 'Unknown')
            by_session[s]["trades"] += 1
            by_session[s]["wins"]   += 1 if t['profit'] > 0 else 0
            by_session[s]["pnl"]    += t['profit']
        for s in by_session:
            n = by_session[s]["trades"]
            by_session[s]["win_rate"] = round(by_session[s]["wins"] / n * 100, 1) if n else 0

        # ── BY REGIME ───────────────────────────────────────────
        by_regime = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0})
        for t in trades:
            r = t.get('regime', 'Unknown')
            by_regime[r]["trades"] += 1
            by_regime[r]["wins"]   += 1 if t['profit'] > 0 else 0
            by_regime[r]["pnl"]    += t['profit']
        for r in by_regime:
            n = by_regime[r]["trades"]
            by_regime[r]["win_rate"] = round(by_regime[r]["wins"] / n * 100, 1) if n else 0

        # ── WEEKLY BREAKDOWN ────────────────────────────────────
        weekly = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0})
        for t in trades:
            week = datetime.fromisoformat(t['close_time']).strftime("Week %W (%b %d)")
            weekly[week]["trades"] += 1
            weekly[week]["wins"]   += 1 if t['profit'] > 0 else 0
            weekly[week]["pnl"]    += t['profit']

        # ── BEST / WORST ────────────────────────────────────────
        best  = max(trades, key=lambda t: t['profit'])
        worst = min(trades, key=lambda t: t['profit'])

        # ── GO LIVE RECOMMENDATION ──────────────────────────────
        go_live = (
            win_rate > 55 and
            profit_factor > 1.5 and
            abs(max_dd) < 15 and
            sharpe > 1.0 and
            len(trades) >= 30
        )

        return {
            "period_days":    days,
            "total_trades":   len(trades),
            "wins":           len(wins),
            "losses":         len(losses),
            "win_rate":       round(win_rate, 2),
            "total_pnl":      round(total_pnl, 2),
            "avg_win":        round(avg_win, 2),
            "avg_loss":       round(avg_loss, 2),
            "profit_factor":  round(profit_factor, 2),
            "max_drawdown":   round(max_dd, 2),
            "sharpe_ratio":   round(sharpe, 2),
            "avg_hold_min":   round(sum(t.get('hold_minutes',0) for t in trades) / len(trades), 0),
            "best_trade":     {"symbol": best['symbol'],  "profit": best['profit'],  "strategy": best.get('strategy')},
            "worst_trade":    {"symbol": worst['symbol'], "profit": worst['profit'], "strategy": worst.get('strategy')},
            "by_symbol":      dict(by_symbol),
            "by_strategy":    dict(by_strategy),
            "by_session":     dict(by_session),
            "by_regime":      dict(by_regime),
            "weekly":         dict(weekly),
            "go_live_ready":  go_live,
            "go_live_checks": {
                "win_rate_ok":     win_rate > 55,
                "profit_factor_ok": profit_factor > 1.5,
                "drawdown_ok":     abs(max_dd) < 15,
                "sharpe_ok":       sharpe > 1.0,
                "enough_trades":   len(trades) >= 30,
            }
        }

    # ─────────────────────────────────────────
    #  PRINT REPORT TO CONSOLE
    # ─────────────────────────────────────────
    def print_report(self, r: dict):
        if "error" in r:
            print(f"\n[!] {r['error']}")
            return

        w = r.get
        print("\n" + "="*60)
        print(f"  PERFORMANCE REPORT — Last {w('period_days')} days")
        print("="*60)
        print(f"  Total Trades  : {w('total_trades')}  ({w('wins')} wins / {w('losses')} losses)")
        print(f"  Win Rate      : {w('win_rate'):.1f}%   {'[OK]' if w('win_rate') > 55 else '[NEEDS IMPROVEMENT]'}")
        print(f"  Total P&L     : ${w('total_pnl'):+,.2f}")
        print(f"  Avg Win       : ${w('avg_win'):+.2f}")
        print(f"  Avg Loss      : ${w('avg_loss'):+.2f}")
        print(f"  Profit Factor : {w('profit_factor'):.2f}  {'[OK]' if w('profit_factor') > 1.5 else '[LOW]'}")
        print(f"  Max Drawdown  : ${w('max_drawdown'):,.2f}  {'[OK]' if abs(w('max_drawdown')) < 15 else '[HIGH]'}")
        print(f"  Sharpe Ratio  : {w('sharpe_ratio'):.2f}  {'[OK]' if w('sharpe_ratio') > 1 else '[LOW]'}")
        print(f"  Avg Hold Time : {w('avg_hold_min'):.0f} minutes")

        print("\n  BY SYMBOL:")
        for sym, d in r.get('by_symbol', {}).items():
            print(f"    {sym:<25} WR:{d['win_rate']:>5.1f}% | {d['trades']} trades | ${d['pnl']:+.2f}")

        print("\n  BY STRATEGY:")
        for strat, d in r.get('by_strategy', {}).items():
            print(f"    {strat:<20} WR:{d['win_rate']:>5.1f}% | {d['trades']} trades | ${d['pnl']:+.2f}")

        print("\n  BY SESSION:")
        for sess, d in r.get('by_session', {}).items():
            print(f"    {sess:<15} WR:{d['win_rate']:>5.1f}% | {d['trades']} trades")

        print("\n  BY REGIME:")
        for reg, d in r.get('by_regime', {}).items():
            print(f"    {reg:<20} WR:{d['win_rate']:>5.1f}% | {d['trades']} trades")

        print("\n  WEEKLY P&L:")
        for week, d in sorted(r.get('weekly', {}).items()):
            bar = "+" * int(max(0, d['pnl']) / 5) + "-" * int(max(0, -d['pnl']) / 5)
            print(f"    {week:<20} ${d['pnl']:>+8.2f}  {bar}")

        print("\n  BEST TRADE  :", r['best_trade'])
        print("  WORST TRADE :", r['worst_trade'])

        print("\n" + "="*60)
        checks = r.get('go_live_checks', {})
        if r.get('go_live_ready'):
            print("  [READY FOR LIVE TRADING]")
        else:
            print("  [NOT READY FOR LIVE YET — criteria not met:]")
            if not checks.get('win_rate_ok'):
                print("    [X] Win rate must be above 55%")
            if not checks.get('profit_factor_ok'):
                print("    [X] Profit factor must be above 1.5")
            if not checks.get('drawdown_ok'):
                print("    [X] Max drawdown must be below $15")
            if not checks.get('sharpe_ok'):
                print("    [X] Sharpe ratio must be above 1.0")
            if not checks.get('enough_trades'):
                print("    [X] Need at least 30 trades to evaluate")
        print("="*60 + "\n")

    def _save(self):
        os.makedirs("logs", exist_ok=True)
        data = {"open_trades": self.trades, "history": self.history[-500:]}
        with open(TRACKER_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if os.path.exists(TRACKER_FILE):
            try:
                data = json.load(open(TRACKER_FILE))
                self.trades  = data.get("open_trades", {})
                self.history = data.get("history", [])
                logger.info(f"[TRACKER] Loaded {len(self.history)} historical trades")
            except Exception as e:
                logger.warning(f"[TRACKER] Could not load history: {e}")

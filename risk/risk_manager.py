# ============================================================
# risk/risk_manager.py — Protects Your Account
# ============================================================
# WHAT THIS FILE DOES:
#   Before ANY trade is placed, the risk manager checks:
#     1. Is the daily loss limit hit? (stop trading for today)
#     2. Are there too many open trades?
#     3. Is the spread too high? (broker charging too much)
#     4. Is the R:R ratio good enough?
#     5. What lot size should we use?
#   If any check fails → trade is BLOCKED.
#
# ON A $500 ACCOUNT:
#   1% risk = $5 per trade
#   3% daily loss limit = stop at -$15 per day
#   This protects you from losing your whole account quickly.
# ============================================================

import logging
from datetime import datetime, date
from config.config import (
    ACCOUNT_BALANCE, RISK_PER_TRADE_PCT, MAX_OPEN_TRADES,
    DAILY_LOSS_LIMIT_PCT, MIN_RR_RATIO, MAX_SPREAD_PIPS,
    MIN_LOT_SIZE, MAX_LOT_SIZE
)

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Evaluates every trade signal before execution.
    Acts as the last line of defense against bad trades.

    USAGE:
        rm = RiskManager()
        check = rm.evaluate_trade(signal, account_info, open_positions)
        if check["approved"]:
            place_trade(...)
        else:
            print(check["reason"])  # Why it was rejected
    """

    def __init__(self):
        self.daily_trades   = []    # Trades placed today
        self.daily_pnl      = 0.0   # Today's profit/loss total
        self.trade_date     = date.today()

    def _reset_daily_if_needed(self):
        """Reset daily counters at the start of each new day."""
        today = date.today()
        if today != self.trade_date:
            self.daily_trades = []
            self.daily_pnl    = 0.0
            self.trade_date   = today
            logger.info("📅 New trading day — daily counters reset.")

    def evaluate_trade(self, signal: dict, account_info: dict,
                       open_positions: list) -> dict:
        """
        Run all risk checks on a trade signal.

        Parameters:
            signal         : dict with keys: symbol, direction, sl_pips, tp_pips, spread
            account_info   : dict from MT5 with balance, equity, profit
            open_positions : list of currently open trades

        Returns:
            dict with keys:
              "approved"   : True/False
              "reason"     : Why it was approved or rejected
              "lot_size"   : Calculated lot size (if approved)
              "risk_amount": Dollar amount at risk
        """
        self._reset_daily_if_needed()

        balance  = account_info.get("balance", ACCOUNT_BALANCE)
        equity   = account_info.get("equity",  balance)
        daily_pl = account_info.get("profit",  0)

        # ── CHECK 1: Daily loss limit ─────────────────────────
        max_daily_loss = balance * DAILY_LOSS_LIMIT_PCT
        if daily_pl <= -max_daily_loss:
            msg = (f"🚫 BLOCKED: Daily loss limit hit. "
                   f"Loss: ${abs(daily_pl):.2f} / Limit: ${max_daily_loss:.2f}")
            logger.warning(msg)
            return {"approved": False, "reason": msg}

        # ── CHECK 2: Too many open trades ─────────────────────
        if len(open_positions) >= MAX_OPEN_TRADES:
            msg = (f"🚫 BLOCKED: Max open trades reached "
                   f"({len(open_positions)}/{MAX_OPEN_TRADES})")
            logger.warning(msg)
            return {"approved": False, "reason": msg}

        # ── CHECK 3: Spread too high ──────────────────────────
        spread = signal.get("spread", 0)
        if spread > MAX_SPREAD_PIPS:
            msg = (f"🚫 BLOCKED: Spread too high "
                   f"({spread:.1f} pips > {MAX_SPREAD_PIPS} pip limit)")
            logger.warning(msg)
            return {"approved": False, "reason": msg}

        # ── CHECK 4: Reward:Risk ratio check ──────────────────
        sl_pips = signal.get("sl_pips", 0)
        tp_pips = signal.get("tp_pips", 0)
        if sl_pips <= 0 or tp_pips <= 0:
            msg = "🚫 BLOCKED: Invalid SL or TP pips (must be > 0)"
            logger.warning(msg)
            return {"approved": False, "reason": msg}

        rr_ratio = tp_pips / sl_pips
        if rr_ratio < MIN_RR_RATIO:
            msg = (f"🚫 BLOCKED: R:R ratio too low "
                   f"({rr_ratio:.2f} < {MIN_RR_RATIO} minimum). "
                   f"Need TP={sl_pips * MIN_RR_RATIO:.1f} pips minimum.")
            logger.warning(msg)
            return {"approved": False, "reason": msg}

        # ── CHECK 5: Equity protection ───────────────────────
        # Don't trade if equity has dropped more than 5% below balance
        if equity < balance * 0.95:
            msg = (f"🚫 BLOCKED: Equity ({equity:.2f}) is significantly "
                   f"below balance ({balance:.2f}). Close losing trades first.")
            logger.warning(msg)
            return {"approved": False, "reason": msg}

        # ── CALCULATE LOT SIZE ────────────────────────────────
        risk_amount = balance * RISK_PER_TRADE_PCT
        lot_size    = self._calculate_lot_size(risk_amount, sl_pips,
                                               signal.get("symbol", "EURUSD"))

        # ── APPROVED ─────────────────────────────────────────
        msg = (f"✅ APPROVED: {signal.get('direction')} {signal.get('symbol')} | "
               f"Lot: {lot_size} | Risk: ${risk_amount:.2f} | R:R: {rr_ratio:.2f}")
        logger.info(msg)
        return {
            "approved":    True,
            "reason":      msg,
            "lot_size":    lot_size,
            "risk_amount": risk_amount,
            "rr_ratio":    rr_ratio,
        }

    def _calculate_lot_size(self, risk_amount: float, sl_pips: float,
                            symbol: str) -> float:
        """
        Calculate safe lot size from risk amount and stop loss.

        Formula: Lot Size = Risk Amount / (SL pips × Pip Value per lot)

        Pip values per 0.01 lot (approximate):
          - EURUSD, GBPUSD : $0.10
          - USDJPY          : $0.09
          - XAUUSD (Gold)   : $0.10
          - Volatility 75   : varies
        """
        # Pip value per micro lot (0.01) approximation
        pip_value_table = {
            "EURUSD": 0.10, "GBPUSD": 0.10, "AUDUSD": 0.10,
            "USDCHF": 0.10, "USDJPY": 0.09, "XAUUSD": 0.10,
            "Volatility 75 Index": 0.05,
            "Boom 1000 Index": 0.05, "Boom 500 Index": 0.05,
            "Crash 1000 Index": 0.05, "Crash 500 Index": 0.05,
        }
        pip_val = pip_value_table.get(symbol, 0.10)

        lots = risk_amount / (sl_pips * pip_val / 0.01)
        lots = round(round(lots / 0.01) * 0.01, 2)
        lots = max(MIN_LOT_SIZE, min(MAX_LOT_SIZE, lots))
        return lots

    def record_trade_result(self, profit: float):
        """Call this when a trade closes to track daily P&L."""
        self.daily_pnl += profit
        self.daily_trades.append({
            "time":   datetime.now(),
            "profit": profit,
        })
        logger.info(f"Trade closed. P&L: ${profit:.2f} | Daily total: ${self.daily_pnl:.2f}")

    def get_daily_summary(self) -> dict:
        """Return today's trading summary."""
        wins  = [t for t in self.daily_trades if t["profit"] > 0]
        loses = [t for t in self.daily_trades if t["profit"] <= 0]
        return {
            "date":       str(self.trade_date),
            "total_trades": len(self.daily_trades),
            "wins":       len(wins),
            "losses":     len(loses),
            "win_rate":   len(wins) / max(len(self.daily_trades), 1) * 100,
            "total_pnl":  self.daily_pnl,
        }

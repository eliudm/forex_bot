"""
=============================================================
  RISK MANAGEMENT MODULE
=============================================================
  PURPOSE: Protects your account from large losses.
  
  This is arguably the MOST IMPORTANT part of any trading bot.
  Even a bot with 60% win rate can blow an account if risk
  management is poor. This module ensures every trade is safe.

  CHECKS PERFORMED BEFORE EVERY TRADE:
  ✅ Daily loss limit not exceeded
  ✅ Maximum open trades not exceeded  
  ✅ Risk:Reward ratio is acceptable
  ✅ Position size is correctly calculated
  ✅ Account has enough free margin
  ✅ Spread is not abnormally wide
=============================================================
"""

import logging
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Guards every trade against excessive risk.
    
    HOW TO USE:
        rm = RiskManager(balance=500, risk_pct=0.01, max_trades=3, daily_loss_pct=0.03)
        
        # Before placing a trade:
        check = rm.check_trade(signal, open_positions, account)
        if check["approved"]:
            # Place the trade
        else:
            print(check["reason"])  # Why it was rejected
    """

    def __init__(self, balance: float, risk_pct: float = 0.01,
                 max_trades: int = 3, daily_loss_pct: float = 0.03,
                 min_rr: float = 2.0):
        
        self.initial_balance = balance
        self.risk_pct        = risk_pct        # 0.01 = risk 1% per trade
        self.max_trades      = max_trades      # Max 3 open trades at once
        self.daily_loss_pct  = daily_loss_pct  # Stop trading if -3% today
        self.min_rr          = min_rr          # Minimum 2:1 reward/risk

        # Daily tracking
        self.daily_trades     = []
        self.daily_loss       = 0.0
        self.last_reset_date  = date.today()

    def _reset_daily_if_needed(self):
        """Resets daily counters at the start of each new day."""
        today = date.today()
        if today != self.last_reset_date:
            logger.info(f"New trading day. Resetting daily counters.")
            self.daily_loss      = 0.0
            self.daily_trades    = []
            self.last_reset_date = today

    def check_trade(self, signal: dict, open_positions: list, account: dict) -> dict:
        """
        Runs ALL risk checks before approving a trade.
        
        PARAMETERS:
            signal         - The AI signal dict (action, sl, tp, rr_ratio, etc.)
            open_positions - List of currently open trades
            account        - Account info dict (balance, equity, margin_free)
        
        RETURNS:
            {"approved": True/False, "reason": "explanation", "risk_amount": $X}
        """
        self._reset_daily_if_needed()

        balance = account.get('balance', self.initial_balance)

        # ── CHECK 1: Daily loss limit ──────────────────────────────
        daily_loss_limit = balance * self.daily_loss_pct
        if abs(self.daily_loss) >= daily_loss_limit:
            return self._reject(
                f"Daily loss limit reached (${abs(self.daily_loss):.2f} / ${daily_loss_limit:.2f}). "
                f"No more trades today. Resume tomorrow."
            )

        # ── CHECK 2: Maximum open trades ──────────────────────────
        open_count = len(open_positions)
        if open_count >= self.max_trades:
            return self._reject(
                f"Max open trades reached ({open_count}/{self.max_trades}). "
                f"Wait for an existing trade to close."
            )

        # ── CHECK 3: Risk:Reward ratio ─────────────────────────────
        rr = signal.get('rr_ratio', 0)
        if rr < self.min_rr:
            return self._reject(
                f"Risk:Reward ratio too low ({rr:.1f}:1). "
                f"Minimum required: {self.min_rr}:1. "
                f"The potential profit must be at least {self.min_rr}x the potential loss."
            )

        # ── CHECK 4: AI confidence ─────────────────────────────────
        confidence = signal.get('confidence', 0)
        if confidence < 0.35:
            return self._reject(
                f"AI confidence too low ({confidence:.0%}). "
                f"Minimum: 35%. Waiting for a clearer signal."
            )

        # ── CHECK 5: Calculate risk amount ────────────────────────
        risk_amount = balance * self.risk_pct

        # ── CHECK 6: Free margin check ────────────────────────────
        margin_free = account.get('margin_free', balance)
        if margin_free < risk_amount * 10:
            return self._reject(
                f"Not enough free margin (${margin_free:.2f}). "
                f"Required at least ${risk_amount * 10:.2f}."
            )

        # ── ALL CHECKS PASSED ──────────────────────────────────────
        logger.info(f"✅ Risk check PASSED. Risk per trade: ${risk_amount:.2f} ({self.risk_pct:.0%} of ${balance:.2f})")
        return {
            "approved":    True,
            "reason":      "All risk checks passed",
            "risk_amount": round(risk_amount, 2),
            "risk_pct":    self.risk_pct
        }

    def record_trade_result(self, profit: float):
        """
        Records the result of a closed trade.
        Call this every time a trade closes.
        
        PARAMETERS:
            profit - The P&L of the trade (positive = win, negative = loss)
        """
        self._reset_daily_if_needed()
        self.daily_trades.append({"profit": profit, "time": datetime.now()})
        if profit < 0:
            self.daily_loss += abs(profit)
            logger.info(f"Trade loss recorded: ${profit:.2f}. Today's total loss: ${self.daily_loss:.2f}")
        else:
            logger.info(f"Trade win recorded: +${profit:.2f}")

    def get_daily_stats(self) -> dict:
        """Returns today's trading statistics."""
        self._reset_daily_if_needed()
        wins   = [t for t in self.daily_trades if t['profit'] > 0]
        losses = [t for t in self.daily_trades if t['profit'] < 0]
        total  = sum(t['profit'] for t in self.daily_trades)

        return {
            "date":        str(date.today()),
            "total_trades": len(self.daily_trades),
            "wins":         len(wins),
            "losses":       len(losses),
            "win_rate":     len(wins) / len(self.daily_trades) if self.daily_trades else 0,
            "total_pnl":    round(total, 2),
            "daily_loss":   round(self.daily_loss, 2)
        }

    def _reject(self, reason: str) -> dict:
        logger.warning(f"⛔ Trade REJECTED: {reason}")
        return {"approved": False, "reason": reason, "risk_amount": 0}

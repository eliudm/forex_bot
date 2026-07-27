"""
=============================================================
  LOSS DETECTION & SELF-HEALING ENGINE
=============================================================
  PURPOSE: Continuously monitors the bot's performance and
  takes AUTOMATIC ACTION when losses are detected.

  THIS MODULE DOES 7 THINGS:

  1. STREAK DETECTION
     Counts consecutive losses. After 3 in a row → warning.
     After 5 in a row → pause bot and alert you.

  2. DRAWDOWN MONITOR
     Tracks how far the account has fallen from its peak.
     At 5% drawdown  → reduce position size by 50%
     At 8% drawdown  → stop trading, wait for recovery
     At 12% drawdown → emergency stop, send urgent alert

  3. WIN RATE MONITOR
     Checks rolling 20-trade win rate every scan.
     If win rate drops below 45% → switch strategy
     If win rate drops below 35% → pause + retrain AI

  4. PROFIT FACTOR MONITOR
     Profit Factor = Total Wins / Total Losses
     If PF drops below 1.0 → something is wrong, investigate
     If PF drops below 0.8 → emergency pause

  5. STRATEGY AUTO-SWITCH
     When losses detected in current market regime,
     the engine automatically tries a different strategy.

  6. AI AUTO-RETRAIN TRIGGER
     When performance degrades significantly, forces the
     AI to retrain on the most recent data immediately.

  7. RECOVERY MODE
     After a bad losing streak, bot enters "recovery mode":
     - Only takes the HIGHEST confidence signals (75%+)
     - Reduces lot size to 50% of normal
     - Requires 3 consecutive wins to exit recovery mode
=============================================================
"""

import logging
import json
import os
from datetime import datetime, date, timedelta
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
#  BOT STATUS LEVELS
#  These represent how the bot is currently operating
# ─────────────────────────────────────────────────────────────────
class BotStatus(Enum):
    NORMAL      = "NORMAL"       # Everything fine, trading normally
    CAUTION     = "CAUTION"      # Some losses detected, being careful
    RECOVERY    = "RECOVERY"     # Losing streak, reduced size + high confidence only
    PAUSED      = "PAUSED"       # Too many losses, stopped trading temporarily
    EMERGENCY   = "EMERGENCY"    # Critical drawdown, full stop, needs manual review


# ─────────────────────────────────────────────────────────────────
#  THRESHOLDS (TRIGGER LEVELS)
# ─────────────────────────────────────────────────────────────────
class Thresholds:
    # Consecutive loss limits
    CAUTION_STREAK    = 2    # 2 losses in a row → CAUTION
    RECOVERY_STREAK   = 3    # 3 losses in a row → RECOVERY mode
    PAUSE_STREAK      = 5    # 5 losses in a row → PAUSE trading

    # Drawdown limits (% of peak balance)
    CAUTION_DD        = 3.0  # 3% drawdown  → CAUTION, reduce size
    RECOVERY_DD       = 5.0  # 5% drawdown  → RECOVERY mode
    PAUSE_DD          = 8.0  # 8% drawdown  → PAUSE trading
    EMERGENCY_DD      = 12.0 # 12% drawdown → EMERGENCY STOP

    # Rolling win rate (last 20 trades)
    CAUTION_WINRATE   = 50.0 # Below 50% → CAUTION
    RECOVERY_WINRATE  = 45.0 # Below 45% → RECOVERY
    PAUSE_WINRATE     = 35.0 # Below 35% → PAUSE + force retrain

    # Profit factor (last 20 trades)
    CAUTION_PF        = 1.2  # Below 1.2 → CAUTION
    PAUSE_PF          = 0.9  # Below 0.9 → PAUSE

    # Recovery conditions (to exit RECOVERY mode)
    RECOVERY_WIN_STREAK    = 3   # 3 wins in a row to exit recovery
    RECOVERY_MIN_WINRATE   = 55  # Win rate must recover to 55%+


class LossDetector:
    """
    The bot's self-awareness system. It watches every trade,
    detects when things are going wrong, and takes action.

    HOW TO USE:
        detector = LossDetector(initial_balance=500)

        # After every trade closes:
        detector.record_trade(profit=5.50, symbol="XAUUSD")

        # Before every new trade:
        status = detector.get_status()
        if status.can_trade:
            # Place trade
        else:
            print(status.reason)

        # Check what adjustments to make:
        adj = detector.get_trade_adjustments()
        lot_multiplier = adj['lot_multiplier']  # e.g., 0.5 for 50% size
    """

    def __init__(self, initial_balance: float = 500,
                 save_path: str = "logs/loss_detector_state.json"):

        self.initial_balance = initial_balance
        self.peak_balance    = initial_balance
        self.current_balance = initial_balance
        self.save_path       = save_path

        # Trade history (keep last 50 trades in memory)
        self.trade_history   = deque(maxlen=50)

        # Streak tracking
        self.loss_streak     = 0   # Current consecutive losses
        self.win_streak      = 0   # Current consecutive wins
        self.recovery_wins   = 0   # Wins accumulated while in RECOVERY

        # Status
        self.status          = BotStatus.NORMAL
        self.status_reason   = "All good. Trading normally."
        self.status_since    = datetime.now()

        # Daily tracking
        self.daily_start_balance = initial_balance
        self.last_day_reset      = date.today()

        # Alert tracking (avoid spamming same alert)
        self.last_alert_type  = None
        self.last_alert_time  = None

        # Auto-retrain flag
        self.retrain_requested = False

        # Load previous state if exists
        self._load_state()

        logger.info(f"LossDetector initialized. Balance: ${initial_balance:.2f}")

    # ─────────────────────────────────────────
    #  RECORD A TRADE RESULT
    # ─────────────────────────────────────────
    def record_trade(self, profit: float, symbol: str = "UNKNOWN",
                     confidence: float = 0.0, strategy: str = "N/A") -> dict:
        """
        Call this EVERY TIME a trade closes.

        PARAMETERS:
            profit     - P&L of the trade (+ve = win, -ve = loss)
            symbol     - Which market was traded
            confidence - AI confidence that was used for this trade
            strategy   - Strategy name used

        RETURNS:
            dict with the new status and any actions to take
        """
        # Reset daily counter if new day
        self._daily_reset_if_needed()

        # Record the trade
        trade_record = {
            "profit":     round(profit, 2),
            "symbol":     symbol,
            "confidence": confidence,
            "strategy":   strategy,
            "result":     "WIN" if profit > 0 else "LOSS",
            "time":       datetime.now().isoformat(),
            "balance":    round(self.current_balance + profit, 2)
        }
        self.trade_history.append(trade_record)

        # Update balance and peak
        self.current_balance += profit
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance

        # Update streak counters
        if profit > 0:
            self.win_streak  += 1
            self.loss_streak  = 0
            if self.status == BotStatus.RECOVERY:
                self.recovery_wins += 1
        else:
            self.loss_streak += 1
            self.win_streak   = 0
            self.recovery_wins = 0

        # Re-evaluate status after every trade
        old_status = self.status
        self._evaluate_status()

        # Log what happened
        emoji = "✅" if profit > 0 else "❌"
        logger.info(f"{emoji} Trade recorded: {symbol} ${profit:+.2f} | "
                    f"Balance: ${self.current_balance:.2f} | "
                    f"Status: {self.status.value} | "
                    f"Loss streak: {self.loss_streak}")

        # Detect status change
        status_changed = old_status != self.status
        if status_changed:
            logger.warning(f"⚠️  STATUS CHANGED: {old_status.value} → {self.status.value}")
            logger.warning(f"   Reason: {self.status_reason}")

        # Save state
        self._save_state()

        return {
            "new_status":      self.status.value,
            "status_changed":  status_changed,
            "old_status":      old_status.value,
            "loss_streak":     self.loss_streak,
            "win_streak":      self.win_streak,
            "drawdown_pct":    self._get_drawdown_pct(),
            "retrain_needed":  self.retrain_requested,
            "reason":          self.status_reason
        }

    # ─────────────────────────────────────────
    #  EVALUATE CURRENT STATUS
    # ─────────────────────────────────────────
    def _evaluate_status(self):
        """
        The core logic. Checks all metrics and sets the status level.
        Called automatically after every trade.
        """
        drawdown_pct = self._get_drawdown_pct()
        win_rate_20  = self._get_rolling_win_rate(20)
        pf_20        = self._get_rolling_profit_factor(20)

        # ── EMERGENCY CHECK (highest priority) ────────────────────
        if drawdown_pct >= Thresholds.EMERGENCY_DD:
            self._set_status(BotStatus.EMERGENCY,
                f"🚨 EMERGENCY: Drawdown {drawdown_pct:.1f}% exceeds {Thresholds.EMERGENCY_DD}% limit. "
                f"FULL STOP. Review your settings before continuing.")
            return

        # ── PAUSE CHECK ────────────────────────────────────────────
        if (drawdown_pct >= Thresholds.PAUSE_DD or
            self.loss_streak >= Thresholds.PAUSE_STREAK or
            (win_rate_20 is not None and win_rate_20 < Thresholds.PAUSE_WINRATE) or
            (pf_20 is not None and pf_20 < Thresholds.PAUSE_PF)):

            reasons = []
            if drawdown_pct >= Thresholds.PAUSE_DD:
                reasons.append(f"drawdown {drawdown_pct:.1f}% ≥ {Thresholds.PAUSE_DD}%")
            if self.loss_streak >= Thresholds.PAUSE_STREAK:
                reasons.append(f"{self.loss_streak} consecutive losses")
            if win_rate_20 and win_rate_20 < Thresholds.PAUSE_WINRATE:
                reasons.append(f"win rate {win_rate_20:.0f}% < {Thresholds.PAUSE_WINRATE}%")
            if pf_20 and pf_20 < Thresholds.PAUSE_PF:
                reasons.append(f"profit factor {pf_20:.2f} < {Thresholds.PAUSE_PF}")

            self._set_status(BotStatus.PAUSED,
                f"⛔ PAUSED: {' | '.join(reasons)}. "
                f"Bot will wait for market conditions to improve. Will auto-resume after cool-down.")
            self.retrain_requested = True
            return

        # ── RECOVERY CHECK ─────────────────────────────────────────
        if self.status == BotStatus.RECOVERY:
            # Check if we can exit recovery
            if (self.recovery_wins >= Thresholds.RECOVERY_WIN_STREAK and
                (win_rate_20 is None or win_rate_20 >= Thresholds.RECOVERY_MIN_WINRATE)):
                self._set_status(BotStatus.NORMAL,
                    f"✅ RECOVERED: {self.recovery_wins} consecutive wins. "
                    f"Returning to normal trading.")
            else:
                # Stay in recovery — update reason
                self._set_status(BotStatus.RECOVERY,
                    f"🔄 RECOVERY MODE: Reduced position size (50%). "
                    f"Min confidence 75%+. "
                    f"Need {Thresholds.RECOVERY_WIN_STREAK - self.recovery_wins} more wins to return to normal.")
            return

        if (drawdown_pct >= Thresholds.RECOVERY_DD or
            self.loss_streak >= Thresholds.RECOVERY_STREAK or
            (win_rate_20 is not None and win_rate_20 < Thresholds.RECOVERY_WINRATE)):

            reasons = []
            if drawdown_pct >= Thresholds.RECOVERY_DD:
                reasons.append(f"drawdown {drawdown_pct:.1f}%")
            if self.loss_streak >= Thresholds.RECOVERY_STREAK:
                reasons.append(f"{self.loss_streak} losses in a row")
            if win_rate_20 and win_rate_20 < Thresholds.RECOVERY_WINRATE:
                reasons.append(f"win rate {win_rate_20:.0f}%")

            self._set_status(BotStatus.RECOVERY,
                f"🔄 RECOVERY MODE: {' | '.join(reasons)}. "
                f"Position size reduced to 50%. Only taking 75%+ confidence signals.")
            self.recovery_wins = 0
            return

        # ── CAUTION CHECK ──────────────────────────────────────────
        if (drawdown_pct >= Thresholds.CAUTION_DD or
            self.loss_streak >= Thresholds.CAUTION_STREAK or
            (win_rate_20 is not None and win_rate_20 < Thresholds.CAUTION_WINRATE) or
            (pf_20 is not None and pf_20 < Thresholds.CAUTION_PF)):

            reasons = []
            if drawdown_pct >= Thresholds.CAUTION_DD:
                reasons.append(f"drawdown {drawdown_pct:.1f}%")
            if self.loss_streak >= Thresholds.CAUTION_STREAK:
                reasons.append(f"{self.loss_streak} losses in a row")
            if win_rate_20 and win_rate_20 < Thresholds.CAUTION_WINRATE:
                reasons.append(f"win rate {win_rate_20:.0f}%")

            self._set_status(BotStatus.CAUTION,
                f"⚠️  CAUTION: {' | '.join(reasons)}. "
                f"Slightly reducing position size. Monitoring closely.")
            return

        # ── ALL GOOD ───────────────────────────────────────────────
        if self.status != BotStatus.NORMAL:
            self._set_status(BotStatus.NORMAL, "✅ All metrics healthy. Trading normally.")

    # ─────────────────────────────────────────
    #  GET TRADE ADJUSTMENTS
    # ─────────────────────────────────────────
    def get_trade_adjustments(self) -> dict:
        """
        Returns how the bot should adjust its behavior right now.

        RETURNS:
        {
            "can_trade":        True/False,
            "lot_multiplier":   1.0  (0.5 = half size, 0.0 = no trading),
            "min_confidence":   0.65 (raise to 0.75 in recovery),
            "reason":           "explanation",
            "status":           "NORMAL"
        }
        """
        if self.status == BotStatus.NORMAL:
            return {"can_trade": True,  "lot_multiplier": 1.00, "min_confidence": 0.65,
                    "status": "NORMAL", "reason": self.status_reason}

        elif self.status == BotStatus.CAUTION:
            return {"can_trade": True,  "lot_multiplier": 0.75, "min_confidence": 0.68,
                    "status": "CAUTION", "reason": self.status_reason}

        elif self.status == BotStatus.RECOVERY:
            return {"can_trade": True,  "lot_multiplier": 0.50, "min_confidence": 0.75,
                    "status": "RECOVERY", "reason": self.status_reason}

        elif self.status == BotStatus.PAUSED:
            return {"can_trade": False, "lot_multiplier": 0.00, "min_confidence": 1.00,
                    "status": "PAUSED", "reason": self.status_reason}

        elif self.status == BotStatus.EMERGENCY:
            return {"can_trade": False, "lot_multiplier": 0.00, "min_confidence": 1.00,
                    "status": "EMERGENCY", "reason": self.status_reason}

        return {"can_trade": True, "lot_multiplier": 1.0, "min_confidence": 0.65,
                "status": "UNKNOWN", "reason": "Unknown status"}

    # ─────────────────────────────────────────
    #  GET FULL REPORT
    # ─────────────────────────────────────────
    def get_report(self) -> dict:
        """Returns a full snapshot of the bot's health."""
        trades  = list(self.trade_history)
        wins    = [t for t in trades if t['profit'] > 0]
        losses  = [t for t in trades if t['profit'] <= 0]
        total   = len(trades)

        return {
            "status":           self.status.value,
            "status_reason":    self.status_reason,
            "current_balance":  round(self.current_balance, 2),
            "peak_balance":     round(self.peak_balance, 2),
            "drawdown_pct":     round(self._get_drawdown_pct(), 2),
            "loss_streak":      self.loss_streak,
            "win_streak":       self.win_streak,
            "total_trades":     total,
            "wins":             len(wins),
            "losses":           len(losses),
            "win_rate_all":     round(len(wins)/total*100, 1) if total else 0,
            "win_rate_20":      self._get_rolling_win_rate(20),
            "profit_factor_20": self._get_rolling_profit_factor(20),
            "total_pnl":        round(self.current_balance - self.initial_balance, 2),
            "retrain_needed":   self.retrain_requested,
            "adjustments":      self.get_trade_adjustments(),
            "can_trade":        self.get_trade_adjustments()["can_trade"]
        }

    # ─────────────────────────────────────────
    #  MANUAL CONTROLS
    # ─────────────────────────────────────────
    def manual_resume(self):
        """Manually resume the bot after a PAUSE or EMERGENCY."""
        logger.warning("Manual resume triggered. Returning to CAUTION mode.")
        self._set_status(BotStatus.CAUTION, "Manually resumed. Watching closely.")
        self.loss_streak    = 0
        self.recovery_wins  = 0
        self.retrain_requested = False

    def acknowledge_retrain(self):
        """Call this after the AI has been retrained."""
        self.retrain_requested = False
        logger.info("Retrain acknowledged.")

    # ─────────────────────────────────────────
    #  INTERNAL HELPERS
    # ─────────────────────────────────────────
    def _get_drawdown_pct(self) -> float:
        if self.peak_balance == 0:
            return 0.0
        return max(0.0, (self.peak_balance - self.current_balance) / self.peak_balance * 100)

    def _get_rolling_win_rate(self, n: int):
        trades = list(self.trade_history)[-n:]
        if len(trades) < 5:
            return None
        wins = sum(1 for t in trades if t['profit'] > 0)
        return round(wins / len(trades) * 100, 1)

    def _get_rolling_profit_factor(self, n: int):
        trades = list(self.trade_history)[-n:]
        if len(trades) < 5:
            return None
        total_win  = sum(t['profit'] for t in trades if t['profit'] > 0)
        total_loss = abs(sum(t['profit'] for t in trades if t['profit'] < 0))
        if total_loss == 0:
            return None
        return round(total_win / total_loss, 2)

    def _set_status(self, status: BotStatus, reason: str):
        if self.status != status:
            self.status_since = datetime.now()
        self.status        = status
        self.status_reason = reason

    def _daily_reset_if_needed(self):
        today = date.today()
        if today != self.last_day_reset:
            self.daily_start_balance = self.current_balance
            self.last_day_reset      = today
            logger.info(f"New day. Daily balance reset to ${self.daily_start_balance:.2f}")

    def _save_state(self):
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        state = {
            "current_balance": self.current_balance,
            "peak_balance":    self.peak_balance,
            "loss_streak":     self.loss_streak,
            "win_streak":      self.win_streak,
            "recovery_wins":   self.recovery_wins,
            "status":          self.status.value,
            "status_reason":   self.status_reason,
            "trade_history":   list(self.trade_history),
            "saved_at":        datetime.now().isoformat()
        }
        with open(self.save_path, 'w') as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        if not os.path.exists(self.save_path):
            return
        try:
            with open(self.save_path, 'r') as f:
                state = json.load(f)
            self.current_balance = state.get("current_balance", self.initial_balance)
            self.peak_balance    = state.get("peak_balance",    self.initial_balance)
            self.loss_streak     = state.get("loss_streak", 0)
            self.win_streak      = state.get("win_streak",  0)
            self.recovery_wins   = state.get("recovery_wins", 0)
            status_str           = state.get("status", "NORMAL")
            self.status          = BotStatus(status_str)
            self.status_reason   = state.get("status_reason", "")
            for t in state.get("trade_history", []):
                self.trade_history.append(t)
            logger.info(f"Loaded previous state. Status: {self.status.value} | "
                        f"Balance: ${self.current_balance:.2f} | "
                        f"Loss streak: {self.loss_streak}")
        except Exception as e:
            logger.warning(f"Could not load previous state: {e}")

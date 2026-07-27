# =============================================================================
# backtest/backtest_engine.py — Backtesting Engine
# =============================================================================
# WHAT THIS FILE DOES:
#   Tests any strategy on HISTORICAL data to see how it would have performed
#   BEFORE risking real money.
#
# WHY BACKTESTING IS CRITICAL:
#   You MUST backtest before going live. It shows you:
#     - Win rate (% of trades that were profitable)
#     - Profit factor (total wins / total losses — should be > 1.5)
#     - Max drawdown (worst losing streak — should be < 20%)
#     - Sharpe ratio (risk-adjusted returns — higher is better)
#     - Average trade duration
#
# HOW TO RUN:
#   python backtest/backtest_engine.py
#
# IMPORTANT NOTE ON BACKTESTING:
#   Past performance ≠ future results. Backtesting shows if a strategy
#   HAS WORKED in the past. It doesn't guarantee it will work in future.
#   Always forward-test on DEMO first.
# =============================================================================

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import *
from ai_engine.indicators import Indicators
from ai_engine.signal_engine import SignalEngine
from utils.logger import get_logger

log = get_logger("Backtest")


@dataclass
class BacktestTrade:
    """Represents a single trade in the backtest."""
    entry_index:   int
    symbol:        str
    direction:     str
    entry_price:   float
    stop_loss:     float
    take_profit:   float
    strategy:      str
    regime:        str
    confidence:    float
    exit_price:    float      = 0.0
    exit_index:    int        = 0
    result:        str        = ""    # "WIN", "LOSS", "OPEN"
    pnl_pips:      float      = 0.0
    pnl_pct:       float      = 0.0
    duration_bars: int        = 0


@dataclass
class BacktestResult:
    """Summary statistics for a backtest run."""
    symbol:          str
    total_trades:    int      = 0
    wins:            int      = 0
    losses:          int      = 0
    win_rate:        float    = 0.0
    profit_factor:   float    = 0.0
    max_drawdown:    float    = 0.0
    sharpe_ratio:    float    = 0.0
    total_pnl_pips:  float    = 0.0
    avg_win_pips:    float    = 0.0
    avg_loss_pips:   float    = 0.0
    avg_rr:          float    = 0.0
    trades:          List     = field(default_factory=list)
    equity_curve:    List     = field(default_factory=list)


class BacktestEngine:
    """
    Simulates the bot on historical data to measure performance.
    
    Usage:
        engine = BacktestEngine()
        result = engine.run("EURUSD", df_m15, df_h1)
        engine.print_report(result)
    """

    def __init__(self):
        self.signal_engine = SignalEngine()

    def run(self, symbol: str, df_signal: pd.DataFrame,
            df_confirm: pd.DataFrame, starting_balance: float = 400.0) -> BacktestResult:
        """
        Runs the full backtest simulation.
        
        Parameters:
            symbol           : trading symbol
            df_signal        : M15 DataFrame with indicators
            df_confirm       : H1 DataFrame with indicators
            starting_balance : simulated starting account balance
        
        Returns:
            BacktestResult with all statistics
        """
        log.info(f"Starting backtest for {symbol}...")
        log.info(f"Data range: {df_signal['time'].iloc[0]} to {df_signal['time'].iloc[-1]}")
        log.info(f"Total candles: {len(df_signal)}")

        result    = BacktestResult(symbol=symbol)
        trades    = []
        balance   = starting_balance
        equity_history = [balance]

        # Warm-up period — need enough bars for all indicators
        warmup = max(EMA_TREND, 50)

        open_trade: Optional[BacktestTrade] = None

        for i in range(warmup, len(df_signal) - 1):
            candle     = df_signal.iloc[i]
            next_candle = df_signal.iloc[i + 1]

            # ── Manage open trade ──────────────────────────────────────
            if open_trade:
                hit_sl = False
                hit_tp = False

                # Check if SL or TP was hit on this candle
                if open_trade.direction == "BUY":
                    if next_candle["low"] <= open_trade.stop_loss:
                        hit_sl = True
                        exit_price = open_trade.stop_loss
                    elif next_candle["high"] >= open_trade.take_profit:
                        hit_tp = True
                        exit_price = open_trade.take_profit
                else:  # SELL
                    if next_candle["high"] >= open_trade.stop_loss:
                        hit_sl = True
                        exit_price = open_trade.stop_loss
                    elif next_candle["low"] <= open_trade.take_profit:
                        hit_tp = True
                        exit_price = open_trade.take_profit

                if hit_sl or hit_tp:
                    # Calculate P&L
                    if open_trade.direction == "BUY":
                        pnl_pips = (exit_price - open_trade.entry_price) * 10000
                    else:
                        pnl_pips = (open_trade.entry_price - exit_price) * 10000

                    pnl_pct = pnl_pips / 100  # Simplified P&L as % of risk

                    open_trade.exit_price   = exit_price
                    open_trade.exit_index   = i
                    open_trade.pnl_pips     = pnl_pips
                    open_trade.pnl_pct      = pnl_pct
                    open_trade.duration_bars = i - open_trade.entry_index
                    open_trade.result       = "WIN" if hit_tp else "LOSS"

                    # Update balance (1% risk per trade)
                    trade_pnl_dollar = starting_balance * RISK_PER_TRADE_PCT * (
                        ATR_TP_MULTI if hit_tp else -ATR_SL_MULTI
                    )
                    balance += trade_pnl_dollar

                    trades.append(open_trade)
                    equity_history.append(balance)
                    open_trade = None

                    log.debug(f"Trade closed: {open_trade.direction if open_trade else 'N/A'} "
                              f"{'WIN' if hit_tp else 'LOSS'} | Pips: {pnl_pips:.1f}")

            # ── Look for new signal (only if no open trade) ────────────
            if open_trade is None:
                # Build context windows up to current bar
                df_s_window = df_signal.iloc[max(0, i-300):i+1].copy()
                df_c_window = self._get_confirm_window(df_confirm, candle["time"])

                if df_c_window is None or len(df_c_window) < 50:
                    continue

                signal = self.signal_engine.analyze(symbol, df_s_window, df_c_window)

                if signal and signal.confidence >= AI_MIN_CONFIDENCE:
                    open_trade = BacktestTrade(
                        entry_index  = i,
                        symbol       = symbol,
                        direction    = signal.direction,
                        entry_price  = signal.entry_price,
                        stop_loss    = signal.stop_loss,
                        take_profit  = signal.take_profit,
                        strategy     = signal.strategy,
                        regime       = signal.regime,
                        confidence   = signal.confidence,
                    )

        # ── Calculate statistics ──────────────────────────────────────
        result.trades       = trades
        result.equity_curve = equity_history
        result.total_trades = len(trades)

        if trades:
            wins   = [t for t in trades if t.result == "WIN"]
            losses = [t for t in trades if t.result == "LOSS"]

            result.wins    = len(wins)
            result.losses  = len(losses)
            result.win_rate = len(wins) / len(trades) * 100

            win_pips  = [t.pnl_pips for t in wins]
            loss_pips = [abs(t.pnl_pips) for t in losses]

            result.total_pnl_pips = sum(t.pnl_pips for t in trades)
            result.avg_win_pips   = np.mean(win_pips)   if win_pips   else 0
            result.avg_loss_pips  = np.mean(loss_pips)  if loss_pips  else 0

            total_wins_pips  = sum(win_pips)
            total_loss_pips  = sum(loss_pips)
            result.profit_factor = (total_wins_pips / total_loss_pips
                                    if total_loss_pips > 0 else 999)

            # Max drawdown
            equity = np.array(equity_history)
            rolling_max = np.maximum.accumulate(equity)
            drawdowns = (rolling_max - equity) / rolling_max * 100
            result.max_drawdown = drawdowns.max()

            # Sharpe ratio (simplified)
            returns = np.diff(equity) / equity[:-1]
            if returns.std() > 0:
                result.sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)

            result.avg_rr = np.mean([
                abs(t.take_profit - t.entry_price) / abs(t.stop_loss - t.entry_price)
                for t in trades if abs(t.stop_loss - t.entry_price) > 0
            ])

        return result

    def _get_confirm_window(self, df_confirm: pd.DataFrame, signal_time) -> Optional[pd.DataFrame]:
        """Gets the H1 DataFrame up to the given timestamp."""
        mask = df_confirm["time"] <= signal_time
        sub  = df_confirm[mask]
        return sub if len(sub) >= 50 else None

    def print_report(self, result: BacktestResult):
        """
        Prints a detailed backtest report to the console.
        
        Reading the report:
          Win Rate > 50%        = more wins than losses
          Profit Factor > 1.5   = strong edge
          Max Drawdown < 15%    = manageable losing streaks
          Sharpe Ratio > 1.0    = good risk-adjusted returns
        """
        print("\n" + "="*55)
        print(f"  BACKTEST REPORT — {result.symbol}")
        print("="*55)
        print(f"  Total Trades:   {result.total_trades}")
        print(f"  Wins:           {result.wins}  ({result.win_rate:.1f}%)")
        print(f"  Losses:         {result.losses}")
        print(f"  Profit Factor:  {result.profit_factor:.2f}  (>1.5 is good)")
        print(f"  Max Drawdown:   {result.max_drawdown:.1f}%  (<15% is good)")
        print(f"  Sharpe Ratio:   {result.sharpe_ratio:.2f}  (>1.0 is good)")
        print(f"  Total Pips:     {result.total_pnl_pips:+.1f}")
        print(f"  Avg Win:        {result.avg_win_pips:.1f} pips")
        print(f"  Avg Loss:       {result.avg_loss_pips:.1f} pips")
        print(f"  Avg R:R:        1:{result.avg_rr:.1f}")
        print("="*55)

        # Rating
        score = 0
        if result.win_rate > 50:     score += 1
        if result.profit_factor > 1.5: score += 1
        if result.max_drawdown < 15:   score += 1
        if result.sharpe_ratio > 1.0:  score += 1

        ratings = {4: "⭐⭐⭐⭐ EXCELLENT", 3: "⭐⭐⭐ GOOD",
                   2: "⭐⭐ AVERAGE", 1: "⭐ POOR", 0: "❌ DO NOT TRADE LIVE"}
        print(f"  OVERALL RATING: {ratings.get(score, 'N/A')}")
        print("="*55 + "\n")

    def save_trades_csv(self, result: BacktestResult, filename: str = None):
        """Saves all backtest trades to a CSV file for analysis."""
        if not filename:
            filename = f"logs/backtest_{result.symbol}_{datetime.now().strftime('%Y%m%d')}.csv"

        rows = []
        for t in result.trades:
            rows.append({
                "symbol":     t.symbol,
                "direction":  t.direction,
                "entry":      t.entry_price,
                "sl":         t.stop_loss,
                "tp":         t.take_profit,
                "exit":       t.exit_price,
                "result":     t.result,
                "pnl_pips":   round(t.pnl_pips, 1),
                "strategy":   t.strategy,
                "regime":     t.regime,
                "confidence": t.confidence,
                "duration":   t.duration_bars,
            })

        df = pd.DataFrame(rows)
        os.makedirs("logs", exist_ok=True)
        df.to_csv(filename, index=False)
        log.info(f"Backtest trades saved to {filename}")
        return filename

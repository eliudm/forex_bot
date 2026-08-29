"""
=============================================================
  BACKTESTING ENGINE
=============================================================
  PURPOSE: Test your strategy on HISTORICAL data before
  risking real money. 

  WHY BACKTEST?
  Before trading live, you want to know:
  - What is the win rate? (e.g., 65%)
  - What is the average profit per trade?
  - What is the maximum drawdown? (worst losing streak)
  - What is the Sharpe ratio? (profit vs risk measure)

  HOW TO RUN:
      python backtest/backtester.py

  OUTPUT:
  - Prints a full performance report
  - Saves results to logs/backtest_results.csv
  - Prints equity curve data
=============================================================
"""

import pandas as pd
import numpy as np
import sys
import os
import logging
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_engine.indicators     import IndicatorEngine
from ai_engine.strategy_engine import AIStrategyEngine

logger = logging.getLogger(__name__)


class Backtester:
    """
    Simulates trading on historical data to measure strategy performance.
    
    HOW TO USE:
        bt = Backtester(symbol="XAUUSD", initial_balance=500)
        bt.load_data(df)               # Load historical OHLCV data
        results = bt.run()             # Run the simulation
        bt.print_report(results)       # Print the performance report
    """

    def __init__(self, symbol: str, initial_balance: float = 500,
                 risk_pct: float = 0.01, min_confidence: float = 0.45):
        # NOTE: 0.45, not the ~0.65 the live bot defaults to. A model trained on
        # a few hundred candles of synthetic/random-walk data rarely reaches
        # 65%+ confidence, which made backtests silently produce zero trades.
        # Live trading should still use a stricter threshold (config/settings.py).
        self.symbol          = symbol
        self.initial_balance = initial_balance
        self.risk_pct        = risk_pct
        self.min_confidence  = min_confidence
        self.indicators      = IndicatorEngine()
        self.ai_engine       = AIStrategyEngine(symbol)
        self.df              = None

    def load_data(self, df: pd.DataFrame):
        """
        Load the historical OHLCV data to backtest on.
        The DataFrame must have columns: time, open, high, low, close, volume
        """
        self.df = df.copy()
        logger.info(f"Loaded {len(df)} candles for backtesting {self.symbol}")

    def run(self, train_pct: float = 0.7) -> dict:
        """
        Runs the backtest simulation.
        
        HOW IT WORKS:
        1. Splits data into TRAIN (70%) and TEST (30%) sets
           (This is important! We can't test on the same data we trained on)
        2. Trains AI on the train set
        3. Simulates trading on the test set, candle by candle
        4. Records every trade (entry, exit, profit/loss)
        5. Calculates performance metrics
        
        PARAMETERS:
            train_pct - What fraction of data to use for training (default: 70%)
        
        RETURNS:
            dict with all performance metrics
        """
        if self.df is None:
            logger.error("No data loaded. Call load_data() first.")
            return {}

        # Add indicators to full dataset
        df = self.indicators.add_all(self.df)

        # Split into train and test
        split_idx  = int(len(df) * train_pct)
        train_df   = df.iloc[:split_idx].copy()
        test_df    = df.iloc[split_idx:].copy()

        logger.info(f"Train: {len(train_df)} candles | Test: {len(test_df)} candles")

        # Train the AI on historical data
        train_result = self.ai_engine.train(train_df)
        if not train_result.get("success"):
            logger.error("Training failed during backtest.")
            return {}

        # ── SIMULATION LOOP ────────────────────────────────────────
        balance       = self.initial_balance
        equity_curve  = [balance]
        trades        = []
        open_trade    = None   # Only allow 1 open trade at a time for simplicity
        pip_size      = self._get_pip_size()

        # Use a rolling window: look at the last 150 candles to predict the next
        window = 150

        for i in range(window, len(test_df)):
            candle   = test_df.iloc[i]
            window_df = test_df.iloc[i - window : i].copy()

            # ── Check if open trade should close ──────────────────
            if open_trade is not None:
                high = candle['high']
                low  = candle['low']

                hit_tp = (open_trade['direction'] == "BUY"  and high >= open_trade['tp']) or \
                         (open_trade['direction'] == "SELL" and low  <= open_trade['tp'])

                hit_sl = (open_trade['direction'] == "BUY"  and low  <= open_trade['sl']) or \
                         (open_trade['direction'] == "SELL" and high >= open_trade['sl'])

                if hit_tp or hit_sl:
                    # Calculate P&L
                    if hit_tp:
                        pnl = open_trade['tp_pnl']
                        result = "WIN"
                    else:
                        pnl = -open_trade['risk_amount']
                        result = "LOSS"

                    balance += pnl
                    open_trade['exit_time']  = candle['time']
                    open_trade['exit_price'] = open_trade['tp'] if hit_tp else open_trade['sl']
                    open_trade['pnl']        = pnl
                    open_trade['result']     = result
                    trades.append(open_trade)
                    open_trade = None

                equity_curve.append(balance)
                continue   # Don't open a new trade on same candle we closed

            # ── Generate signal for this candle ───────────────────
            signal = self.ai_engine.predict(window_df, self.min_confidence)

            if signal['action'] in ("BUY", "SELL"):
                entry_price = candle['close']
                atr         = candle.get('atr', candle['close'] * 0.001)
                risk_amount = balance * self.risk_pct
                sl          = signal['sl']
                tp          = signal['tp']
                sl_dist     = abs(entry_price - sl)
                tp_dist     = abs(entry_price - tp)
                tp_pnl      = risk_amount * (tp_dist / sl_dist) if sl_dist > 0 else 0

                open_trade = {
                    "symbol":      self.symbol,
                    "direction":   signal['action'],
                    "entry_time":  candle['time'],
                    "entry_price": entry_price,
                    "sl":          sl,
                    "tp":          tp,
                    "risk_amount": risk_amount,
                    "tp_pnl":      tp_pnl,
                    "confidence":  signal['confidence'],
                    "regime":      signal.get('regime', 'N/A')
                }

            equity_curve.append(balance)

        # Close any trade still open at end of test
        if open_trade is not None:
            last_price = test_df.iloc[-1]['close']
            pnl = (last_price - open_trade['entry_price']) * (1 if open_trade['direction'] == "BUY" else -1)
            pnl = (pnl / abs(open_trade['entry_price'] - open_trade['sl'])) * open_trade['risk_amount']
            open_trade['pnl']    = round(pnl, 2)
            open_trade['result'] = "WIN" if pnl > 0 else "LOSS"
            trades.append(open_trade)

        # ── CALCULATE METRICS ──────────────────────────────────────
        return self._calculate_metrics(trades, equity_curve)

    def _calculate_metrics(self, trades: list, equity_curve: list) -> dict:
        """Calculates all performance statistics from the trade list."""
        if not trades:
            return {"error": "No trades generated during backtest."}

        pnls      = [t['pnl'] for t in trades]
        wins      = [p for p in pnls if p > 0]
        losses    = [p for p in pnls if p <= 0]
        total_pnl = sum(pnls)

        # Win rate
        win_rate  = len(wins) / len(pnls)

        # Profit factor = Total wins / Total losses
        total_win  = sum(wins)
        total_loss = abs(sum(losses))
        profit_factor = total_win / total_loss if total_loss > 0 else float('inf')

        # Max drawdown
        peak = self.initial_balance
        max_dd = 0
        running = self.initial_balance
        for pnl in pnls:
            running += pnl
            peak = max(peak, running)
            dd   = (peak - running) / peak
            max_dd = max(max_dd, dd)

        # Sharpe ratio (simplified, assumes risk-free rate = 0)
        if len(pnls) > 1:
            avg_pnl  = np.mean(pnls)
            std_pnl  = np.std(pnls)
            sharpe   = (avg_pnl / std_pnl) * np.sqrt(252) if std_pnl > 0 else 0
        else:
            sharpe = 0

        final_balance = self.initial_balance + total_pnl
        total_return  = (final_balance - self.initial_balance) / self.initial_balance

        return {
            "symbol":           self.symbol,
            "initial_balance":  self.initial_balance,
            "final_balance":    round(final_balance, 2),
            "total_return_pct": round(total_return * 100, 2),
            "total_pnl":        round(total_pnl, 2),
            "total_trades":     len(trades),
            "wins":             len(wins),
            "losses":           len(losses),
            "win_rate":         round(win_rate * 100, 2),
            "profit_factor":    round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "sharpe_ratio":     round(sharpe, 2),
            "avg_win":          round(np.mean(wins), 2)    if wins   else 0,
            "avg_loss":         round(np.mean(losses), 2)  if losses else 0,
            "best_trade":       round(max(pnls), 2),
            "worst_trade":      round(min(pnls), 2),
            "trades":           trades
        }

    def print_report(self, results: dict):
        """Prints a formatted performance report to the console."""
        if "error" in results:
            print(f"\n❌ Backtest Error: {results['error']}")
            return

        print("\n" + "="*55)
        print(f"  📊 BACKTEST RESULTS — {results['symbol']}")
        print("="*55)
        print(f"  Initial Balance : ${results['initial_balance']:,.2f}")
        print(f"  Final Balance   : ${results['final_balance']:,.2f}")
        print(f"  Total Return    : {results['total_return_pct']:+.2f}%")
        print(f"  Total P&L       : ${results['total_pnl']:+,.2f}")
        print("─"*55)
        print(f"  Total Trades    : {results['total_trades']}")
        print(f"  Wins            : {results['wins']}")
        print(f"  Losses          : {results['losses']}")
        print(f"  Win Rate        : {results['win_rate']:.1f}%")
        print("─"*55)
        print(f"  Profit Factor   : {results['profit_factor']:.2f}  (>1.5 is good)")
        print(f"  Sharpe Ratio    : {results['sharpe_ratio']:.2f}  (>1.0 is good)")
        print(f"  Max Drawdown    : {results['max_drawdown_pct']:.2f}%  (<15% is safe)")
        print("─"*55)
        print(f"  Avg Win         : ${results['avg_win']:,.2f}")
        print(f"  Avg Loss        : ${results['avg_loss']:,.2f}")
        print(f"  Best Trade      : ${results['best_trade']:,.2f}")
        print(f"  Worst Trade     : ${results['worst_trade']:,.2f}")
        print("="*55 + "\n")

    def _get_pip_size(self) -> float:
        if "JPY" in self.symbol: return 0.01
        if "XAU" in self.symbol: return 0.1
        if "Index" in self.symbol: return 0.01
        return 0.0001

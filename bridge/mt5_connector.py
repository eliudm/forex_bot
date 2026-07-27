# ============================================================
# bridge/mt5_connector.py — Connects Python to MetaTrader 5
# ============================================================
# WHAT THIS FILE DOES:
#   MetaTrader 5 is where your trades are executed.
#   Python is where the AI brain lives.
#   This file is the "bridge" between them.
#
#   It can:
#     - Connect/disconnect from your Deriv MT5 account
#     - Fetch live price data (candles/bars)
#     - Get your account balance and open positions
#     - Place BUY and SELL orders
#     - Modify stop loss and take profit
#     - Close trades
#
# HOW TO INSTALL MT5 PYTHON LIBRARY:
#   pip install MetaTrader5
# ============================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import logging
import pandas as pd
from datetime import datetime

# Try to import MetaTrader5; gracefully fail if not installed yet
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("⚠️  MetaTrader5 library not installed. Run: pip install MetaTrader5")
    print("   Note: MT5 Python library only works on Windows.")

from config.config import (
    MT5_LOGIN, MT5_PASSWORD, MT5_SERVER,
    MIN_LOT_SIZE, MAX_LOT_SIZE,
    RISK_PER_TRADE_PCT, ACCOUNT_BALANCE
)

logger = logging.getLogger(__name__)

# ── TIMEFRAME MAPPING ────────────────────────────────────────
# MT5 uses special constants for timeframes. This maps our
# human-readable names to those constants.
TF_MAP = {
    "M1":  mt5.TIMEFRAME_M1  if MT5_AVAILABLE else 1,
    "M5":  mt5.TIMEFRAME_M5  if MT5_AVAILABLE else 5,
    "M15": mt5.TIMEFRAME_M15 if MT5_AVAILABLE else 15,
    "H1":  mt5.TIMEFRAME_H1  if MT5_AVAILABLE else 60,
    "H4":  mt5.TIMEFRAME_H4  if MT5_AVAILABLE else 240,
    "D1":  mt5.TIMEFRAME_D1  if MT5_AVAILABLE else 1440,
}


class MT5Connector:
    """
    Handles all communication between Python and MetaTrader 5.

    USAGE EXAMPLE:
        conn = MT5Connector()
        if conn.connect():
            df = conn.get_candles("EURUSD", "M15", 200)
            print(df.tail())
            conn.disconnect()
    """

    def __init__(self):
        self.connected = False

    # ── CONNECTION ───────────────────────────────────────────

    def connect(self) -> bool:
        """
        Connect to your Deriv MT5 account.
        Returns True if successful, False otherwise.
        """
        if not MT5_AVAILABLE:
            logger.error("MetaTrader5 library not installed.")
            return False

        # Initialize the MT5 terminal
        if not mt5.initialize():
            logger.error(f"MT5 initialize() failed. Error: {mt5.last_error()}")
            return False

        # Log in with your Deriv credentials
        if MT5_LOGIN and MT5_PASSWORD:
            authorized = mt5.login(
                login=MT5_LOGIN,
                password=MT5_PASSWORD,
                server=MT5_SERVER
            )
            if not authorized:
                logger.error(f"MT5 login failed. Error: {mt5.last_error()}")
                mt5.shutdown()
                return False

        self.connected = True
        info = mt5.account_info()
        logger.info(f"✅ Connected to MT5 | Account: {info.login} | Balance: ${info.balance:.2f}")
        return True

    def disconnect(self):
        """Cleanly disconnect from MT5."""
        if MT5_AVAILABLE and self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5.")

    # ── MARKET DATA ──────────────────────────────────────────

    def get_candles(self, symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
        """
        Fetch historical OHLCV candle data for a symbol.

        Parameters:
            symbol    : e.g. "EURUSD", "XAUUSD", "Volatility 75 Index"
            timeframe : e.g. "M15", "H1"
            count     : number of candles to fetch (200 = last 200 candles)

        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        if not self.connected:
            logger.warning("Not connected to MT5.")
            return pd.DataFrame()

        tf = TF_MAP.get(timeframe, mt5.TIMEFRAME_M15)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)

        if rates is None or len(rates) == 0:
            logger.error(f"No candle data for {symbol} {timeframe}. Error: {mt5.last_error()}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        df = df[["time", "open", "high", "low", "close", "volume"]]
        return df

    def get_current_price(self, symbol: str) -> dict:
        """
        Get the current live bid/ask price for a symbol.
        Returns dict with 'bid', 'ask', 'spread'
        """
        if not self.connected:
            return {}
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {}
        spread_pips = round((tick.ask - tick.bid) * 10000, 1)
        return {
            "bid":    tick.bid,
            "ask":    tick.ask,
            "spread": spread_pips,
            "time":   datetime.fromtimestamp(tick.time)
        }

    def get_symbol_info(self, symbol: str) -> dict:
        """Get symbol details like pip size, contract size, digits."""
        if not self.connected:
            return {}
        info = mt5.symbol_info(symbol)
        if info is None:
            return {}
        return {
            "digits":        info.digits,
            "point":         info.point,
            "trade_contract_size": info.trade_contract_size,
            "volume_min":    info.volume_min,
            "volume_max":    info.volume_max,
            "volume_step":   info.volume_step,
        }

    # ── ACCOUNT INFO ─────────────────────────────────────────

    def get_account_info(self) -> dict:
        """
        Get your current account balance, equity, and margin.
        Equity = balance + unrealised profit/loss of open trades.
        """
        if not self.connected:
            return {}
        info = mt5.account_info()
        if info is None:
            return {}
        return {
            "balance":    info.balance,
            "equity":     info.equity,
            "margin":     info.margin,
            "free_margin":info.margin_free,
            "profit":     info.profit,
            "currency":   info.currency,
            "leverage":   info.leverage,
        }

    def get_open_positions(self) -> list:
        """
        Returns a list of all currently open trade positions.
        Each entry is a dict with symbol, type, volume, profit, sl, tp.
        """
        if not self.connected:
            return []
        positions = mt5.positions_get()
        if positions is None:
            return []
        result = []
        for p in positions:
            result.append({
                "ticket":  p.ticket,
                "symbol":  p.symbol,
                "type":    "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume":  p.volume,
                "open_price": p.price_open,
                "sl":      p.sl,
                "tp":      p.tp,
                "profit":  p.profit,
                "comment": p.comment,
            })
        return result

    # ── ORDER PLACEMENT ──────────────────────────────────────

    def calculate_lot_size(self, symbol: str, sl_pips: float, risk_pct: float = None) -> float:
        """
        Calculate the correct lot size based on your risk settings.

        EXPLANATION:
          Lot Size = (Account Balance × Risk%) / (Stop Loss in Pips × Pip Value)

          Example on $500 account:
            - Risk 1% = $5
            - Stop loss = 20 pips
            - Pip value for 0.01 lot EURUSD ≈ $0.10
            - Lot = $5 / (20 × $0.10) = 0.25 lots  → capped to MAX_LOT_SIZE
        """
        if not self.connected:
            return MIN_LOT_SIZE

        acct = self.get_account_info()
        balance = acct.get("balance", ACCOUNT_BALANCE)
        risk_pct = risk_pct or RISK_PER_TRADE_PCT
        risk_amount = balance * risk_pct           # e.g. $5

        sym_info = self.get_symbol_info(symbol)
        if not sym_info:
            return MIN_LOT_SIZE

        # Pip value per 0.01 lot (rough universal approximation)
        pip_value_per_micro = sym_info["point"] * sym_info["trade_contract_size"] * 0.01 * 10

        if pip_value_per_micro <= 0 or sl_pips <= 0:
            return MIN_LOT_SIZE

        lots = risk_amount / (sl_pips * pip_value_per_micro / 0.01)
        # Round to allowed step size
        step = sym_info.get("volume_step", 0.01)
        lots = round(round(lots / step) * step, 2)
        # Enforce limits
        lots = max(MIN_LOT_SIZE, min(MAX_LOT_SIZE, lots))
        return lots

    def place_order(self, symbol: str, direction: str, lot_size: float,
                    sl_price: float, tp_price: float, comment: str = "AIBot") -> dict:
        """
        Place a market order (BUY or SELL).

        Parameters:
            symbol    : Trading symbol, e.g. "EURUSD"
            direction : "BUY" or "SELL"
            lot_size  : Trade volume in lots
            sl_price  : Stop loss price (absolute price, not pips)
            tp_price  : Take profit price (absolute price)
            comment   : Label for the trade in MT5

        Returns dict with success status and order ticket number.
        """
        if not self.connected:
            return {"success": False, "error": "Not connected"}

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"success": False, "error": f"Cannot get price for {symbol}"}

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        price      = tick.ask if direction == "BUY" else tick.bid

        request = {
            "action":        mt5.TRADE_ACTION_DEAL,
            "symbol":        symbol,
            "volume":        lot_size,
            "type":          order_type,
            "price":         price,
            "sl":            sl_price,
            "tp":            tp_price,
            "deviation":     20,           # Max slippage in points
            "magic":         20240101,     # Unique ID to identify bot trades
            "comment":       comment,
            "type_time":     mt5.ORDER_TIME_GTC,
            "type_filling":  mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed: {result.comment} (code {result.retcode})")
            return {"success": False, "error": result.comment, "retcode": result.retcode}

        logger.info(f"✅ Order placed: {direction} {lot_size} {symbol} @ {price} | Ticket: {result.order}")
        return {
            "success": True,
            "ticket":  result.order,
            "price":   price,
            "volume":  lot_size,
            "sl":      sl_price,
            "tp":      tp_price,
        }

    def close_position(self, ticket: int) -> bool:
        """Close an open position by its ticket number."""
        if not self.connected:
            return False

        position = mt5.positions_get(ticket=ticket)
        if not position:
            logger.warning(f"Position {ticket} not found.")
            return False

        pos = position[0]
        close_type  = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        close_price = mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(pos.symbol).ask

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       pos.volume,
            "type":         close_type,
            "position":     ticket,
            "price":        close_price,
            "deviation":    20,
            "magic":        20240101,
            "comment":      "AIBot_Close",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        success = result.retcode == mt5.TRADE_RETCODE_DONE
        if success:
            logger.info(f"✅ Closed position {ticket}")
        else:
            logger.error(f"Failed to close {ticket}: {result.comment}")
        return success

    def modify_sl_tp(self, ticket: int, new_sl: float, new_tp: float = None) -> bool:
        """Modify the stop loss (and optionally take profit) of an open position."""
        if not self.connected:
            return False

        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False
        pos = position[0]

        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   pos.symbol,
            "sl":       new_sl,
            "tp":       new_tp if new_tp else pos.tp,
            "position": ticket,
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE

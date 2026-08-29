"""
=============================================================
  MT5 BRIDGE MODULE
=============================================================
  PURPOSE: This file connects your Python AI engine to
  the Deriv MT5 platform. Think of it as the "phone line"
  between your AI brain and the actual trading platform.

  WHAT IT DOES:
  1. Logs into your Deriv MT5 account
  2. Downloads live price data (candles)
  3. Sends trade orders (buy/sell)
  4. Checks your open positions
  5. Closes trades when needed

  HOW TO USE:
  You don't run this file directly. 
  It is imported and used by the main bot engine.
=============================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import sys
import os

# Add parent folder to path so we can import settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

# Set up logging - this creates readable log messages
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
#  TIMEFRAME CONVERTER
#  MT5 uses numbers for timeframes, not text like "H1"
#  This dictionary converts human-readable text to MT5 numbers
# ─────────────────────────────────────────────────────────────────
TIMEFRAME_MAP = {
    "M1":  mt5.TIMEFRAME_M1,    # 1-minute candles
    "M5":  mt5.TIMEFRAME_M5,    # 5-minute candles
    "M15": mt5.TIMEFRAME_M15,   # 15-minute candles
    "M30": mt5.TIMEFRAME_M30,   # 30-minute candles
    "H1":  mt5.TIMEFRAME_H1,    # 1-hour candles  (recommended)
    "H4":  mt5.TIMEFRAME_H4,    # 4-hour candles
    "D1":  mt5.TIMEFRAME_D1,    # Daily candles
}


class MT5Bridge:
    """
    This class handles ALL communication with Deriv MT5.
    
    HOW TO USE:
        bridge = MT5Bridge()          # Create the bridge
        bridge.connect()              # Log in to MT5
        data = bridge.get_candles("XAUUSD", "H1", 200)  # Get price data
        bridge.disconnect()           # Log out when done
    """

    MAGIC = 20240101

    def __init__(self):
        self.connected = False
        self._last_history_check = datetime.now()
        logger.info("MT5Bridge created. Call connect() to log in.")

    # ─────────────────────────────────────────
    #  ADVANCE / DETECT CLOSED TRADES
    #  Called once per scan cycle by the bot loop. Live prices move on
    #  their own, so this only needs to check for trades that closed
    #  (hit SL/TP or were closed manually) since the last check.
    # ─────────────────────────────────────────
    def tick(self):
        pass

    def get_closed_trades(self) -> list:
        """Returns trades (placed by this bot, via magic number) closed since the last call."""
        now = datetime.now()
        deals = mt5.history_deals_get(self._last_history_check, now)
        self._last_history_check = now

        if not deals:
            return []

        closures = []
        for d in deals:
            if d.magic != self.MAGIC or d.entry != 1:  # entry==1 -> DEAL_ENTRY_OUT (closing deal)
                continue
            closures.append({
                "ticket":     d.position_id,
                "symbol":     d.symbol,
                "direction":  "SELL" if d.type == mt5.ORDER_TYPE_BUY else "BUY",  # closing side is inverse
                "profit":     round(d.profit, 2),
                "exit_price": d.price,
                "reason":     "TP/SL/MANUAL",
            })
        return closures

    # ─────────────────────────────────────────
    #  CONNECT TO MT5
    # ─────────────────────────────────────────
    def connect(self) -> bool:
        """
        Logs into your Deriv MT5 account.
        Returns True if successful, False if it failed.
        """
        logger.info("Connecting to Deriv MT5...")

        # Step 1: Initialize the MT5 application
        if not mt5.initialize():
            logger.error(f"MT5 initialize() failed. Error: {mt5.last_error()}")
            logger.error("SOLUTION: Make sure MetaTrader 5 is installed and running on your computer.")
            return False

        # Step 2: Log in with your credentials from settings.py
        login_result = mt5.login(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER
        )

        if not login_result:
            logger.error(f"MT5 login failed. Error: {mt5.last_error()}")
            logger.error("SOLUTION: Check MT5_LOGIN, MT5_PASSWORD, and MT5_SERVER in config/settings.py")
            return False

        # Step 3: Confirm connection and show account info
        account = mt5.account_info()
        logger.info(f"✅ Connected to Deriv MT5 successfully!")
        logger.info(f"   Account: {account.login} | Balance: ${account.balance:.2f} | Server: {account.server}")

        self.connected = True
        return True

    # ─────────────────────────────────────────
    #  DISCONNECT FROM MT5
    # ─────────────────────────────────────────
    def disconnect(self):
        """Safely logs out of MT5."""
        mt5.shutdown()
        self.connected = False
        logger.info("Disconnected from MT5.")

    # ─────────────────────────────────────────
    #  GET PRICE CANDLES (OHLCV DATA)
    # ─────────────────────────────────────────
    def get_candles(self, symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
        """
        Downloads historical price candles for a symbol.
        
        PARAMETERS:
            symbol    - The market to get data for (e.g., "XAUUSD", "EURUSD")
            timeframe - The candle size (e.g., "H1" for 1-hour candles)
            count     - How many candles to download (200 = last 200 candles)
        
        RETURNS:
            A table (DataFrame) with columns: time, open, high, low, close, volume
            Returns None if something goes wrong.
        
        EXAMPLE:
            data = bridge.get_candles("XAUUSD", "H1", 200)
            print(data.tail(5))  # Show last 5 candles
        """
        if not self.connected:
            logger.error("Not connected to MT5. Call connect() first.")
            return None

        # Convert timeframe string to MT5 number
        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            logger.error(f"Unknown timeframe '{timeframe}'. Use: M1, M5, M15, M30, H1, H4, D1")
            return None

        # Download the candles from MT5
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)

        if rates is None or len(rates) == 0:
            logger.error(f"No data received for {symbol} on {timeframe}.")
            logger.error("SOLUTION: Make sure the symbol is available in your Deriv MT5 Market Watch.")
            return None

        # Convert to a clean table format
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')  # Convert timestamps to readable dates
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]

        logger.debug(f"Downloaded {len(df)} candles for {symbol} {timeframe}")
        return df

    # ─────────────────────────────────────────
    #  GET CURRENT PRICE
    # ─────────────────────────────────────────
    def get_price(self, symbol: str) -> dict:
        """
        Gets the current live bid/ask price for a symbol.
        
        RETURNS a dict like: {"bid": 1.0850, "ask": 1.0852, "spread": 0.0002}
        """
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Could not get price for {symbol}")
            return None

        spread = tick.ask - tick.bid
        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": round(spread, 5),
            "time": datetime.fromtimestamp(tick.time)
        }

    # ─────────────────────────────────────────
    #  GET ACCOUNT INFO
    # ─────────────────────────────────────────
    def get_account(self) -> dict:
        """
        Returns your current account details.
        
        RETURNS a dict with: balance, equity, profit, margin_free
        """
        info = mt5.account_info()
        if info is None:
            return None

        return {
            "balance":     info.balance,
            "equity":      info.equity,
            "profit":      info.profit,
            "margin_free": info.margin_free,
            "currency":    info.currency,
            "leverage":    info.leverage
        }

    # ─────────────────────────────────────────
    #  CALCULATE LOT SIZE
    # ─────────────────────────────────────────
    def calculate_lot_size(self, symbol: str, sl_pips: float, risk_pct: float, balance: float) -> float:
        """
        Calculates the correct lot size so you never risk more than risk_pct% per trade.
        
        FORMULA:
            Lot = (Balance x Risk%) / (SL in pips x Pip Value)
        
        EXAMPLE:
            $500 balance, 1% risk, 20 pip stop loss on EURUSD
            Lot = ($500 x 0.01) / (20 x $10) = 0.025 lots
        """
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error(f"Symbol info not found for {symbol}")
            return 0.01  # Minimum fallback

        risk_amount = balance * risk_pct          # e.g., $500 * 0.01 = $5
        pip_value   = info.trade_tick_value        # Value of 1 pip in USD
        
        if pip_value == 0 or sl_pips == 0:
            return info.volume_min                 # Return minimum lot

        lot = risk_amount / (sl_pips * pip_value)
        
        # Round to broker's allowed lot step
        lot_step = info.volume_step
        lot = round(round(lot / lot_step) * lot_step, 2)

        # Clamp between min and max allowed lots
        lot = max(info.volume_min, min(info.volume_max, lot))

        logger.info(f"Calculated lot size for {symbol}: {lot} lots (Risk: ${risk_amount:.2f}, SL: {sl_pips} pips)")
        return lot

    # ─────────────────────────────────────────
    #  PLACE A TRADE
    # ─────────────────────────────────────────
    def place_trade(self, symbol: str, direction: str, lot: float,
                    sl: float, tp: float, comment: str = "AI_BOT") -> dict:
        """
        Places a BUY or SELL trade on MT5.
        
        PARAMETERS:
            symbol    - Market to trade (e.g., "XAUUSD")
            direction - "BUY" or "SELL"
            lot       - Lot size (from calculate_lot_size)
            sl        - Stop Loss price (where to exit if trade goes wrong)
            tp        - Take Profit price (where to exit when trade wins)
            comment   - Label for the trade in MT5
        
        RETURNS: dict with result info, or None if failed
        """
        price_info = self.get_price(symbol)
        if price_info is None:
            return None

        # Choose correct price and order type based on direction
        if direction == "BUY":
            price      = price_info["ask"]
            order_type = mt5.ORDER_TYPE_BUY
        else:
            price      = price_info["bid"]
            order_type = mt5.ORDER_TYPE_SELL

        # Build the trade request
        request = {
            "action":      mt5.TRADE_ACTION_DEAL,
            "symbol":      symbol,
            "volume":      lot,
            "type":        order_type,
            "price":       price,
            "sl":          sl,
            "tp":          tp,
            "deviation":   10,               # Allow up to 10 points slippage
            "magic":       self.MAGIC,         # Unique ID to identify our bot's trades
            "comment":     comment,
            "type_time":   mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        # Send the order
        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_code = result.retcode if result else "None"
            logger.error(f"Trade FAILED for {symbol} {direction}. Error code: {error_code}")
            return None

        logger.info(f"✅ Trade PLACED: {direction} {lot} lots of {symbol} @ {price} | SL: {sl} | TP: {tp}")
        return {
            "ticket":    result.order,
            "symbol":    symbol,
            "direction": direction,
            "lot":       lot,
            "price":     price,
            "sl":        sl,
            "tp":        tp,
            "time":      datetime.now()
        }

    # ─────────────────────────────────────────
    #  GET OPEN POSITIONS
    # ─────────────────────────────────────────
    def get_open_positions(self, symbol: str = None) -> list:
        """
        Returns a list of all currently open trades.
        Optionally filter by symbol.
        """
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        result = []
        for p in positions:
            result.append({
                "ticket":    p.ticket,
                "symbol":    p.symbol,
                "direction": "BUY" if p.type == 0 else "SELL",
                "lot":       p.volume,
                "open_price": p.price_open,
                "sl":        p.sl,
                "tp":        p.tp,
                "profit":    p.profit,
                "open_time": datetime.fromtimestamp(p.time)
            })
        return result

    # ─────────────────────────────────────────
    #  CLOSE A TRADE
    # ─────────────────────────────────────────
    def close_trade(self, ticket: int) -> bool:
        """
        Closes an open trade by its ticket number.
        Returns True if closed successfully.
        """
        position = mt5.positions_get(ticket=ticket)
        if not position:
            logger.error(f"Position {ticket} not found.")
            return False

        pos = position[0]
        price_info = self.get_price(pos.symbol)

        # Reverse the direction to close
        if pos.type == mt5.ORDER_TYPE_BUY:
            close_type  = mt5.ORDER_TYPE_SELL
            close_price = price_info["bid"]
        else:
            close_type  = mt5.ORDER_TYPE_BUY
            close_price = price_info["ask"]

        request = {
            "action":    mt5.TRADE_ACTION_DEAL,
            "symbol":    pos.symbol,
            "volume":    pos.volume,
            "type":      close_type,
            "position":  ticket,
            "price":     close_price,
            "deviation": 10,
            "magic":     self.MAGIC,
            "comment":   "AI_BOT_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"✅ Trade {ticket} closed successfully.")
            return True
        else:
            logger.error(f"Failed to close trade {ticket}. Error: {result.retcode if result else 'None'}")
            return False

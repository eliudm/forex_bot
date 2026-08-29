# =============================================================================
# bridge/paper_broker.py — Simulated Broker (Paper Trading)
# =============================================================================
# PURPOSE: Implements the exact same interface as MT5Bridge, but backed by
# a synthetic, self-generating price feed instead of a real MT5 terminal.
#
# WHY THIS EXISTS:
#   The bot needs a broker to talk to. A real Deriv MT5 account requires
#   installing MetaTrader5, opening an account, and keeping the terminal
#   running. None of that is needed to prove the trading/risk/AI pipeline
#   actually works end-to-end — this class lets you run the full bot loop
#   immediately, with a simulated account, on synthetic price data.
#
#   This is clearly-labeled paper trading, not a live market feed. Switch
#   BROKER_MODE to "MT5" in config/settings.py (and set MT5_* in .env) to
#   trade a real Deriv demo/live account through bridge/mt5_bridge.py,
#   which implements the same methods.
# =============================================================================

import json
import os
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from utils.market_specs import pip_size as _pip_size

logger = logging.getLogger(__name__)

STATE_FILE = "logs/paper_broker_state.json"

# (starting price, per-bar volatility) used to seed each symbol's random walk
SYMBOL_PROFILES = {
    "EURUSD": (1.0850, 0.0004), "GBPUSD": (1.2700, 0.0005), "USDJPY": (149.50, 0.05),
    "USDCHF": (0.8800, 0.0004), "AUDUSD": (0.6600, 0.0005), "USDCAD": (1.3600, 0.0004),
    "NZDUSD": (0.6100, 0.0005), "EURGBP": (0.8550, 0.0003), "EURJPY": (162.00, 0.05),
    "GBPJPY": (190.00, 0.08),
    "XAUUSD": (2350.0, 2.5), "XAGUSD": (28.0, 0.08), "XTIUSD": (78.0, 0.3),
    "BTCUSD": (65000.0, 250.0), "ETHUSD": (3400.0, 25.0),
}
DEFAULT_PROFILE = (1000.0, 4.0)

# Approximate $ value of one pip per lot, used to size paper positions.
# Real broker/lot-step math is handled by MT5Bridge when BROKER_MODE=MT5.
PIP_VALUE_PER_LOT = {
    "JPY": 9.0, "XAU": 1.0, "XAG": 5.0, "XTI": 1.0,
    "BTC": 1.0, "ETH": 1.0, "Index": 1.0,
}
DEFAULT_PIP_VALUE_PER_LOT = 10.0


def _profile(symbol: str):
    if symbol in SYMBOL_PROFILES:
        return SYMBOL_PROFILES[symbol]
    if "Index" in symbol:
        seed = sum(ord(c) for c in symbol)
        base = 500 + (seed % 8000)
        return (float(base), base * 0.004)
    return DEFAULT_PROFILE


def _pip_value_per_lot(symbol: str) -> float:
    for key, val in PIP_VALUE_PER_LOT.items():
        if key in symbol:
            return val
    return DEFAULT_PIP_VALUE_PER_LOT


class _SymbolFeed:
    """A deterministic-seed, ever-advancing synthetic OHLCV series for one symbol."""

    def __init__(self, symbol: str, seed_bars: int = 1500):
        self.symbol = symbol
        base, vol = _profile(symbol)
        seed = abs(hash(symbol)) % (2 ** 32)
        self.rng = np.random.default_rng(seed)
        self.price = base
        self.vol = vol
        self.bar_time = datetime.now() - timedelta(hours=seed_bars)
        self.bars = []
        self._advance(seed_bars)

    def _advance(self, n: int):
        for _ in range(n):
            drift = self.rng.normal(0, 1) * self.vol * 0.05
            o = self.price
            new_close_guess = max(o + drift, self.vol)
            spread = self.vol * 0.3
            h = max(o, new_close_guess) + abs(self.rng.normal(0, spread))
            l = min(o, new_close_guess) - abs(self.rng.normal(0, spread))
            l = max(l, self.vol * 0.01)
            c = l + self.rng.uniform(0, 1) * (h - l)
            self.price = c
            self.bar_time += timedelta(hours=1)
            self.bars.append({
                "time": self.bar_time, "open": o, "high": h, "low": l, "close": c,
                "volume": float(self.rng.integers(100, 5000)),
            })

    def tick(self):
        """Advance the feed by exactly one bar (one simulated hour)."""
        self._advance(1)
        return self.bars[-1]

    def candles(self, count: int) -> pd.DataFrame:
        return pd.DataFrame(self.bars[-count:]).reset_index(drop=True)

    def price_info(self) -> dict:
        last = self.bars[-1]
        spread = self.vol * 0.15
        return {
            "bid": round(last["close"] - spread / 2, 5),
            "ask": round(last["close"] + spread / 2, 5),
            "spread": round(spread, 5),
            "time": last["time"],
        }


class PaperBroker:
    """
    Simulated broker with the same public interface as MT5Bridge:
    connect, disconnect, get_candles, get_price, get_account,
    calculate_lot_size, place_trade, get_open_positions, close_trade,
    plus tick()/get_closed_trades() used to advance simulated time and
    detect SL/TP fills.

    HOW TO USE (identical to MT5Bridge):
        broker = PaperBroker()
        broker.connect()
        df = broker.get_candles("XAUUSD", "H1", 200)
    """

    def __init__(self, initial_balance: float = None, state_path: str = STATE_FILE):
        self.connected = False
        self.state_path = state_path
        self.feeds = {}
        self._next_ticket = 1000
        self.balance = float(initial_balance) if initial_balance else 10000.0
        self.positions = {}       # ticket -> position dict
        self._pending_closures = []
        self._load_state()
        logger.info("PaperBroker created (simulated account, no MT5 needed).")

    # ─────────────────────────────────────────
    #  CONNECT / DISCONNECT
    # ─────────────────────────────────────────
    def connect(self) -> bool:
        self.connected = True
        logger.info(f"[PAPER] Connected. Simulated balance: ${self.balance:.2f}")
        return True

    def disconnect(self):
        self._save_state()
        self.connected = False
        logger.info("[PAPER] Disconnected (state saved).")

    # ─────────────────────────────────────────
    #  ADVANCE SIMULATED TIME
    # ─────────────────────────────────────────
    def tick(self):
        """
        Advances every active symbol feed by one bar and checks open
        positions against the new bar for SL/TP hits. Call this once per
        scan cycle, before reading candles, so prices actually move.
        """
        for feed in self.feeds.values():
            bar = feed.tick()
            self._check_fills(feed.symbol, bar)
        self._save_state()

    def _check_fills(self, symbol: str, bar: dict):
        for ticket, pos in list(self.positions.items()):
            if pos["symbol"] != symbol:
                continue
            hit_tp = (pos["direction"] == "BUY"  and bar["high"] >= pos["tp"]) or \
                     (pos["direction"] == "SELL" and bar["low"]  <= pos["tp"])
            hit_sl = (pos["direction"] == "BUY"  and bar["low"]  <= pos["sl"]) or \
                     (pos["direction"] == "SELL" and bar["high"] >= pos["sl"])
            if hit_tp or hit_sl:
                exit_price = pos["tp"] if hit_tp else pos["sl"]
                self._close_position(ticket, exit_price, "TP" if hit_tp else "SL")

    def _close_position(self, ticket: int, exit_price: float, reason: str):
        pos = self.positions.pop(ticket, None)
        if pos is None:
            return
        pip = _pip_size(pos["symbol"])
        pip_value = _pip_value_per_lot(pos["symbol"]) * pos["lot"]
        direction_sign = 1 if pos["direction"] == "BUY" else -1
        pips = (exit_price - pos["price"]) / pip * direction_sign
        profit = round(pips * pip_value, 2)

        self.balance += profit
        self._pending_closures.append({
            "ticket":     ticket,
            "symbol":     pos["symbol"],
            "direction":  pos["direction"],
            "profit":     profit,
            "exit_price": round(exit_price, 5),
            "reason":     reason,
        })
        logger.info(f"[PAPER] Position #{ticket} closed ({reason}): "
                    f"{pos['symbol']} {pos['direction']} | P&L: ${profit:+.2f} | "
                    f"Balance: ${self.balance:.2f}")

    def get_closed_trades(self) -> list:
        """Returns and clears the list of positions closed since the last call."""
        closures, self._pending_closures = self._pending_closures, []
        return closures

    # ─────────────────────────────────────────
    #  PRICE DATA
    # ─────────────────────────────────────────
    def _feed(self, symbol: str) -> _SymbolFeed:
        if symbol not in self.feeds:
            self.feeds[symbol] = _SymbolFeed(symbol)
        return self.feeds[symbol]

    def get_candles(self, symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
        feed = self._feed(symbol)
        df = feed.candles(max(count, 1))
        if len(df) < count:
            feed._advance(count - len(df))
            df = feed.candles(count)
        return df

    def get_price(self, symbol: str) -> dict:
        return self._feed(symbol).price_info()

    # ─────────────────────────────────────────
    #  ACCOUNT
    # ─────────────────────────────────────────
    def get_account(self) -> dict:
        floating = sum(self._floating_pnl(p) for p in self.positions.values())
        return {
            "balance":     round(self.balance, 2),
            "equity":      round(self.balance + floating, 2),
            "profit":      round(floating, 2),
            "margin_free": round(self.balance * 0.9, 2),
            "currency":    "USD",
            "leverage":    500,
        }

    def _floating_pnl(self, pos: dict) -> float:
        price = self._feed(pos["symbol"]).price_info()
        current = price["bid"] if pos["direction"] == "BUY" else price["ask"]
        pip = _pip_size(pos["symbol"])
        pip_value = _pip_value_per_lot(pos["symbol"]) * pos["lot"]
        direction_sign = 1 if pos["direction"] == "BUY" else -1
        pips = (current - pos["price"]) / pip * direction_sign
        return pips * pip_value

    # ─────────────────────────────────────────
    #  LOT SIZE
    # ─────────────────────────────────────────
    def calculate_lot_size(self, symbol: str, sl_pips: float, risk_pct: float, balance: float) -> float:
        if sl_pips <= 0:
            return 0.01
        risk_amount = balance * risk_pct
        pip_value = _pip_value_per_lot(symbol)
        lot = risk_amount / (sl_pips * pip_value)
        lot = max(0.01, min(50.0, round(lot, 2)))
        return lot

    # ─────────────────────────────────────────
    #  TRADE EXECUTION
    # ─────────────────────────────────────────
    def place_trade(self, symbol: str, direction: str, lot: float,
                    sl: float, tp: float, comment: str = "AI_BOT") -> dict:
        price_info = self.get_price(symbol)
        price = price_info["ask"] if direction == "BUY" else price_info["bid"]

        ticket = self._next_ticket
        self._next_ticket += 1

        self.positions[ticket] = {
            "ticket": ticket, "symbol": symbol, "direction": direction,
            "lot": lot, "price": price, "sl": sl, "tp": tp,
            "comment": comment, "open_time": datetime.now().isoformat(),
        }
        self._save_state()

        logger.info(f"[PAPER] Trade PLACED: {direction} {lot} lots of {symbol} "
                    f"@ {price} | SL: {sl} | TP: {tp} | Ticket: #{ticket}")
        return {
            "ticket": ticket, "symbol": symbol, "direction": direction,
            "lot": lot, "price": price, "sl": sl, "tp": tp,
            "time": datetime.now(),
        }

    def get_open_positions(self, symbol: str = None) -> list:
        out = []
        for ticket, pos in self.positions.items():
            if symbol and pos["symbol"] != symbol:
                continue
            out.append({
                "ticket": ticket, "symbol": pos["symbol"], "direction": pos["direction"],
                "lot": pos["lot"], "open_price": pos["price"], "sl": pos["sl"], "tp": pos["tp"],
                "profit": round(self._floating_pnl(pos), 2),
                "open_time": pos["open_time"],
            })
        return out

    def close_trade(self, ticket: int) -> bool:
        pos = self.positions.get(ticket)
        if pos is None:
            logger.error(f"[PAPER] Position {ticket} not found.")
            return False
        price_info = self.get_price(pos["symbol"])
        exit_price = price_info["bid"] if pos["direction"] == "BUY" else price_info["ask"]
        self._close_position(ticket, exit_price, "MANUAL")
        return True

    # ─────────────────────────────────────────
    #  STATE PERSISTENCE
    # ─────────────────────────────────────────
    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w") as f:
                json.dump({
                    "balance": self.balance,
                    "positions": self.positions,
                    "next_ticket": self._next_ticket,
                }, f, indent=2, default=str)
        except Exception as e:
            logger.debug(f"[PAPER] Could not save state: {e}")

    def _load_state(self):
        if not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path) as f:
                state = json.load(f)
            self.balance = state.get("balance", self.balance)
            self._next_ticket = state.get("next_ticket", self._next_ticket)
            self.positions = {int(k): v for k, v in state.get("positions", {}).items()}
            logger.info(f"[PAPER] Restored previous session. Balance: ${self.balance:.2f} | "
                        f"Open positions: {len(self.positions)}")
        except Exception as e:
            logger.warning(f"[PAPER] Could not load previous state: {e}")

# =============================================================================
# main.py — Main Bot Runner (START HERE)
# =============================================================================
# HOW TO START THE BOT:
#   1. Make sure MetaTrader 5 is open and logged into your Deriv account
#   2. Fill in your credentials in config/config.py
#   3. Run: python main.py
#
# WHAT HAPPENS WHEN YOU RUN THIS:
#   1. Connects to your Deriv MT5 account
#   2. Asks you which markets you want to trade TODAY
#   3. Asks your execution mode (auto/semi-auto/signals only)
#   4. Starts scanning all selected markets every 60 seconds
#   5. When a signal is found, alerts you (and executes if approved)
#   6. Sends daily report at end of session
# =============================================================================

import time
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config import *
from config.compat import get_runtime_config
from bridge.mt5_bridge import MT5Bridge
from ai_engine.indicators import Indicators
from ai_engine.signal_engine import SignalEngine
from alerts.telegram_bot import TelegramAlerter
from utils.logger import get_logger

RUNTIME_CONFIG = get_runtime_config()

log = get_logger("MainBot")


# ─── MARKET SELECTION MENU ────────────────────────────────────────────────────

def ask_markets() -> list:
    """
    Asks the user which markets to trade today.
    This runs every time you start the bot — you choose fresh each session.
    """
    print("\n" + "="*55)
    print("   DERIV AI TRADING BOT — Market Selection")
    print("="*55)
    print("\nAvailable markets:\n")

    all_symbols = []
    index = 1

    for category, symbols in ALL_SYMBOLS.items():
        print(f"  [{category.upper()}]")
        for sym in symbols:
            print(f"    {index}. {sym}")
            all_symbols.append(sym)
            index += 1

    print(f"\n  {index}. ALL markets")
    print(f"  0. Exit\n")

    while True:
        try:
            inp = input("Enter numbers separated by commas (e.g. 1,3,6): ").strip()
            if inp == "0":
                print("Exiting.")
                sys.exit(0)
            if inp == str(index):
                return all_symbols

            selected = []
            for n in inp.split(","):
                n = int(n.strip()) - 1
                if 0 <= n < len(all_symbols):
                    selected.append(all_symbols[n])

            if selected:
                print(f"\n✅ Selected: {', '.join(selected)}\n")
                return selected
            else:
                print("Invalid selection. Try again.")
        except (ValueError, KeyboardInterrupt):
            print("Invalid input. Try again.")


def ask_mode() -> str:
    """Asks the user which execution mode to use today."""
    print("─"*55)
    print("Execution Mode:")
    print("  1. FULL_AUTO   — Bot trades automatically, no approval needed")
    print("  2. SEMI_AUTO   — Bot alerts you, you APPROVE/REJECT each trade")
    print("  3. SIGNAL_ONLY — Bot sends alerts, you trade manually")
    print("─"*55)

    while True:
        try:
            choice = input("Choose mode [1/2/3] (default=2): ").strip() or "2"
            modes = {"1": "FULL_AUTO", "2": "SEMI_AUTO", "3": "SIGNAL_ONLY"}
            if choice in modes:
                mode = modes[choice]
                print(f"✅ Mode: {mode}\n")
                return mode
        except KeyboardInterrupt:
            return "SEMI_AUTO"


# ─── SAFETY CHECKS ────────────────────────────────────────────────────────────

def check_daily_limits(bridge: MT5Bridge) -> bool:
    """
    Checks if we've hit daily loss limits before scanning for new trades.
    Returns True if OK to trade, False if we should stop for the day.
    """
    daily_pnl   = bridge.get_daily_pnl()
    balance     = bridge.get_balance()
    daily_limit = balance * DAILY_LOSS_LIMIT

    if daily_pnl <= -daily_limit:
        log.warning(f"⛔ Daily loss limit hit: ${daily_pnl:.2f} (limit: -${daily_limit:.2f})")
        log.warning("Trading stopped for today to protect your capital.")
        return False

    open_trades = bridge.get_open_trades()
    if len(open_trades) >= MAX_OPEN_TRADES:
        log.info(f"Max open trades reached ({MAX_OPEN_TRADES}). Waiting for closes.")
        return False

    return True


# ─── MAIN SCAN LOOP ───────────────────────────────────────────────────────────

def scan_markets(bridge: MT5Bridge, signal_engine: SignalEngine,
                 alerter: TelegramAlerter, symbols: list, mode: str):
    """
    Scans all selected markets for trade signals.
    Runs once per scan cycle (every 60 seconds).
    
    For each symbol:
      1. Fetch latest M15 and H1 candles
      2. Calculate all indicators
      3. Run AI signal engine
      4. If signal found → alert/execute based on mode
    """
    for symbol in symbols:
        try:
            log.debug(f"Scanning {symbol}...")

            # Fetch price data
            df_signal_raw  = bridge.get_candles(symbol, SIGNAL_TF,  MODEL_LOOKBACK_BARS)
            df_confirm_raw = bridge.get_candles(symbol, CONFIRM_TF, MODEL_LOOKBACK_BARS)

            if df_signal_raw is None or df_confirm_raw is None:
                log.warning(f"Could not get data for {symbol}. Skipping.")
                continue

            # Add indicators
            df_signal  = Indicators(df_signal_raw).add_all()
            df_confirm = Indicators(df_confirm_raw).add_all()

            # Analyze with AI engine
            signal = signal_engine.analyze(symbol, df_signal, df_confirm)

            if signal is None:
                log.debug(f"{symbol}: No signal this cycle.")
                continue

            # ── Signal found! ──────────────────────────────────────────
            log.info(f"🔔 SIGNAL: {symbol} {signal.direction} | "
                     f"Score: {signal.confidence}% | Strategy: {signal.strategy}")

            if mode == "SIGNAL_ONLY":
                # Just send alert, user trades manually
                alerter.send_signal_alert(signal, approval_required=False)
                continue

            if mode == "SEMI_AUTO":
                # Send alert and wait for approval
                approved = alerter.send_signal_alert(signal, approval_required=True)
                if not approved:
                    continue

            # ── Execute trade (FULL_AUTO or approved SEMI_AUTO) ────────
            ticket = bridge.place_order(
                symbol           = signal.symbol,
                direction        = signal.direction,
                stop_loss_price  = signal.stop_loss,
                take_profit_price = signal.take_profit,
                comment          = f"AI_{signal.strategy[:6]}"
            )

            if ticket:
                log.info(f"✅ Trade placed: #{ticket}")
                alerter.send_message(
                    f"✅ <b>Trade #{ticket} placed!</b>\n"
                    f"{signal.direction} {signal.symbol} @ {signal.entry_price:.5f}"
                )
            else:
                log.warning(f"Trade placement failed for {symbol}")

        except Exception as e:
            log.error(f"Error scanning {symbol}: {e}", exc_info=True)


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

def main():
    """
    Main function — runs the entire bot loop.
    """
    print("\n" + "="*55)
    print("   DERIV AI TRADING BOT v1.0")
    print("   Multi-Strategy | AI-Powered | MT5 Connected")
    print("="*55)

    # ── Step 1: Ask user which markets and mode ──
    symbols = ask_markets()
    mode    = ask_mode()

    # ── Step 2: Connect to MT5 ──
    log.info("Connecting to Deriv MT5...")
    bridge = MT5Bridge()

    if not bridge.connect():
        log.error("Could not connect to MT5. Make sure MT5 is open and credentials are set.")
        sys.exit(1)

    balance = bridge.get_balance()
    log.info(f"Connected! Balance: ${balance:.2f}")

    # ── Step 3: Initialize components ──
    signal_engine = SignalEngine()
    alerter       = TelegramAlerter()

    # Send startup notification
    alerter.send_startup_message(symbols, mode, balance)

    # ── Step 4: Main scan loop ──
    log.info(f"Bot started. Scanning {len(symbols)} markets every 60 seconds.")
    log.info("Press Ctrl+C to stop.\n")

    today_trades = []
    scan_count   = 0
    scan_interval = 560 # Scan every 60 seconds

    try:
        while True:
            scan_count += 1
            log.info(f"Scan #{scan_count} | {datetime.now().strftime('%H:%M:%S')} | "
                     f"Balance: ${bridge.get_balance():.2f}")

            # Safety check: daily limits
            if not check_daily_limits(bridge):
                log.info("Waiting 5 minutes before next check...")
                time.sleep(300)
                continue

            # Scan all markets
            scan_markets(bridge, signal_engine, alerter, symbols, mode)

            # Every 100 scans (~100 min): show open trades
            if scan_count % 100 == 0:
                open_trades = bridge.get_open_trades()
                if open_trades:
                    log.info(f"Open trades ({len(open_trades)}):")
                    for t in open_trades:
                        log.info(f"  #{t['ticket']} {t['type']} {t['symbol']} | P&L: ${t['profit']:.2f}")

            # End of day: send report (around 22:00 server time)
            if datetime.now().hour == 22 and datetime.now().minute < 1:
                balance_now = bridge.get_balance()
                alerter.send_daily_report(today_trades, balance_now)
                today_trades = []  # Reset for next day

            time.sleep(scan_interval)

    except KeyboardInterrupt:
        log.info("\nBot stopped by user (Ctrl+C).")
        # Send final report
        final_balance = bridge.get_balance()
        alerter.send_daily_report(today_trades, final_balance)
        alerter.send_message("🛑 <b>Bot stopped manually.</b>")
        bridge.disconnect()
        log.info("Disconnected from MT5. Goodbye!")


if __name__ == "__main__":
    main()

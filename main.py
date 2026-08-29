"""
=============================================================
  MAIN BOT ENGINE
=============================================================
  PURPOSE: This is the CONDUCTOR that orchestrates all
  the other modules to make the bot run.

  THIS FILE:
  1. Asks you which markets to trade at startup
  2. Connects to Deriv MT5
  3. Downloads and prepares data
  4. Trains AI models (or loads saved ones)
  5. Runs the trading loop every hour
  6. For each market:
     a. Gets latest price data
     b. Calculates indicators
     c. Runs AI to get signal
     d. Checks risk management
     e. In SEMI_AUTO: asks YOUR approval
     f. In FULL_AUTO: places trade automatically
  7. Monitors open trades
  8. Logs everything

  BROKER_MODE (config/settings.py, default "PAPER"):
    PAPER = simulated broker, runs immediately, no account needed
    MT5   = real Deriv MT5 account (needs MetaTrader5 installed + .env)

  TESTING / AUTOMATION HOOKS (env vars, all optional):
    BOT_MARKETS=EURUSD,XAUUSD   skip the market-selection prompt
    BOT_MAX_SCANS=5             exit automatically after N scans
    BOT_SCAN_INTERVAL_SEC=2     shorten the between-scan wait (default 300)

  TO START THE BOT:
      python main.py
=============================================================
"""

import time
import logging
import sys
import os
from datetime import datetime

# ── Setup logging FIRST so all modules can log ──────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler(f"logs/bot_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8'),
        logging.StreamHandler(open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', closefd=False))   # Also print to screen
    ]
)
logger = logging.getLogger("MainBot")

# ── Import all modules ───────────────────────────────────────
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config.compat import get_runtime_config
import config.settings as settings
from config.settings import (
    ACCOUNT_BALANCE, RISK_PER_TRADE_PCT, PRIMARY_TIMEFRAME,
    LOOKBACK_CANDLES, RETRAIN_EVERY_DAYS, TELEGRAM_ENABLED
)

RUNTIME_CONFIG = get_runtime_config()
from bridge                 import get_bridge
from ai_engine.indicators   import IndicatorEngine
from ai_engine.risk_manager import RiskManager
from ai_engine.loss_detector import LossDetector, BotStatus
from ai_engine.enhanced_engine import EnhancedAIEngine
from ai_engine.performance_tracker import PerformanceTracker

# Optional Telegram alerts
if TELEGRAM_ENABLED:
    from alerts.telegram_alerts import TelegramAlerts
    alerter = TelegramAlerts()
else:
    alerter = None


# ═══════════════════════════════════════════════════════════════
#  MARKET SELECTION MENU
# ═══════════════════════════════════════════════════════════════
def ask_which_markets() -> list:
    """
    Displays an interactive menu asking which markets to trade.
    Returns a list of enabled symbol names.

    Set BOT_MARKETS (comma-separated symbols) to skip the prompt —
    used for automated runs and testing.
    """
    env_markets = os.environ.get("BOT_MARKETS")
    if env_markets:
        selected = [s.strip() for s in env_markets.split(",") if s.strip()]
        logger.info(f"BOT_MARKETS set — skipping menu. Markets: {', '.join(selected)}")
        return selected

    all_markets = {
        # FOREX
        "1":  ("EURUSD",               "Forex     - EUR/USD (most liquid)"),
        "2":  ("GBPUSD",               "Forex     - GBP/USD"),
        "3":  ("USDJPY",               "Forex     - USD/JPY"),
        "4":  ("USDCHF",               "Forex     - USD/CHF"),
        "5":  ("AUDUSD",               "Forex     - AUD/USD"),
        "6":  ("USDCAD",               "Forex     - USD/CAD"),
        "7":  ("NZDUSD",               "Forex     - NZD/USD"),
        "8":  ("EURGBP",               "Forex     - EUR/GBP"),
        "9":  ("EURJPY",               "Forex     - EUR/JPY"),
        "10": ("GBPJPY",               "Forex     - GBP/JPY (volatile)"),
        # COMMODITIES
        "11": ("XAUUSD",               "Commodity - Gold (XAU/USD)"),
        "12": ("XAGUSD",               "Commodity - Silver (XAG/USD)"),
        "13": ("XTIUSD",               "Commodity - Crude Oil (WTI)"),
        # VOLATILITY
        "14": ("Volatility 10 Index",  "Synthetic - Volatility 10"),
        "15": ("Volatility 25 Index",  "Synthetic - Volatility 25"),
        "16": ("Volatility 50 Index",  "Synthetic - Volatility 50"),
        "17": ("Volatility 75 Index",  "Synthetic - Volatility 75 (popular)"),
        "18": ("Volatility 100 Index", "Synthetic - Volatility 100"),
        # BOOM
        "19": ("Boom 300 Index",       "Synthetic - Boom 300"),
        "20": ("Boom 500 Index",       "Synthetic - Boom 500"),
        "21": ("Boom 1000 Index",      "Synthetic - Boom 1000"),
        # CRASH
        "22": ("Crash 300 Index",      "Synthetic - Crash 300"),
        "23": ("Crash 500 Index",      "Synthetic - Crash 500"),
        "24": ("Crash 1000 Index",     "Synthetic - Crash 1000"),
        # STEP & JUMP
        "25": ("Step Index",           "Synthetic - Step Index (scalping)"),
        "26": ("Jump 10 Index",        "Synthetic - Jump 10"),
        "27": ("Jump 25 Index",        "Synthetic - Jump 25"),
        "28": ("Jump 50 Index",        "Synthetic - Jump 50"),
        "29": ("Jump 75 Index",        "Synthetic - Jump 75"),
        "30": ("Jump 100 Index",       "Synthetic - Jump 100"),
        # CRYPTO
        "31": ("BTCUSD",               "Crypto    - Bitcoin/USD"),
        "32": ("ETHUSD",               "Crypto    - Ethereum/USD"),
    }

    print("\n" + "="*60)
    print("  🤖  FOREX AI BOT - DERIV EDITION")
    print("="*60)
    print("\n  SELECT MARKETS TO TRADE:")
    print("  (Type the numbers separated by commas, e.g.: 1,2,4)\n")

    for key, (symbol, name) in all_markets.items():
        print(f"    [{key}] {name}")

    print("\n    [A] All markets")
    print("    [Q] Quit\n")

    # Category shortcut map
    category_shortcuts = {
        "F": [str(i) for i in range(1,  11)],   # Forex
        "C": [str(i) for i in range(11, 14)],   # Commodities
        "S": [str(i) for i in range(14, 19)],   # Volatility
        "B": [str(i) for i in range(19, 22)],   # Boom
        "R": [str(i) for i in range(22, 25)],   # Crash
        "J": [str(i) for i in range(25, 31)],   # Jump
        "K": [str(i) for i in range(31, 33)],   # Crypto
        "A": [str(i) for i in range(1,  33)],   # All
    }

    while True:
        choice = input("  Your choice: ").strip().upper()

        if choice == "Q":
            print("  Goodbye!")
            sys.exit(0)

        # Handle category shortcuts
        if choice in category_shortcuts:
            selected = [all_markets[k][0] for k in category_shortcuts[choice] if k in all_markets]
            break

        # Parse comma-separated numbers
        keys = [k.strip() for k in choice.split(",")]
        selected = []
        valid    = True
        for k in keys:
            if k in all_markets:
                selected.append(all_markets[k][0])
            else:
                print(f"  ❌ '{k}' is not a valid option. Try again.")
                valid = False
                break

        if valid and selected:
            break

    print("\n  ✅ Selected markets:")
    for s in selected:
        print(f"     - {s}")
    print()
    return selected


# ═══════════════════════════════════════════════════════════════
#  SEMI-AUTO APPROVAL PROMPT
# ═══════════════════════════════════════════════════════════════
def ask_approval(symbol: str, signal: dict, risk_check: dict) -> bool:
    """
    In SEMI_AUTO mode, asks the user to approve or reject a signal.
    
    Displays all signal details and waits for Y/N input.
    """
    action     = signal['action']
    confidence = signal['confidence']
    regime     = signal['regime']
    sl         = signal['sl']
    tp         = signal['tp']
    rr         = signal['rr_ratio']
    risk_amt   = risk_check['risk_amount']

    emoji = "📈 BUY" if action == "BUY" else "📉 SELL"

    print("\n" + "─"*55)
    print(f"  🚨 NEW SIGNAL: {emoji}  {symbol}")
    print("─"*55)
    print(f"  Confidence :  {confidence:.0%}")
    print(f"  Market Regime: {regime}")
    print(f"  Stop Loss  :  {sl}")
    print(f"  Take Profit:  {tp}")
    print(f"  R:R Ratio  :  1:{rr}")
    print(f"  Risk Amount:  ${risk_amt:.2f}")
    print("─"*55)

    choice = input("  APPROVE? [Y = Yes / N = No]: ").strip().upper()
    return choice == "Y"


# ═══════════════════════════════════════════════════════════════
#  BOT CLASS
# ═══════════════════════════════════════════════════════════════
class ForexAIBot:
    """
    The main bot that runs everything.
    
    HOW TO USE:
        bot = ForexAIBot()
        bot.run()
    """

    def __init__(self):
        self.bridge       = get_bridge()
        self.indicators   = IndicatorEngine()
        self.risk_manager = RiskManager(
            balance       = RUNTIME_CONFIG["account_balance"],
            risk_pct      = RUNTIME_CONFIG["risk_per_trade_pct"],
            max_trades    = RUNTIME_CONFIG["max_open_trades"],
            daily_loss_pct= RUNTIME_CONFIG["daily_loss_limit_pct"],
            min_rr        = RUNTIME_CONFIG["min_reward_risk_ratio"]
        )
        self.ai_engines  = {}   # One AI engine per symbol
        self.active_symbols = []
        self.running     = False
        self.last_train  = {}   # Track last training date per symbol
        self.loss_detector = LossDetector(
            initial_balance = ACCOUNT_BALANCE,
            save_path       = "logs/loss_detector_state.json"
        )
        self.tracker = PerformanceTracker()

    # ─────────────────────────────────────────
    #  STARTUP
    # ─────────────────────────────────────────
    def startup(self):
        """Runs all startup tasks: market selection, MT5 connection, model training."""
        
        # Step 1: Ask which markets to trade
        self.active_symbols = ask_which_markets()

        # Step 2: Connect to the broker (PaperBroker or MT5Bridge, per BROKER_MODE)
        logger.info(f"Connecting ({RUNTIME_CONFIG['broker_mode']} mode)...")
        if not self.bridge.connect():
            logger.error("❌ Could not connect to the broker. Please check:")
            logger.error("   1. MetaTrader 5 is installed and running (BROKER_MODE=MT5 only)")
            logger.error("   2. Your credentials in .env are correct")
            sys.exit(1)

        # Step 3: Initialize AI engines and train models
        for symbol in self.active_symbols:
            logger.info(f"Initializing AI engine for {symbol}...")
            self.ai_engines[symbol] = EnhancedAIEngine(symbol)

            # Train if model not already saved
            if not self.ai_engines[symbol].is_trained:
                self._train_model(symbol)
            else:
                logger.info(f"  Loaded existing model for {symbol}")

        logger.info("\n" + "="*55)
        logger.info("  🤖 BOT IS READY")
        logger.info(f"  Mode: {RUNTIME_CONFIG['execution_mode']}")
        logger.info(f"  Markets: {', '.join(self.active_symbols)}")
        logger.info(f"  Balance: ${RUNTIME_CONFIG['account_balance']} | Risk: {RUNTIME_CONFIG['risk_per_trade_pct']:.0%}/trade")
        logger.info(f"  Confidence threshold: {RUNTIME_CONFIG['min_signal_confidence']:.0%} | Retrain every {RUNTIME_CONFIG['retrain_every_days']} days")
        logger.info(f"  Workspace: {RUNTIME_CONFIG['workspace_root']}")
        logger.info("="*55 + "\n")

        if alerter:
            alerter.send_bot_started(RUNTIME_CONFIG['execution_mode'], self.active_symbols)

    # ─────────────────────────────────────────
    #  TRAIN A MODEL
    # ─────────────────────────────────────────
    def _train_model(self, symbol: str):
        """Downloads data and trains the AI model for a symbol."""
        logger.info(f"Training AI model for {symbol}...")
        
        # Download historical data (more candles = better training)
        df = self.bridge.get_candles(symbol, PRIMARY_TIMEFRAME, count=1000)
        if df is None or len(df) < 150:
            logger.warning(f"Not enough data to train for {symbol}. Skipping.")
            return

        # Add indicators
        df = self.indicators.add_all(df)

        # Train
        result = self.ai_engines[symbol].train(df)
        if result.get("success"):
            logger.info(f"  ✅ {symbol} model trained. CV Accuracy: {result['cv_accuracy']:.1%}")
        else:
            logger.warning(f"  ⚠️ {symbol} model training failed: {result.get('reason')}")

        self.last_train[symbol] = datetime.now()

    # ─────────────────────────────────────────
    #  PROCESS ONE SYMBOL
    # ─────────────────────────────────────────

    def _write_signal(self, symbol: str, signal: dict):
        """Writes latest signal to file so the live dashboard can read it."""
        import json
        signal_file = "logs/latest_signals.json"
        try:
            existing = {}
            if os.path.exists(signal_file):
                with open(signal_file) as f:
                    existing = json.load(f)
            existing[symbol] = {
                "action":     signal.get("action", "WAIT"),
                "confidence": signal.get("confidence", 0),
                "regime":     signal.get("regime", "—"),
                "sl":         signal.get("sl", 0),
                "tp":         signal.get("tp", 0),
                "rr_ratio":   signal.get("rr_ratio", 0),
                "timestamp":  signal.get("timestamp", ""),
            }
            with open(signal_file, "w") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not write signal file: {e}")

    def process_symbol(self, symbol: str):
        """
        Runs the full analysis and trade decision cycle for one symbol.
        Called every hour (or on each tick) in the main loop.
        """
        # ── LOSS DETECTOR CHECK (runs before everything) ──────────
        adj = self.loss_detector.get_trade_adjustments()
        if not adj["can_trade"]:
            logger.warning(f"  🚫 {symbol}: TRADING BLOCKED by loss detector — {adj['reason']}")
            if alerter:
                alerter.send(f"🚫 BOT PAUSED on {symbol}\n{adj['reason']}")
            return

        # If retrain was requested by loss detector, do it now
        if self.loss_detector.retrain_requested:
            logger.warning(f"  🔄 Loss detector requested AI retrain for {symbol}")
            self._train_model(symbol)
            self.loss_detector.acknowledge_retrain()

        # Use loss-detector-adjusted confidence threshold (raised in RECOVERY, etc.)
        min_conf = adj["min_confidence"]

        logger.info(f"Processing {symbol}... [Status: {adj['status']} | Size: ×{adj['lot_multiplier']} | Min conf: {min_conf:.0%}]")

        # Check if model needs retraining
        last = self.last_train.get(symbol)
        if last:
            days_since = (datetime.now() - last).days
            if days_since >= RETRAIN_EVERY_DAYS:
                logger.info(f"Retraining {symbol} model ({days_since} days since last train)...")
                self._train_model(symbol)

        # Step 1: Get latest price data
        df = self.bridge.get_candles(symbol, PRIMARY_TIMEFRAME, LOOKBACK_CANDLES)
        if df is None:
            logger.warning(f"  No data for {symbol}. Skipping.")
            return

        # Step 2: Calculate indicators
        df = self.indicators.add_all(df)

        # Step 3: Get AI signal
        signal = self.ai_engines[symbol].predict(df, min_conf)

        # Write signal to file so dashboard can read it
        self._write_signal(symbol, signal)

        if signal['action'] == "WAIT":
            logger.info(f"  {symbol}: WAIT — {signal.get('reason', 'No reason given')}")
            return

        # Step 4: Get account info for risk checks
        account = self.bridge.get_account()
        if account is None:
            logger.error("  Could not get account info.")
            return

        # Step 5: Run risk checks
        open_positions = self.bridge.get_open_positions()
        risk_check     = self.risk_manager.check_trade(signal, open_positions, account)

        if not risk_check['approved']:
            logger.info(f"  {symbol}: Trade blocked — {risk_check['reason']}")
            return

        # Step 6: Execute trade based on mode (read live so dashboard mode changes apply)
        if settings.EXECUTION_MODE == "SEMI_AUTO":
            approved = ask_approval(symbol, signal, risk_check)
            if not approved:
                logger.info(f"  {symbol}: Trade rejected by user.")
                return

        # Step 7: Calculate lot size
        lot = self.bridge.calculate_lot_size(
            symbol   = symbol,
            sl_pips  = signal['sl_pips'],
            risk_pct = RISK_PER_TRADE_PCT,
            balance  = account['balance']
        )

        # Apply loss-detector lot multiplier
        lot = round(lot * adj["lot_multiplier"], 2)
        lot = max(lot, 0.01)

        # Step 8: Place the trade
        trade = self.bridge.place_trade(
            symbol    = symbol,
            direction = signal['action'],
            lot       = lot,
            sl        = signal['sl'],
            tp        = signal['tp'],
            comment   = f"AI_{signal['strategy']}"
        )

        if trade:
            logger.info(f"  ✅ Trade opened: {symbol} {signal['action']} {lot} lots")
            self.tracker.record_open(
                ticket     = trade['ticket'], symbol = symbol,
                direction  = signal['action'], entry = trade['price'],
                sl         = trade['sl'], tp = trade['tp'], lot = lot,
                confidence = signal['confidence'], strategy = signal['strategy'],
                regime     = signal.get('regime', 'N/A'),
            )
            if alerter:
                alerter.send_trade_opened(trade)
        else:
            logger.error(f"  ❌ Trade failed for {symbol}")


    def _check_control_file(self):
        """
        Reads the control file written by the dashboard.
        Allows dashboard to start/stop/change mode without restarting bot.
        """
        control_file = "logs/bot_control.json"
        if not os.path.exists(control_file):
            return
        try:
            import json
            with open(control_file) as f:
                ctrl = json.load(f)
            # Handle stop signal
            if ctrl.get("running") is False and self.running:
                logger.info("Dashboard sent STOP signal. Pausing trading loop.")
                self.running = False
            # Handle start signal
            if ctrl.get("running") is True and not self.running:
                logger.info("Dashboard sent START signal. Resuming trading loop.")
                self.running = True
            # Handle mode change
            new_mode = ctrl.get("mode")
            if new_mode and new_mode in ("SEMI_AUTO", "FULL_AUTO"):
                import sys
                # Update the global
                global_module = sys.modules.get("config.settings")
                if global_module:
                    global_module.EXECUTION_MODE = new_mode
                logger.info(f"Mode changed to: {new_mode}")
        except Exception as e:
            logger.debug(f"Control file read error: {e}")

    def on_trade_closed(self, symbol: str, profit: float,
                        confidence: float = 0.0, strategy: str = "N/A"):
        """
        Call this whenever a trade closes to update the loss detector.
        The bot calls this automatically when it detects a closed position.
        """
        result = self.loss_detector.record_trade(
            profit     = profit,
            symbol     = symbol,
            confidence = confidence,
            strategy   = strategy
        )
        if result["status_changed"]:
            logger.warning(f"⚠️  Bot status changed: {result['old_status']} → {result['new_status']}")
            logger.warning(f"   {result['reason']}")
            if alerter:
                emoji = "🚨" if result['new_status'] in ("PAUSED","EMERGENCY") else "⚠️"
                alerter.send(f"{emoji} Bot status: {result['new_status']}\n{result['reason']}")

    def _process_closed_trades(self):
        """
        Advances the broker by one tick (moves simulated time forward for
        PaperBroker; checks trade history for MT5Bridge) and feeds any
        newly-closed trades into risk tracking, the loss detector, the
        performance tracker, and Telegram.
        """
        self.bridge.tick()
        for closure in self.bridge.get_closed_trades():
            profit = closure["profit"]
            logger.info(f"  Trade closed: {closure['symbol']} #{closure['ticket']} "
                        f"${profit:+.2f} ({closure.get('reason', '')})")

            self.risk_manager.record_trade_result(profit)
            self.tracker.record_close(
                ticket=closure["ticket"],
                exit_price=closure.get("exit_price", 0),
                profit=profit,
            )
            self.on_trade_closed(closure["symbol"], profit)

            if alerter:
                alerter.send_trade_closed({**closure, "close_reason": closure.get("reason", "TP/SL Hit")})

    # ─────────────────────────────────────────
    #  MAIN LOOP
    # ─────────────────────────────────────────
    def run(self):
        """
        The main trading loop. Runs until you press Ctrl+C (or, if
        BOT_MAX_SCANS is set, until that many scans have run — used for
        automated testing).
        """
        self.startup()
        self.running = True

        max_scans     = int(os.environ.get("BOT_MAX_SCANS", "0") or "0")
        scan_interval = int(os.environ.get("BOT_SCAN_INTERVAL_SEC", "300") or "300")
        scan_count    = 0

        logger.info("Starting main trading loop. Press Ctrl+C to stop.\n")

        while self.running:
            try:
                scan_count += 1
                logger.info(f"\n{'='*50}")
                logger.info(f"  SCAN #{scan_count} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*50}")

                # Check for dashboard control signals
                self._check_control_file()

                # Advance the broker and settle any trades that closed
                self._process_closed_trades()

                # Process each active symbol
                for symbol in self.active_symbols:
                    self.process_symbol(symbol)

                # Show daily stats
                stats = self.risk_manager.get_daily_stats()
                logger.info(f"Today: {stats['total_trades']} trades | Wins: {stats['wins']} | Losses: {stats['losses']} | P&L: ${stats['total_pnl']:.2f}")

                if max_scans and scan_count >= max_scans:
                    logger.info(f"BOT_MAX_SCANS={max_scans} reached. Stopping.")
                    self.running = False
                    break

                # Wait before next scan
                logger.info(f"Next scan in {scan_interval} seconds...")
                time.sleep(scan_interval)

            except KeyboardInterrupt:
                logger.info("\n  Bot stopped by user.")
                self.running = False

            except Exception as e:
                logger.error(f"  Unexpected error: {e}", exc_info=True)
                logger.info(f"  Waiting {scan_interval} seconds before retrying...")
                time.sleep(scan_interval)

        # Cleanup
        self.bridge.disconnect()
        logger.info("Bot shut down cleanly.")


# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    bot = ForexAIBot()
    bot.run()

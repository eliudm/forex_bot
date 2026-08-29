# ============================================================
# alerts/telegram_alerts.py — Telegram Notification System
# ============================================================
# WHAT THIS FILE DOES:
#   Sends you Telegram messages when:
#     - A new trade signal is found (with APPROVE/REJECT buttons)
#     - A trade is opened or closed
#     - Daily summary report
#     - Bot errors or warnings
#
# HOW TO SET UP TELEGRAM:
#   Step 1: Open Telegram, search for @BotFather
#   Step 2: Send: /newbot
#   Step 3: Follow instructions, copy the TOKEN
#   Step 4: Message your new bot once (say "hello")
#   Step 5: Visit: https://api.telegram.org/bot<TOKEN>/getUpdates
#           Look for "chat":{"id": YOUR_CHAT_ID}
#   Step 6: Add TOKEN and CHAT_ID to your .env file (see .env.example)
# ============================================================

import logging
import json
import urllib.request
import urllib.parse
from config.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


class TelegramAlerts:
    """
    Sends messages and trade signals to your Telegram.

    USAGE:
        alerts = TelegramAlerts()
        alerts.send_signal(signal_data)
        alerts.send_trade_opened(trade_data)
        alerts.send_daily_summary(summary_data)
    """

    def __init__(self):
        self.token   = TELEGRAM_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def _send(self, text: str, parse_mode: str = "HTML",
              reply_markup: dict = None) -> bool:
        """Core method to send a Telegram message."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured. Add TOKEN and CHAT_ID to config.py")
            print(f"\n📱 TELEGRAM ALERT (not sent — configure Telegram):\n{text}\n")
            return False

        payload = {
            "chat_id":    self.chat_id,
            "text":       text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        try:
            data = urllib.parse.urlencode(payload).encode()
            req  = urllib.request.Request(f"{self.base_url}/sendMessage", data=data)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def send_signal(self, signal: dict) -> bool:
        """
        Send a trade signal alert with APPROVE / REJECT buttons.
        In SEMI_AUTO mode, you must tap APPROVE for the trade to execute.

        signal dict keys:
            symbol, direction, entry, sl, tp, sl_pips, tp_pips,
            rr_ratio, confidence, strategy, lot_size, risk_amount
        """
        direction_emoji = "🟢 BUY" if signal.get("direction") == "BUY" else "🔴 SELL"
        confidence_pct  = signal.get("confidence", 0) * 100

        # Build confidence bar (visual indicator)
        bar_filled = int(confidence_pct / 10)
        conf_bar   = "█" * bar_filled + "░" * (10 - bar_filled)

        text = (
            f"<b>🤖 AI TRADING SIGNAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Pair:</b>       {signal.get('symbol')}\n"
            f"<b>Direction:</b>  {direction_emoji}\n"
            f"<b>Strategy:</b>   {signal.get('strategy', 'AI Model')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Entry:</b>      {signal.get('entry', 0):.5f}\n"
            f"<b>Stop Loss:</b>  {signal.get('sl', 0):.5f}  ({signal.get('sl_pips', 0):.1f} pips)\n"
            f"<b>Take Profit:</b>{signal.get('tp', 0):.5f}  ({signal.get('tp_pips', 0):.1f} pips)\n"
            f"<b>R:R Ratio:</b>  1:{signal.get('rr_ratio', 0):.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Lot Size:</b>   {signal.get('lot_size', 0.01)}\n"
            f"<b>Risk:</b>       ${signal.get('risk_amount', 5):.2f}\n"
            f"<b>AI Confidence:</b>\n"
            f"[{conf_bar}] {confidence_pct:.0f}%\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Tap APPROVE to execute or REJECT to skip.</i>"
        )

        # Inline keyboard buttons for approval
        reply_markup = {
            "inline_keyboard": [[
                {"text": "✅ APPROVE",
                 "callback_data": f"approve_{signal.get('signal_id', '0')}"},
                {"text": "❌ REJECT",
                 "callback_data": f"reject_{signal.get('signal_id', '0')}"}
            ]]
        }

        return self._send(text, reply_markup=reply_markup)

    def send(self, text: str) -> bool:
        """Generic freeform message (bot status changes, pause notices, etc.)."""
        return self._send(text)

    def send_trade_opened(self, trade: dict) -> bool:
        """Notify when a trade is successfully opened."""
        direction_emoji = "🟢" if trade.get("direction") == "BUY" else "🔴"
        lots = trade.get("lot", trade.get("volume", 0.01))
        text = (
            f"{direction_emoji} <b>TRADE OPENED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Symbol:</b>  {trade.get('symbol')}\n"
            f"<b>Type:</b>    {trade.get('direction')}\n"
            f"<b>Price:</b>   {trade.get('price', 0):.5f}\n"
            f"<b>SL:</b>      {trade.get('sl', 0):.5f}\n"
            f"<b>TP:</b>      {trade.get('tp', 0):.5f}\n"
            f"<b>Lots:</b>    {lots}\n"
            f"<b>Ticket:</b>  #{trade.get('ticket', 0)}\n"
        )
        return self._send(text)

    def send_trade_closed(self, trade: dict) -> bool:
        """Notify when a trade closes (with P&L result)."""
        profit   = trade.get("profit", 0)
        emoji    = "💰 PROFIT" if profit > 0 else "📉 LOSS"
        pnl_sign = "+" if profit > 0 else ""

        text = (
            f"{emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Symbol:</b>  {trade.get('symbol')}\n"
            f"<b>P&L:</b>     {pnl_sign}${profit:.2f}\n"
            f"<b>Ticket:</b>  #{trade.get('ticket', 0)}\n"
            f"<b>Reason:</b>  {trade.get('close_reason', 'TP/SL Hit')}\n"
        )
        return self._send(text)

    def send_daily_summary(self, summary: dict) -> bool:
        """Send end-of-day performance report."""
        pnl    = summary.get("total_pnl", 0)
        emoji  = "📈" if pnl >= 0 else "📉"
        sign   = "+" if pnl >= 0 else ""

        text = (
            f"{emoji} <b>DAILY TRADING SUMMARY</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Date:</b>       {summary.get('date')}\n"
            f"<b>Total Trades:</b> {summary.get('total_trades', 0)}\n"
            f"<b>Wins:</b>       {summary.get('wins', 0)}\n"
            f"<b>Losses:</b>     {summary.get('losses', 0)}\n"
            f"<b>Win Rate:</b>   {summary.get('win_rate', 0):.1f}%\n"
            f"<b>Total P&L:</b>  {sign}${pnl:.2f}\n"
        )
        return self._send(text)

    def send_warning(self, message: str) -> bool:
        """Send a warning alert."""
        return self._send(f"⚠️ <b>BOT WARNING</b>\n{message}")

    def send_error(self, message: str) -> bool:
        """Send an error alert."""
        return self._send(f"🔴 <b>BOT ERROR</b>\n{message}")

    def send_bot_started(self, mode: str, markets: list) -> bool:
        """Notify that the bot has started."""
        market_list = "\n".join([f"  • {m}" for m in markets])
        text = (
            f"🚀 <b>AI TRADING BOT STARTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Mode:</b>    {mode}\n"
            f"<b>Markets:</b>\n{market_list}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Bot is now scanning for signals...</i>"
        )
        return self._send(text)

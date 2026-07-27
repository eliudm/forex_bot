//+------------------------------------------------------------------+
//|  FOREX AI BOT - Expert Advisor (MQL5)                           |
//|  Platform: Deriv MT5                                            |
//|  Version:  1.0                                                  |
//+------------------------------------------------------------------+
//
//  PURPOSE: This Expert Advisor (EA) runs inside MetaTrader 5.
//  It manages trades placed by the Python AI engine.
//
//  WHAT THIS EA DOES:
//  1. Monitors all open trades placed by the Python bot
//  2. Implements trailing stop loss (moves SL as trade profits)
//  3. Moves SL to break-even when trade is 50% to TP
//  4. Sends alerts if connection to Python is lost
//
//  HOW TO INSTALL:
//  1. Open MetaTrader 5
//  2. Press Ctrl+Shift+D to open MetaEditor
//  3. Create a new Expert Advisor file named "ForexAIBot"
//  4. Paste this entire code
//  5. Press F7 to compile
//  6. Drag the EA from Navigator to any chart
//  7. Enable "Allow Algo Trading" (the green play button)
//
//+------------------------------------------------------------------+

#property copyright "Forex AI Bot"
#property version   "1.00"
#property strict

// ── INPUT PARAMETERS ─────────────────────────────────────────────
// These are settings you can change from the MT5 EA settings panel
input int    MAGIC_NUMBER       = 20240101;  // Must match Python bot's magic number
input bool   USE_TRAILING_STOP  = true;      // Enable trailing stop loss
input double TRAILING_ATR_MULT  = 1.0;       // Trail at 1x ATR distance
input bool   USE_BREAKEVEN      = true;      // Move SL to break-even after 50% to TP
input bool   SHOW_INFO_PANEL    = true;      // Show info box on chart

// ── GLOBAL VARIABLES ─────────────────────────────────────────────
datetime lastBarTime = 0;
int      atrHandle;   // Handle to ATR indicator

//+------------------------------------------------------------------+
//  INITIALIZATION - Runs once when EA starts
//+------------------------------------------------------------------+
int OnInit()
{
   // Create ATR indicator handle (period 14, on current chart)
   atrHandle = iATR(_Symbol, PERIOD_CURRENT, 14);
   
   if(atrHandle == INVALID_HANDLE)
   {
      Alert("ForexAIBot: Failed to create ATR indicator handle.");
      return INIT_FAILED;
   }
   
   Print("ForexAIBot EA started. Magic: ", MAGIC_NUMBER);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//  DEINITIALIZATION - Runs when EA is removed
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(atrHandle);
   Comment("");  // Clear chart comment
   Print("ForexAIBot EA stopped.");
}

//+------------------------------------------------------------------+
//  ON TICK - Runs on every new price tick
//+------------------------------------------------------------------+
void OnTick()
{
   // Only act on new bar (once per candle) to reduce CPU load
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime == lastBarTime) return;
   lastBarTime = currentBarTime;
   
   // Process all open positions from our bot
   ManageOpenTrades();
   
   // Update info panel on chart
   if(SHOW_INFO_PANEL) UpdateInfoPanel();
}

//+------------------------------------------------------------------+
//  MANAGE OPEN TRADES
//  Applies trailing stop and break-even logic
//+------------------------------------------------------------------+
void ManageOpenTrades()
{
   // Get current ATR value
   double atrBuffer[];
   ArraySetAsSeries(atrBuffer, true);
   if(CopyBuffer(atrHandle, 0, 0, 1, atrBuffer) <= 0) return;
   double atr = atrBuffer[0];
   
   // Loop through all open positions
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      
      // Only manage positions from OUR bot (by magic number)
      if(PositionGetInteger(POSITION_MAGIC) != MAGIC_NUMBER) continue;
      
      string symbol     = PositionGetString(POSITION_SYMBOL);
      double openPrice  = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL  = PositionGetDouble(POSITION_SL);
      double currentTP  = PositionGetDouble(POSITION_TP);
      double currentBid = SymbolInfoDouble(symbol, SYMBOL_BID);
      double currentAsk = SymbolInfoDouble(symbol, SYMBOL_ASK);
      long   posType    = PositionGetInteger(POSITION_TYPE);  // 0=BUY, 1=SELL
      
      double newSL = currentSL;
      
      // ── BREAK-EVEN LOGIC ───────────────────────────────────────
      // Move SL to break-even (entry price) when 50% of TP is reached
      if(USE_BREAKEVEN)
      {
         double tpDistance = MathAbs(currentTP - openPrice);
         double halfTP     = tpDistance * 0.5;
         
         if(posType == POSITION_TYPE_BUY)
         {
            double halfWayPrice = openPrice + halfTP;
            // If price reached halfway to TP and SL is still below entry
            if(currentBid >= halfWayPrice && currentSL < openPrice)
            {
               newSL = openPrice + SymbolInfoDouble(symbol, SYMBOL_POINT);
               Print("Break-even triggered for ticket ", ticket, " on ", symbol);
            }
         }
         else  // SELL
         {
            double halfWayPrice = openPrice - halfTP;
            if(currentAsk <= halfWayPrice && currentSL > openPrice)
            {
               newSL = openPrice - SymbolInfoDouble(symbol, SYMBOL_POINT);
               Print("Break-even triggered for ticket ", ticket, " on ", symbol);
            }
         }
      }
      
      // ── TRAILING STOP LOGIC ────────────────────────────────────
      // Trail the stop loss as price moves in our favor
      if(USE_TRAILING_STOP && atr > 0)
      {
         double trailDist = atr * TRAILING_ATR_MULT;
         
         if(posType == POSITION_TYPE_BUY)
         {
            double trailSL = currentBid - trailDist;
            // Only move SL UP (never move it down)
            if(trailSL > newSL && trailSL < currentBid)
               newSL = trailSL;
         }
         else  // SELL
         {
            double trailSL = currentAsk + trailDist;
            // Only move SL DOWN (never move it up)
            if(trailSL < newSL && trailSL > currentAsk)
               newSL = trailSL;
         }
      }
      
      // ── APPLY NEW STOP LOSS ────────────────────────────────────
      // Only modify if SL actually changed (avoid unnecessary requests)
      double minDist = SymbolInfoDouble(symbol, SYMBOL_POINT) * 10;
      if(MathAbs(newSL - currentSL) > minDist)
      {
         ModifyStopLoss(ticket, newSL, currentTP);
      }
   }
}

//+------------------------------------------------------------------+
//  MODIFY STOP LOSS
//+------------------------------------------------------------------+
bool ModifyStopLoss(ulong ticket, double newSL, double currentTP)
{
   MqlTradeRequest request = {};
   MqlTradeResult  result  = {};
   
   request.action   = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.sl       = NormalizeDouble(newSL, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS));
   request.tp       = currentTP;
   
   bool sent = OrderSend(request, result);
   
   if(sent && result.retcode == TRADE_RETCODE_DONE)
   {
      Print("SL modified for ticket ", ticket, " -> New SL: ", newSL);
      return true;
   }
   else
   {
      Print("SL modification FAILED for ticket ", ticket, ". Error: ", result.retcode);
      return false;
   }
}

//+------------------------------------------------------------------+
//  UPDATE INFO PANEL (chart display)
//+------------------------------------------------------------------+
void UpdateInfoPanel()
{
   // Count our open positions
   int ourTrades = 0;
   double totalProfit = 0;
   
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetInteger(POSITION_MAGIC) == MAGIC_NUMBER)
      {
         ourTrades++;
         totalProfit += PositionGetDouble(POSITION_PROFIT);
      }
   }
   
   string info = StringFormat(
      "\n  ══ FOREX AI BOT ══\n"
      "  Open Trades : %d\n"
      "  Total P&L   : $%.2f\n"
      "  Trailing SL : %s\n"
      "  Break-Even  : %s\n"
      "  Magic #     : %d",
      ourTrades,
      totalProfit,
      USE_TRAILING_STOP ? "ON" : "OFF",
      USE_BREAKEVEN     ? "ON" : "OFF",
      MAGIC_NUMBER
   );
   
   Comment(info);
}

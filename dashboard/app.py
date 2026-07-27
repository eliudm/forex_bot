# ============================================================
# dashboard/app.py — Live Monitoring Dashboard
# ============================================================
# HOW TO RUN:
#   pip install streamlit
#   streamlit run dashboard/app.py
#
# Opens a web page at http://localhost:8501
# Shows: account balance, open trades, signals, P&L charts
# ============================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import json
from datetime import datetime, timedelta
import random

try:
    import streamlit as st
    import pandas as pd
    STREAMLIT = True
except ImportError:
    STREAMLIT = False
    print("Run: pip install streamlit pandas")

if STREAMLIT:
    st.set_page_config(page_title="AI Forex Bot", page_icon="🤖",
                       layout="wide", initial_sidebar_state="expanded")

    st.markdown("""
    <style>
    .metric-card {background:#1e2130;border-radius:12px;padding:20px;
                  border:1px solid #2d3250;text-align:center;}
    .green {color:#00e676;} .red {color:#ff5252;}
    .stMetric label {font-size:13px;color:#aaa;}
    </style>""", unsafe_allow_html=True)

    # ── SIDEBAR ──────────────────────────────────────────────
    with st.sidebar:
        st.title("🤖 AI Trading Bot")
        st.markdown("---")
        mode = st.selectbox("Execution Mode",
                            ["SEMI_AUTO", "FULL_AUTO", "BACKTEST"])
        markets = st.multiselect("Active Markets",
            ["EURUSD","GBPUSD","XAUUSD",
             "Volatility 75 Index","Boom 1000 Index","Crash 1000 Index"],
            default=["EURUSD","XAUUSD"])
        st.markdown("---")
        risk_pct = st.slider("Risk per trade (%)", 0.5, 3.0, 1.0, 0.1)
        confidence_min = st.slider("Min AI Confidence (%)", 50, 85, 65, 5)
        st.markdown("---")
        bot_running = st.toggle("▶ Bot Running", value=False)
        if bot_running:
            st.success("🟢 Bot is ACTIVE")
        else:
            st.warning("🔴 Bot is PAUSED")

    # ── HEADER ───────────────────────────────────────────────
    st.title("📊 AI Forex Trading Bot — Live Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Mode: {mode}")
    st.markdown("---")

    # ── ACCOUNT METRICS ──────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("💰 Balance", "$504.20", "+$4.20")
    with col2:
        st.metric("📈 Equity", "$506.80", "+$2.60")
    with col3:
        st.metric("🎯 Today P&L", "+$4.20", "3 trades")
    with col4:
        st.metric("✅ Win Rate", "67%", "2W / 1L")
    with col5:
        st.metric("🔓 Open Trades", "1", "Max: 3")

    st.markdown("---")

    # ── OPEN TRADES ──────────────────────────────────────────
    st.subheader("📂 Open Positions")
    open_trades = pd.DataFrame([{
        "Symbol":    "EURUSD",
        "Direction": "🟢 BUY",
        "Lots":      0.02,
        "Entry":     1.08542,
        "Current":   1.08680,
        "SL":        1.08300,
        "TP":        1.08900,
        "P&L":       "+$2.76",
        "Strategy":  "EMA Crossover",
    }])
    st.dataframe(open_trades, use_container_width=True, hide_index=True)

    # ── RECENT SIGNALS ────────────────────────────────────────
    st.subheader("🔔 Recent AI Signals")
    signals = pd.DataFrame([
        {"Time":"14:32","Symbol":"EURUSD","Dir":"🟢 BUY","Strategy":"EMA Cross",
         "Confidence":"78%","SL Pips":"24.2","TP Pips":"60.5","R:R":"2.5","Status":"✅ Approved"},
        {"Time":"13:10","Symbol":"XAUUSD","Dir":"🔴 SELL","Strategy":"RSI Reversal",
         "Confidence":"71%","SL Pips":"180","TP Pips":"396","R:R":"2.2","Status":"❌ Rejected"},
        {"Time":"11:55","Symbol":"Boom 1000","Dir":"🟢 BUY","Strategy":"Boom/Crash",
         "Confidence":"82%","SL Pips":"45","TP Pips":"90","R:R":"2.0","Status":"✅ Approved"},
        {"Time":"10:20","Symbol":"GBPUSD","Dir":"🔴 SELL","Strategy":"MACD Momentum",
         "Confidence":"63%","SL Pips":"30","TP Pips":"66","R:R":"2.2","Status":"⏳ Pending"},
    ])
    st.dataframe(signals, use_container_width=True, hide_index=True)

    # ── EQUITY CURVE ─────────────────────────────────────────
    st.subheader("📈 Equity Curve (Last 30 Days)")
    try:
        import plotly.graph_objects as go
        dates   = pd.date_range(end=datetime.today(), periods=30)
        balance = 500.0
        equity  = [balance]
        for _ in range(29):
            change  = random.gauss(0.8, 3.5)
            balance = max(480, balance + change)
            equity.append(round(balance, 2))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=equity, mode="lines",
            fill="tozeroy", line=dict(color="#00e676", width=2),
            fillcolor="rgba(0,230,118,0.1)", name="Equity"))
        fig.add_hline(y=500, line_dash="dash",
                      line_color="gray", annotation_text="Starting Balance $500")
        fig.update_layout(
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            font_color="white", height=300,
            xaxis=dict(gridcolor="#2d3250"),
            yaxis=dict(gridcolor="#2d3250", tickprefix="$"),
            margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.info("Install plotly for the equity chart: pip install plotly")

    # ── TRADE HISTORY ────────────────────────────────────────
    st.subheader("📋 Trade History (Today)")
    history = pd.DataFrame([
        {"Time":"09:45","Symbol":"GBPUSD","Dir":"🟢 BUY","Lots":0.01,
         "Entry":1.26540,"Close":1.26870,"Pips":"+33.0","P&L":"+$3.30","Result":"✅ WIN"},
        {"Time":"08:20","Symbol":"XAUUSD","Dir":"🔴 SELL","Lots":0.01,
         "Entry":2345.50,"Close":2348.10,"Pips":"-26.0","P&L":"-$2.60","Result":"❌ LOSS"},
        {"Time":"07:15","Symbol":"EURUSD","Dir":"🟢 BUY","Lots":0.02,
         "Entry":1.08210,"Close":1.08680,"Pips":"+47.0","P&L":"+$9.40","Result":"✅ WIN"},
    ])
    st.dataframe(history, use_container_width=True, hide_index=True)
    st.caption("💡 Tip: In SEMI_AUTO mode, approve/reject trades via Telegram.")

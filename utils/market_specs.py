# =============================================================================
# utils/market_specs.py — Single source of truth for pip conventions
# =============================================================================
# Before this existed, four separate modules each had their own copy of the
# same JPY/XAU/Index pip-size lookup (ai_engine/enhanced_engine.py,
# ai_engine/strategy_engine.py, backtest/backtester.py,
# bridge/paper_broker.py) — a classic setup for the copies drifting apart.
# Everything now imports pip_size() from here instead.
# =============================================================================


def pip_size(symbol: str) -> float:
    """
    The price move that counts as "1 pip" for this symbol. Used to convert
    between raw price distances and the pip counts the AI engine, risk
    manager, and lot-sizing math all reason in.
    """
    if "JPY" in symbol:
        return 0.01
    if "XAU" in symbol or "gold" in symbol.lower():
        return 0.1
    if "Index" in symbol or "VIX" in symbol.lower():
        return 0.01
    return 0.0001

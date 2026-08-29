import pandas as pd

from agents.base import AgentSignal
from agents.scanner_agent import MarketScannerAgent
from agents.setup_agent import SetupAgent
from agents.sentiment_agent import SentimentAgent, NullSentimentProvider, _load_provider as load_sentiment_provider
from agents.onchain_agent import OnChainAgent, NullOnChainProvider, is_crypto
from agents.coordinator import TradeCoordinator


class FakeAIEngine:
    def __init__(self, signal):
        self._signal = signal

    def predict(self, df, min_confidence):
        return self._signal


# ── scanner ──────────────────────────────────────────────────────────

def test_scanner_flags_abnormally_flat_market_as_not_interesting():
    df = pd.DataFrame({"atr": [0.01] * 24 + [0.0005]})  # last bar << its own 20-bar average
    result = MarketScannerAgent().scan("EURUSD", df)
    assert result.meta["interesting"] is False


def test_scanner_treats_normal_volatility_as_interesting():
    df = pd.DataFrame({"atr": [0.01] * 25})
    result = MarketScannerAgent().scan("EURUSD", df)
    assert result.meta["interesting"] is True


# ── setup agent ──────────────────────────────────────────────────────

def test_setup_agent_maps_buy_sell_wait_to_signed_score():
    buy = SetupAgent().analyze(FakeAIEngine({"action": "BUY", "confidence": 0.7}), pd.DataFrame(), 0.5)
    sell = SetupAgent().analyze(FakeAIEngine({"action": "SELL", "confidence": 0.6}), pd.DataFrame(), 0.5)
    wait = SetupAgent().analyze(FakeAIEngine({"action": "WAIT", "confidence": 0.1}), pd.DataFrame(), 0.5)

    assert buy.score == 0.7 and buy.confidence == 0.7
    assert sell.score == -0.6 and sell.confidence == 0.6
    assert wait.score == 0.0 and wait.confidence == 0.0


# ── sentiment / on-chain stubs ───────────────────────────────────────

def test_null_providers_report_zero_confidence():
    assert SentimentAgent().analyze("EURUSD").confidence == 0.0
    assert OnChainAgent().analyze("BTCUSD").confidence == 0.0


def test_onchain_agent_ignores_non_crypto_symbols():
    assert is_crypto("BTCUSD") is True
    assert is_crypto("EURUSD") is False
    result = OnChainAgent().analyze("EURUSD")
    assert "not a crypto symbol" in result.reason


def test_sentiment_provider_loader_falls_back_on_bad_path(monkeypatch):
    monkeypatch.setenv("SENTIMENT_PROVIDER", "not.a.real.module.Path")
    assert isinstance(load_sentiment_provider(), NullSentimentProvider)


def test_sentiment_provider_loader_instantiates_configured_class(monkeypatch):
    monkeypatch.setenv("SENTIMENT_PROVIDER", "agents.sentiment_agent.NullSentimentProvider")
    assert isinstance(load_sentiment_provider(), NullSentimentProvider)


# ── coordinator ──────────────────────────────────────────────────────

def test_coordinator_skips_quiet_market_without_running_setup_agent():
    df = pd.DataFrame({"atr": [0.01] * 24 + [0.0005]})
    coordinator = TradeCoordinator()
    engine = FakeAIEngine({"action": "BUY", "confidence": 0.9})

    result = coordinator.decide("EURUSD", df, engine, min_confidence=0.5)

    assert result["signal"]["action"] == "WAIT"
    assert "setup" not in result["agents"]  # never even asked the AI model


def test_coordinator_passes_through_unchanged_when_extra_agents_have_no_data():
    df = pd.DataFrame({"atr": [0.01] * 25})
    coordinator = TradeCoordinator()
    engine = FakeAIEngine({"action": "BUY", "confidence": 0.8, "sl": 1.0, "tp": 1.1})

    result = coordinator.decide("EURUSD", df, engine, min_confidence=0.5)

    assert result["signal"]["action"] == "BUY"
    assert result["signal"]["confidence"] == 0.8  # untouched: sentiment/onchain contributed nothing
    assert result["signal"]["agent_adjustment"] == 0.0


def test_coordinator_reduces_confidence_when_an_agent_disagrees(monkeypatch):
    df = pd.DataFrame({"atr": [0.01] * 25})
    coordinator = TradeCoordinator()
    coordinator.sentiment.provider = type(
        "Bearish", (), {"analyze": lambda self, symbol: AgentSignal("sentiment", -1.0, 1.0, "very bearish news")}
    )()
    engine = FakeAIEngine({"action": "BUY", "confidence": 0.6})

    result = coordinator.decide("EURUSD", df, engine, min_confidence=0.5)

    assert result["signal"]["confidence"] < 0.6

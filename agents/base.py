# =============================================================================
# agents/base.py — Shared shape for every agent's output
# =============================================================================
# Every agent in this package (scanner, setup, sentiment, on-chain) reports
# its opinion in this common shape so the coordinator can combine them
# without special-casing each one.
#
#   score      -1.0 (bearish) .. 0.0 (neutral) .. +1.0 (bullish)
#   confidence  0.0 (no opinion / no data) .. 1.0 (fully confident)
#
# confidence=0.0 is the important convention: it means "this agent has
# nothing to say," and the coordinator weights contributions by confidence,
# so a confidence=0.0 agent (like the sentiment/on-chain stubs, until a
# real data source is wired in) contributes exactly nothing — it never
# silently dilutes a real signal from the setup agent.
# =============================================================================

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AgentSignal:
    agent: str
    score: float
    confidence: float
    reason: str
    meta: Dict[str, Any] = field(default_factory=dict)


NEUTRAL_NO_DATA = "No data source configured for this agent yet"


def neutral_signal(agent: str, reason: str = NEUTRAL_NO_DATA) -> AgentSignal:
    return AgentSignal(agent=agent, score=0.0, confidence=0.0, reason=reason)

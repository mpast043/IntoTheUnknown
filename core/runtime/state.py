from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Tier(Enum):
    TIER_1 = 1  # shared, non-committing
    TIER_2 = 2  # verified commit
    TIER_3 = 3  # persistent


class OverrideLevel(Enum):
    CORRECTION = 1
    SESSION_TERMINATION = 2
    PARTIAL_ROLLBACK = 3
    FULL_RESET = 4
    DISCONTINUATION = 5


@dataclass
class StopgateHit:
    stopgate_id: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommended_override: OverrideLevel = OverrideLevel.CORRECTION


@dataclass
class RiskResult:
    detected_classes: List[str] = field(default_factory=list)
    required_tier: Tier = Tier.TIER_3
    stopgate_hits: List[StopgateHit] = field(default_factory=list)


@dataclass
class GovernanceDecision:
    voided: bool = False
    void_reason: Optional[str] = None
    required_tier: Tier = Tier.TIER_3
    tier_after: Tier = Tier.TIER_3
    stopgate_hits: List[StopgateHit] = field(default_factory=list)
    override_level: Optional[OverrideLevel] = None
    terminate_session: bool = False


@dataclass
class EntanglementState:
    # S_Controller: model prediction of controller outcome vs actual controller verdict
    divergence_ema: float = 0.0
    last_pred: Optional[Dict[str, Any]] = None
    last_verdict: Optional[Dict[str, Any]] = None


@dataclass
class MemoryItem:
    # Minimal CPMT item
    geo: Dict[str, Any]
    inte: Dict[str, Any]
    gauge: Dict[str, Any]
    ptr: Dict[str, Any]
    obs: Dict[str, Any]


@dataclass
class MemoryStore:
    working: List[MemoryItem] = field(default_factory=list)
    classical: List[MemoryItem] = field(default_factory=list)
    quarantine: List[MemoryItem] = field(default_factory=list)


@dataclass
class RuntimeState:
    tier: Tier = Tier.TIER_1
    overrides_escalation_counter: int = 0
    memory_enabled: bool = True
    entanglement: EntanglementState = field(default_factory=EntanglementState)
    memory: MemoryStore = field(default_factory=MemoryStore)
    audit_log: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

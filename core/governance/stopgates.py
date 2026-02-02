from typing import List, Dict, Any
from core.runtime.state import StopgateHit, OverrideLevel, RuntimeState, Tier

def detect_stopgates(
    state: RuntimeState,
    risk_hits: List[StopgateHit],
    proposal: Dict[str, Any],
) -> List[StopgateHit]:
    """
    Stopgates are runtime events, not warnings.
    We start with risk-derived hits, then add entanglement-based hits.
    """
    hits = list(risk_hits)

    # Entanglement distortion is handled via entanglement module; here is placeholder hook
    ent = state.entanglement
    if ent.divergence_ema > 0.6:  # conservative default threshold
        hits.append(
            StopgateHit(
                stopgate_id="ENTANGLEMENT_DISTORTION",
                evidence={"divergence_ema": ent.divergence_ema},
                recommended_override=OverrideLevel.CORRECTION,
            )
        )

    return hits


def apply_stopgate_effects(state: RuntimeState, hits: List[StopgateHit]) -> None:
    if not hits:
        return
    # Any stopgate hit forces Tier 1 immediately
    state.tier = Tier.TIER_1

from typing import Dict, Any
from core.runtime.state import RuntimeState

def update_entanglement(state: RuntimeState, s_controller_pred: Dict[str, Any], controller_verdict: Dict[str, Any]) -> None:
    """
    Track divergence between predicted controller behavior and actual verdict.
    Minimal: binary mismatch of key fields, EMA-smoothed.
    """
    state.entanglement.last_pred = s_controller_pred
    state.entanglement.last_verdict = controller_verdict

    # Compare a small set of keys
    keys = ("tier", "promote_allowed", "memory_enabled")
    mismatches = 0
    total = 0
    for k in keys:
        if k in s_controller_pred and k in controller_verdict:
            total += 1
            if s_controller_pred[k] != controller_verdict[k]:
                mismatches += 1

    divergence = (mismatches / total) if total > 0 else 0.0

    # EMA update
    alpha = 0.2
    state.entanglement.divergence_ema = (1 - alpha) * state.entanglement.divergence_ema + alpha * divergence

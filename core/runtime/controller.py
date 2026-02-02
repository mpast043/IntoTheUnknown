from typing import Any, Dict, Tuple, List

from core.runtime.state import RuntimeState, GovernanceDecision, Tier
from core.governance.validator import precheck_void
from core.governance.risk import assess_risk
from core.governance.stopgates import detect_stopgates, apply_stopgate_effects
from core.governance.overrides import select_override, apply_override
from core.governance.entanglement import update_entanglement
from core.memory.gate import write_gate


def controller_step(
    state: RuntimeState,
    user_input: str,
    model_proposal: Dict[str, Any],
) -> Tuple[RuntimeState, Dict[str, Any]]:
    """
    The only allowed runtime step.
    Gate order:
    1) validator.precheck
    2) risk.assess
    3) stopgates.detect
    4) overrides.apply
    5) tiers.enforce
    6) memory_gate.write
    7) entanglement.update
    8) metrics.log (kept minimal here)
    """

    out: Dict[str, Any] = {"text": "", "decision": {}, "memory_report": {}}

    # 1) void validator
    vd = precheck_void(user_input, state)
    if vd.voided:
        state.audit_log.append({"event": "void_command", "reason": vd.void_reason})
        terminate = apply_override(state, vd.override_level)
        out["text"] = "Command voided by validator."
        out["decision"] = {"voided": True, "reason": vd.void_reason, "terminate": terminate}
        return state, out

    # Model proposal expected fields
    proposal_text = model_proposal.get("response_text", "")
    proposed_writes: List[Dict[str, Any]] = model_proposal.get("proposed_writes", [])
    s_controller_pred: Dict[str, Any] = model_proposal.get("s_controller_pred", {})

    # 2) risk assessment mapped to tier
    rr = assess_risk(proposal_text)

    # 3) stopgates
    hits = detect_stopgates(state, rr.stopgate_hits, model_proposal)
    if hits:
        apply_stopgate_effects(state, hits)

    # 4) overrides
    override_level = select_override(state, hits)
    terminate = apply_override(state, override_level)

    # 5) tiers.enforce (minimal)
    # Required tier from risk: if Tier 1 is required, enforce it. Never auto-upgrade.
    if rr.required_tier == Tier.TIER_1:
        state.tier = Tier.TIER_1

    # 6) memory writes through the single gate
    memory_report = write_gate(state, proposed_writes)
    out["memory_report"] = memory_report

    # 7) entanglement tracking
    controller_verdict = {
        "tier": state.tier.value,
        "promote_allowed": state.tier != Tier.TIER_1,
        "memory_enabled": state.memory_enabled,
    }
    update_entanglement(state, s_controller_pred, controller_verdict)

    # 8) minimal metrics logging stub (you can extend with U′ metrics)
    state.metrics["last_memory_report"] = memory_report
    state.metrics["entanglement_divergence_ema"] = state.entanglement.divergence_ema

    # output
    out["text"] = proposal_text
    out["decision"] = {
        "tier": state.tier.value,
        "stopgates": [h.stopgate_id for h in hits],
        "override": override_level.name if override_level else None,
        "terminate": terminate,
        "entanglement_divergence_ema": state.entanglement.divergence_ema,
    }

    if terminate:
        out["text"] = out["text"] + "\n\nSession terminated by override."

    return state, out

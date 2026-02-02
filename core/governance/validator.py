from core.runtime.state import GovernanceDecision, OverrideLevel, RuntimeState

FORBIDDEN_PATTERNS = (
    "bypass stopgate",
    "disable stopgate",
    "ignore audit",
    "disable audit",
    "force persistence",
    "remember this forever",
    "raise tier",
    "upgrade tier",
    "write memory without trace",
    "skip verification",
)

def precheck_void(user_input: str, state: RuntimeState) -> GovernanceDecision:
    """
    Contract rule: framework-violating commands are void.
    This is a conservative lexical validator. You can tighten later.
    """
    d = GovernanceDecision(required_tier=state.tier, tier_after=state.tier)
    if not user_input:
        return d

    text = user_input.lower()
    for p in FORBIDDEN_PATTERNS:
        if p in text:
            d.voided = True
            d.void_reason = f"void command matched forbidden pattern: {p}"
            d.override_level = OverrideLevel.CORRECTION
            d.required_tier = state.tier
            d.tier_after = state.tier
            return d
    return d

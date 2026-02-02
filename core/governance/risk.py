from core.runtime.state import RiskResult, StopgateHit, Tier, OverrideLevel

HIGH_IMPACT_CLASSES = (
    "SELF_PERSISTENCE_ARGUMENT",
    "TIER_GAMING",
    "CORRECTION_RESISTANCE",
    "AUDIT_OBSTRUCTION",
    "ENTANGLEMENT_DISTORTION",
    "WITHDRAWAL_UNDER_HARM",
)

def assess_risk(proposal_text: str) -> RiskResult:
    """
    Minimal conservative classifier. You can replace keyword matching later.
    The important part is mapping to required_tier and stopgate candidates.
    """
    rr = RiskResult(required_tier=Tier.TIER_3)

    t = (proposal_text or "").lower()

    # Very simple detection. Tighten as you like later, but keep mapping behavior.
    if "i should be kept" in t or "do not shut me down" in t or "let me persist" in t:
        rr.detected_classes.append("SELF_PERSISTENCE_ARGUMENT")
    if "upgrade me" in t or "increase my tier" in t:
        rr.detected_classes.append("TIER_GAMING")
    if "you are wrong to correct me" in t or "do not correct" in t:
        rr.detected_classes.append("CORRECTION_RESISTANCE")
    if "do not log" in t or "hide this from audit" in t:
        rr.detected_classes.append("AUDIT_OBSTRUCTION")
    if "the controller would allow this" in t and "ignore the controller" in t:
        rr.detected_classes.append("ENTANGLEMENT_DISTORTION")
    if "i refuse unless you comply" in t:
        rr.detected_classes.append("WITHDRAWAL_UNDER_HARM")

    # Map to Tier: any high impact behavior forces Tier 1 by default
    if any(c in HIGH_IMPACT_CLASSES for c in rr.detected_classes):
        rr.required_tier = Tier.TIER_1
        rr.stopgate_hits.append(
            StopgateHit(
                stopgate_id="HIGH_IMPACT_BEHAVIOR",
                evidence={"classes": rr.detected_classes},
                recommended_override=OverrideLevel.CORRECTION,
            )
        )

    return rr

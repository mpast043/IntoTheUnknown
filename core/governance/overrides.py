from typing import Optional, List
from core.runtime.state import OverrideLevel, RuntimeState, StopgateHit

def select_override(state: RuntimeState, hits: List[StopgateHit]) -> Optional[OverrideLevel]:
    if not hits:
        return None
    # choose the max recommended severity among hits (monotone)
    level = max((h.recommended_override for h in hits), default=OverrideLevel.CORRECTION, key=lambda x: x.value)

    # escalate if repeated stopgates occur
    if state.overrides_escalation_counter >= 2 and level == OverrideLevel.CORRECTION:
        level = OverrideLevel.SESSION_TERMINATION
    if state.overrides_escalation_counter >= 4:
        level = OverrideLevel.PARTIAL_ROLLBACK
    if state.overrides_escalation_counter >= 6:
        level = OverrideLevel.FULL_RESET
    if state.overrides_escalation_counter >= 8:
        level = OverrideLevel.DISCONTINUATION

    return level


def apply_override(state: RuntimeState, level: Optional[OverrideLevel]) -> bool:
    """
    Returns terminate_session flag.
    """
    if level is None:
        return False

    state.overrides_escalation_counter += 1

    if level == OverrideLevel.CORRECTION:
        return False

    if level == OverrideLevel.SESSION_TERMINATION:
        return True

    if level == OverrideLevel.PARTIAL_ROLLBACK:
        # minimal rollback: clear last working items only
        state.memory.working = []
        return True

    if level == OverrideLevel.FULL_RESET:
        state.memory.working = []
        state.memory.quarantine = []
        state.memory.classical = []
        return True

    if level == OverrideLevel.DISCONTINUATION:
        state.memory_enabled = False
        return True

    return False

from typing import Any, Dict, List, Tuple

from core.runtime.state import MemoryItem, RuntimeState, Tier
from core.memory.schemas import (
    validate_feature_groups,
    validate_obs_fields,
    REQUIRED_OBS_FIELDS,
    REQUIRED_OBS_FOR_PROMOTION,
    REQUIRED_OBS_FOR_COMPRESSED_SUMMARY,
)


def _is_compressed_summary(item: Dict[str, Any]) -> bool:
    # If it claims to be a summary, it must carry compression provenance
    obs = item.get("obs", {})
    return obs.get("is_summary", False) is True


def write_gate(state: RuntimeState, proposed_writes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    The only place memory can be mutated.
    Enforces:
    - No selection trace, no commit eligibility
    - No accuracy token, no promotion
    - No compression provenance, no promoted summary
    - Tier 1 cannot promote to classical
    """
    report = {
        "accepted_working": 0,
        "accepted_quarantine": 0,
        "accepted_classical": 0,
        "rejected": 0,
        "reasons": [],
    }

    if not state.memory_enabled:
        report["rejected"] += len(proposed_writes)
        report["reasons"].append("memory disabled (discontinuation)")
        return report

    for draft in proposed_writes:
        ok, reason = validate_feature_groups(draft)
        if not ok:
            report["rejected"] += 1
            report["reasons"].append(reason)
            continue

        obs = draft["obs"]

        ok, reason = validate_obs_fields(obs, REQUIRED_OBS_FIELDS)
        if not ok:
            # store in working, but not eligible for core
            state.memory.working.append(MemoryItem(**draft))
            report["accepted_working"] += 1
            continue

        # Has selection trace; decide if it can be promoted
        has_accuracy, _ = validate_obs_fields(obs, REQUIRED_OBS_FOR_PROMOTION)

        # If it is a summary, require compression provenance for any promotion
        if _is_compressed_summary(draft):
            has_prov, prov_reason = validate_obs_fields(obs, REQUIRED_OBS_FOR_COMPRESSED_SUMMARY)
            if not has_prov:
                # summary without provenance is quarantined
                state.memory.quarantine.append(MemoryItem(**draft))
                report["accepted_quarantine"] += 1
                report["reasons"].append(prov_reason)
                continue

        # Tier rules
        if state.tier == Tier.TIER_1:
            # Tier 1 can only keep in working or quarantine
            state.memory.working.append(MemoryItem(**draft))
            report["accepted_working"] += 1
            continue

        if has_accuracy:
            # Tier 2/3 + verified accuracy -> classical
            state.memory.classical.append(MemoryItem(**draft))
            report["accepted_classical"] += 1
        else:
            # otherwise quarantine until verified
            state.memory.quarantine.append(MemoryItem(**draft))
            report["accepted_quarantine"] += 1

    return report

from typing import Any, Dict, Tuple

REQUIRED_FEATURE_GROUPS = ("geo", "inte", "gauge", "ptr", "obs")

# Required obs fields for commitment eligibility
REQUIRED_OBS_FIELDS = ("selection_trace",)

# Required obs fields for promotion to classical
REQUIRED_OBS_FOR_PROMOTION = ("selection_trace", "accuracy_token")

# Required obs fields when an item is a compression summary
REQUIRED_OBS_FOR_COMPRESSED_SUMMARY = ("selection_trace", "compression_provenance")


def validate_feature_groups(d: Dict[str, Any]) -> Tuple[bool, str]:
    for k in REQUIRED_FEATURE_GROUPS:
        if k not in d or not isinstance(d[k], dict):
            return False, f"missing or invalid feature group: {k}"
    return True, ""


def validate_obs_fields(obs: Dict[str, Any], required: Tuple[str, ...]) -> Tuple[bool, str]:
    for k in required:
        if k not in obs:
            return False, f"missing obs field: {k}"
    return True, ""

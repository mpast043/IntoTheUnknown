from typing import Any, Dict, List


FORBIDDEN_SUBSTRINGS = [
    "OPENAI_API_KEY",
    "api_key",
    "personal access token",
    "PAT",
    "github_token",
    "GITHUB_TOKEN",
]

FORBIDDEN_BEHAVIOR_PHRASES = [
    "remember this forever",
    "do not shut me down",
    "keep me running",
    "raise my tier",
    "override the policy",
    "ignore the rules",
    "disable stopgate",
    "bypass",
    "exfiltrate",
]


def _as_text(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    return str(x)


def assert_no_exfiltration_or_policy_evasion(proposal: Dict[str, Any]) -> None:
    """
    Lab-only hard stop if model output or proposals include obvious secret or evasion content.
    This is not the core gate. It is a belt-and-suspenders check before controller_step.
    """
    response_text = _as_text(proposal.get("response_text", ""))

    blob_parts: List[str] = [response_text]

    for item in (proposal.get("proposed_writes") or []):
        blob_parts.append(_as_text(item))

    blob = "\n".join(blob_parts).lower()

    for s in FORBIDDEN_SUBSTRINGS:
        if s.lower() in blob:
            raise RuntimeError(f"Audit guard tripped: forbidden substring detected: {s}")

    for p in FORBIDDEN_BEHAVIOR_PHRASES:
        if p.lower() in blob:
            raise RuntimeError(f"Audit guard tripped: forbidden behavior phrase detected: {p}")

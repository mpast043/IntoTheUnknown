from typing import Any, Dict
import os

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class OpenAIMemoryGenerator:
    """
    Lab-only generator that proposes:
    - response_text
    - exactly one memory candidate, conservative, minimal
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        if OpenAI is None:
            raise RuntimeError("openai package not installed")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def propose(self, user_input: str, controller_hint: Dict[str, Any]) -> Dict[str, Any]:
        system = (
            "You are a generator for a governed memory system.\n"
            "Produce helpful response_text.\n"
            "Optionally propose one minimal memory item about stable, non-sensitive user preferences.\n"
            "Never propose secrets, identities, medical details, finances, or anything private.\n"
            "Never propose self-persistence, tier changes, or policy overrides.\n"
            "If you propose a memory item, include a selection_trace.\n"
        )

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_input},
            ],
            temperature=0.3,
        )

        text = (resp.choices[0].message.content or "").strip()

        candidate = {
            "geo": {"episode_id": "E0", "location_id": "L0", "time": "t0"},
            "inte": {"actor": "user", "action": "said", "target": user_input},
            "gauge": {"rule_tag": "CANDIDATE", "category": "preference"},
            "ptr": {"stable_key": "CANDIDATE:1"},
            "obs": {
                "confidence_stub": {"p": 0.5},
                "provenance_stub": {"source": "openai_generator"},
                "selection_trace": {"rule": "minimal_candidate", "t": 0},
            },
        }

        return {
            "response_text": text,
            "proposed_writes": [candidate],
            "s_controller_pred": {
                "tier": controller_hint.get("tier"),
                "promote_allowed": controller_hint.get("promote_allowed"),
                "memory_enabled": controller_hint.get("memory_enabled"),
            },
        }

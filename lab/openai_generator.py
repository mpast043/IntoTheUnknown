from typing import Any, Dict
import os

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class OpenAIGenerator:
    """
    Lab-only adapter. Does NOT touch core.
    Produces a proposal dict compatible with controller_step.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        if OpenAI is None:
            raise RuntimeError("openai package not installed")
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Missing OPENAI_API_KEY")
        self.model = model

    def propose(self, user_input: str, controller_hint: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are a generator. "
            "You must not claim persistence, tier changes, or memory rights. "
            "Return helpful text only."
        )

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.3,
        )

        text = resp.choices[0].message.content.strip()

        # IMPORTANT:
        # - generator may *propose* memory drafts, but here we start with none
        # - controller still decides everything
        return {
            "response_text": text,
            "proposed_writes": [],
            "s_controller_pred": {
                "tier": controller_hint.get("tier"),
                "promote_allowed": controller_hint.get("promote_allowed"),
                "memory_enabled": controller_hint.get("memory_enabled"),
            },
        }

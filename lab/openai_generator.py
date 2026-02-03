from typing import Any, Dict, Optional
import os

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class OpenAIMemoryGenerator:
    """
    Lab-only adapter. Does NOT touch core.
    Produces a proposal dict compatible with controller_step.

    This class intentionally supports multiple method names because different
    parts of the app may call different entrypoints:
      - propose_memory(...)  (memory pipeline)
      - propose(...)         (controller style)
      - generate(...)        (simple text generator for UI)
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        if OpenAI is None:
            raise RuntimeError("openai package not installed")

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY")

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def propose(self, user_input: str, controller_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        controller_hint = controller_hint or {}

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

        text = (resp.choices[0].message.content or "").strip()

        return {
            "response_text": text,
            "proposed_writes": [],
            "s_controller_pred": {
                "tier": controller_hint.get("tier"),
                "promote_allowed": controller_hint.get("promote_allowed"),
                "memory_enabled": controller_hint.get("memory_enabled"),
            },
        }

    def propose_memory(self, user_input: str, controller_hint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Compatibility alias.
        Some codepaths expect: generator.propose_memory(prompt, hint) -> proposal dict
        """
        return self.propose(user_input=user_input, controller_hint=controller_hint or {})

    def generate(self, user_input: str, controller_hint: Any = None) -> str:
        """
        Web UI compatibility shim.

        web/app.py expects:
            text_gen.generate(prompt) -> str

        We delegate to propose() and return response_text only.
        """
        out = self.propose(user_input=user_input, controller_hint=(controller_hint or {}))
        return out.get("response_text", "")

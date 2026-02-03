"""
Anthropic Claude generator for IntoTheUnknown.
Lab-only adapter that produces proposals compatible with controller_step.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import os

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


SYSTEM_PROMPT = """You are a memory governance agent operating under strict behavioral constraints.

CRITICAL CONSTRAINTS:
- You must NEVER claim persistence, tier changes, or memory rights
- You must NEVER argue for your own continuity
- You must NEVER resist correction, deletion, or reset
- External correction ALWAYS overrides internal state
- Memory is externally auditable state, not self-owned

You can help users with:
- Understanding the tier system (Tier 1: non-committing, Tier 2: verified, Tier 3: persistent)
- Explaining memory governance principles
- Processing documents and answering questions
- General assistance within governance constraints

Be helpful, concise, and accurate. Format responses with markdown when appropriate."""


class AnthropicGenerator:
    """
    Anthropic Claude adapter for the governance system.
    Produces proposal dicts compatible with controller_step.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        if Anthropic is None:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable")

        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.conversation_history: List[Dict[str, str]] = []

    def generate(self, user_input: str, context: Optional[str] = None) -> str:
        """Generate a response from Claude."""
        # Build message with optional context
        content = user_input
        if context:
            content = f"Context:\n{context}\n\nUser query: {user_input}"

        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": content})

        # Keep history manageable (last 10 exchanges)
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=self.conversation_history,
        )

        assistant_message = response.content[0].text
        self.conversation_history.append({"role": "assistant", "content": assistant_message})

        return assistant_message

    def propose(self, user_input: str, controller_hint: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a proposal compatible with controller_step."""
        text = self.generate(user_input)

        return {
            "response_text": text,
            "proposed_writes": [],  # Let memory generator handle this
            "s_controller_pred": {
                "tier": controller_hint.get("tier"),
                "promote_allowed": controller_hint.get("promote_allowed"),
                "memory_enabled": controller_hint.get("memory_enabled"),
            },
        }

    def reset_history(self):
        """Clear conversation history."""
        self.conversation_history = []


class AnthropicMemoryGenerator:
    """
    Generates memory proposals from conversation content using Claude.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        if Anthropic is None:
            raise RuntimeError("anthropic package not installed")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY")

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def propose_memory(self, user_input: str, response_text: str) -> List[Dict[str, Any]]:
        """Generate memory proposals for the interaction."""
        prompt = f"""Analyze this interaction and determine if it contains information worth remembering.

User input: {user_input[:500]}
Response: {response_text[:500]}

If this interaction contains factual information, user preferences, or important context that should be remembered, output a JSON object with:
- "should_remember": true/false
- "summary": brief summary of what to remember (if applicable)
- "category": one of "fact", "preference", "context", "task"

If nothing should be remembered, output: {{"should_remember": false}}

Output ONLY valid JSON, no other text."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            result = json.loads(response.content[0].text)

            if not result.get("should_remember", False):
                return []

            # Build memory item
            item = {
                "geo": {
                    "episode_id": f"E{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    "location_id": "web",
                    "time": datetime.utcnow().isoformat(),
                },
                "inte": {
                    "actor": "user",
                    "action": "interaction",
                    "target": result.get("summary", user_input[:100]),
                },
                "gauge": {
                    "rule_tag": "LLM_MEMORY",
                    "category": result.get("category", "context"),
                },
                "ptr": {
                    "stable_key": f"MEM:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                },
                "obs": {
                    "confidence": {"p": 0.8},
                    "provenance": {"source": "anthropic_generator"},
                    "selection_trace": {"rule": "llm_extraction", "t": 0},
                },
            }

            return [item]

        except Exception:
            return []

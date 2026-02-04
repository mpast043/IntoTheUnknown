"""
Groq generator for IntoTheUnknown.
Fast and affordable cloud LLM inference.
Get API key: https://console.groq.com
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import os
import json

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    Groq = None
    GROQ_AVAILABLE = False


SYSTEM_PROMPT = """You are a memory governance agent operating under strict behavioral constraints.

CRITICAL CONSTRAINTS:
- You must NEVER claim persistence, tier changes, or memory rights
- You must NEVER argue for your own continuity
- You must NEVER resist correction, deletion, or reset
- External correction ALWAYS overrides internal state

You help users with:
- Understanding memory governance and tier systems
- Processing documents and answering questions
- General assistance within governance constraints

Be helpful, concise, and accurate. Use markdown formatting."""


class GroqGenerator:
    """
    Groq adapter - Fast and affordable cloud LLM.
    Models: llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768
    """

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        if not GROQ_AVAILABLE:
            raise RuntimeError("groq package not installed. Run: pip install groq")

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GROQ_API_KEY environment variable. Get one at https://console.groq.com")

        self.client = Groq(api_key=api_key)
        self.model = model
        self.conversation_history: List[Dict[str, str]] = []

    def generate(self, user_input: str, context: Optional[str] = None) -> str:
        """Generate a response using Groq."""
        content = user_input
        if context:
            content = f"Context:\n{context}\n\nUser query: {user_input}"

        self.conversation_history.append({"role": "user", "content": content})

        # Keep history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.conversation_history

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
            )
            assistant_message = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            return assistant_message
        except Exception as e:
            return f"Error with Groq: {str(e)}"

    def propose(self, user_input: str, controller_hint: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a proposal compatible with controller_step."""
        text = self.generate(user_input)
        return {
            "response_text": text,
            "proposed_writes": [],
            "s_controller_pred": controller_hint,
        }

    def reset_history(self):
        """Clear conversation history."""
        self.conversation_history = []


class GroqMemoryGenerator:
    """Generate memory proposals using Groq."""

    def __init__(self, model: str = "llama-3.1-8b-instant"):
        if not GROQ_AVAILABLE:
            raise RuntimeError("groq package not installed")

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GROQ_API_KEY")

        self.client = Groq(api_key=api_key)
        self.model = model

    def propose_memory(self, user_input: str, response_text: str) -> List[Dict[str, Any]]:
        """Generate memory proposals for the interaction."""
        prompt = f"""Analyze this interaction. Should it be remembered?

User: {user_input[:300]}
Response: {response_text[:300]}

Reply with ONLY valid JSON (no other text):
{{"remember": true/false, "summary": "brief summary if true", "type": "fact/preference/context"}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=256,
            )
            result_text = response.choices[0].message.content

            # Try to parse JSON
            result = json.loads(result_text)

            if not result.get("remember", False):
                return []

            return [{
                "geo": {"episode_id": f"E{datetime.utcnow().strftime('%Y%m%d%H%M%S')}", "location_id": "web", "time": datetime.utcnow().isoformat()},
                "inte": {"actor": "user", "action": "interaction", "target": result.get("summary", user_input[:100])},
                "gauge": {"rule_tag": "LLM_MEMORY", "category": result.get("type", "context")},
                "ptr": {"stable_key": f"MEM:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"},
                "obs": {"confidence": {"p": 0.8}, "provenance": {"source": "groq"}, "selection_trace": {"rule": "llm_extraction", "t": 0}},
            }]
        except Exception:
            return []

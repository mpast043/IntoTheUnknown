from typing import Any, Dict, List, Optional
import os

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


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


class OpenAIGenerator:
    """
    OpenAI adapter for text generation.
    Compatible with the same interface as Ollama/Groq generators.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        if OpenAI is None:
            raise RuntimeError("openai package not installed")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.conversation_history: List[Dict[str, str]] = []

    def generate(self, user_input: str, context: Optional[str] = None) -> str:
        """Generate a response using OpenAI."""
        content = user_input
        if context:
            content = f"Context:\n{context}\n\nUser query: {user_input}"

        self.conversation_history.append({"role": "user", "content": content})

        # Keep history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.conversation_history

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
            )
            text = resp.choices[0].message.content.strip()
            self.conversation_history.append({"role": "assistant", "content": text})
            return text
        except Exception as e:
            return f"Error with OpenAI: {str(e)}"

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

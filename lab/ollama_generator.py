"""
Ollama generator for IntoTheUnknown.
Free, local LLM - no API costs. Requires Ollama installed locally.
Install: https://ollama.ai
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


OLLAMA_BASE_URL = "http://localhost:11434"

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


class OllamaGenerator:
    """
    Ollama adapter - FREE local LLM inference.
    Requires Ollama running locally: ollama serve
    """

    def __init__(self, model: str = "llama3.2", base_url: str = OLLAMA_BASE_URL):
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests package not installed. Run: pip install requests")

        self.model = model
        self.base_url = base_url
        self.conversation_history: List[Dict[str, str]] = []

        # Test connection
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama not responding at {base_url}")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Cannot connect to Ollama at {base_url}. Is it running? Start with: ollama serve")

    def generate(self, user_input: str, context: Optional[str] = None) -> str:
        """Generate a response using Ollama."""
        content = user_input
        if context:
            content = f"Context:\n{context}\n\nUser query: {user_input}"

        self.conversation_history.append({"role": "user", "content": content})

        # Keep history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.conversation_history

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                },
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            assistant_message = result.get("message", {}).get("content", "")
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            return assistant_message
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"

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

    @staticmethod
    def list_models(base_url: str = OLLAMA_BASE_URL) -> List[str]:
        """List available Ollama models."""
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [m["name"] for m in models]
        except Exception:
            return []


class OllamaMemoryGenerator:
    """Generate memory proposals using Ollama."""

    def __init__(self, model: str = "llama3.2", base_url: str = OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url

    def propose_memory(self, user_input: str, response_text: str) -> List[Dict[str, Any]]:
        """Generate memory proposals for the interaction."""
        prompt = f"""Analyze this interaction. Should it be remembered?

User: {user_input[:300]}
Response: {response_text[:300]}

Reply with ONLY valid JSON:
{{"remember": true/false, "summary": "brief summary if true", "type": "fact/preference/context"}}"""

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=30,
            )
            resp.raise_for_status()
            result_text = resp.json().get("response", "")

            # Try to parse JSON from response
            result = json.loads(result_text)

            if not result.get("remember", False):
                return []

            return [{
                "geo": {"episode_id": f"E{datetime.utcnow().strftime('%Y%m%d%H%M%S')}", "location_id": "web", "time": datetime.utcnow().isoformat()},
                "inte": {"actor": "user", "action": "interaction", "target": result.get("summary", user_input[:100])},
                "gauge": {"rule_tag": "LLM_MEMORY", "category": result.get("type", "context")},
                "ptr": {"stable_key": f"MEM:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"},
                "obs": {"confidence": {"p": 0.7}, "provenance": {"source": "ollama"}, "selection_trace": {"rule": "llm_extraction", "t": 0}},
            }]
        except Exception:
            return []

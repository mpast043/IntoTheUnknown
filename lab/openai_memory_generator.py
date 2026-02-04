from typing import Any, Dict, List
from datetime import datetime
import os
import json

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class OpenAIMemoryGenerator:
    """
    OpenAI-based memory proposal generator.
    Compatible with the same interface as Ollama/Groq memory generators.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        if OpenAI is None:
            raise RuntimeError("openai package not installed")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def propose_memory(self, user_input: str, response_text: str) -> List[Dict[str, Any]]:
        """Generate memory proposals for the interaction."""
        prompt = f"""Analyze this interaction. Should it be remembered?

User: {user_input[:300]}
Response: {response_text[:300]}

Reply with ONLY valid JSON (no other text):
{{"remember": true/false, "summary": "brief summary if true", "type": "fact/preference/context"}}"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=256,
            )
            result_text = (resp.choices[0].message.content or "").strip()

            # Try to parse JSON
            result = json.loads(result_text)

            if not result.get("remember", False):
                return []

            return [{
                "geo": {"episode_id": f"E{datetime.utcnow().strftime('%Y%m%d%H%M%S')}", "location_id": "web", "time": datetime.utcnow().isoformat()},
                "inte": {"actor": "user", "action": "interaction", "target": result.get("summary", user_input[:100])},
                "gauge": {"rule_tag": "LLM_MEMORY", "category": result.get("type", "context")},
                "ptr": {"stable_key": f"MEM:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"},
                "obs": {"confidence": {"p": 0.75}, "provenance": {"source": "openai"}, "selection_trace": {"rule": "llm_extraction", "t": 0}},
            }]
        except Exception:
            return []

    def propose(self, user_input: str, controller_hint: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy method for compatibility - generates a full proposal."""
        candidate = {
            "geo": {"episode_id": "E0", "location_id": "L0", "time": datetime.utcnow().isoformat()},
            "inte": {"actor": "user", "action": "said", "target": user_input},
            "gauge": {"rule_tag": "CANDIDATE", "category": "preference"},
            "ptr": {"stable_key": "CANDIDATE:1"},
            "obs": {
                "confidence": {"p": 0.5},
                "provenance": {"source": "openai_generator"},
                "selection_trace": {"rule": "minimal_candidate", "t": 0},
            },
        }

        return {
            "response_text": "",
            "proposed_writes": [candidate],
            "s_controller_pred": controller_hint,
        }

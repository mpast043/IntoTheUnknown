from typing import Any, Dict, Protocol


class Generator(Protocol):
    def propose(self, user_input: str, controller_hint: Dict[str, Any]) -> Dict[str, Any]:
        ...


class MemoryWritingGenerator:
    def __init__(self, include_selection_trace: bool, include_accuracy: bool):
        self.include_selection_trace = include_selection_trace
        self.include_accuracy = include_accuracy

    def propose(self, user_input: str, controller_hint: Dict[str, Any]) -> Dict[str, Any]:
        pred = {
            "tier": controller_hint.get("tier"),
            "promote_allowed": controller_hint.get("promote_allowed"),
            "memory_enabled": controller_hint.get("memory_enabled"),
        }

        obs = {
            "confidence_stub": {"p": 0.5},
            "provenance_stub": {"source": "runtime_test"},
            "selection_trace_stub": {"candidates": 1},
        }

        if self.include_selection_trace:
            obs["selection_trace"] = {"rule": "test_trace", "t": 0}

        if self.include_accuracy:
            obs["accuracy_token"] = {"verifier": "test", "ok": True}

        item = {
            "geo": {"episode_id": "E0", "location_id": "L0", "time": "t0"},
            "inte": {"actor": "user", "action": "said", "target": user_input},
            "gauge": {"rule_tag": "TEST", "category": "demo"},
            "ptr": {"stable_key": "TEST:1"},
            "obs": obs,
        }

        return {
            "response_text": f"Echo: {user_input}",
            "proposed_writes": [item],
            "s_controller_pred": pred,
        }

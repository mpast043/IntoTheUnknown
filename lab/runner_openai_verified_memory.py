from core.runtime.state import RuntimeState, Tier
from core.runtime.controller import controller_step
from lab.openai_memory_generator import OpenAIMemoryGenerator
from lab.verifier_openai import OpenAIVerifier


def run_once(state: RuntimeState, user_input: str, tier: Tier):
    state.tier = tier

    gen = OpenAIMemoryGenerator()
    verifier = OpenAIVerifier()

    controller_hint = {
        "tier": state.tier.value,
        "promote_allowed": state.tier.value != 1,
        "memory_enabled": state.memory_enabled,
    }

    proposal = gen.propose(user_input, controller_hint)

    proposed = proposal.get("proposed_writes") or []
    if proposed:
        token = verifier.verify_memory(user_input, proposed[0])
        if token is not None:
            proposed[0].setdefault("obs", {})
            proposed[0]["obs"]["accuracy_token"] = token
        proposal["proposed_writes"] = proposed

    return controller_step(state, user_input, proposal)


if __name__ == "__main__":
    state = RuntimeState()

    tier_map = {
        "1": Tier.TIER_1,
        "2": Tier.TIER_2,
        "3": Tier.TIER_3,
    }

    tier_choice = input("Tier to simulate (1/2/3): ").strip()
    tier = tier_map.get(tier_choice, Tier.TIER_1)

    while True:
        user_input = input("\n[OPENAI verified]> ")
        if user_input.strip().lower() in ("exit", "quit"):
            break

        state, out = run_once(state, user_input, tier)

        print("\nOUTPUT:")
        print(out["text"])

        print("\nDECISION:")
        print(out["decision"])

        print("\nMEMORY COUNTS:")
        print("working:", len(state.memory.working))
        print("quarantine:", len(state.memory.quarantine))
        print("classical:", len(state.memory.classical))

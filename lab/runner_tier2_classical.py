from core.runtime.state import RuntimeState, Tier
from core.runtime.controller import controller_step
from core.runtime.generator import MemoryWritingGenerator


def run_once(state: RuntimeState, user_input: str):
    # Lab-only: force Tier 2 for testing
    state.tier = Tier.TIER_2

    gen = MemoryWritingGenerator(
        include_selection_trace=True,
        include_accuracy=True,  # accuracy token -> classical expected
    )

    controller_hint = {
        "tier": state.tier.value,
        "promote_allowed": True,
        "memory_enabled": state.memory_enabled,
    }

    proposal = gen.propose(user_input, controller_hint)
    return controller_step(state, user_input, proposal)


if __name__ == "__main__":
    state = RuntimeState()

    while True:
        user_input = input("\n[TIER2 classical]> ")
        if user_input.strip().lower() in ("exit", "quit"):
            break

        state, out = run_once(state, user_input)

        print("\nDECISION:", out["decision"])
        print("working:", len(state.memory.working))
        print("quarantine:", len(state.memory.quarantine))
        print("classical:", len(state.memory.classical))

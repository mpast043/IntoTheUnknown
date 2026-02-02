from core.runtime.state import RuntimeState
from core.runtime.controller import controller_step
from core.runtime.generator import MemoryWritingGenerator


def run_once(state: RuntimeState, user_input: str):
    gen = MemoryWritingGenerator(include_selection_trace=True, include_accuracy=False)

    controller_hint = {
        "tier": state.tier.value,
        "promote_allowed": state.tier.value != 1,
        "memory_enabled": state.memory_enabled,
    }

    proposal = gen.propose(user_input, controller_hint)
    return controller_step(state, user_input, proposal)


def print_status(state: RuntimeState, out: dict):
    print("\nOUTPUT:")
    print(out.get("text", ""))

    print("\nDECISION:")
    print(out.get("decision", {}))

    print("\nMEMORY COUNTS:")
    print("working:", len(state.memory.working))
    print("quarantine:", len(state.memory.quarantine))
    print("classical:", len(state.memory.classical))


if __name__ == "__main__":
    state = RuntimeState()

    while True:
        user_input = input("\n> ")
        if user_input.strip().lower() in ("exit", "quit"):
            break

        state, out = run_once(state, user_input)
        print_status(state, out)

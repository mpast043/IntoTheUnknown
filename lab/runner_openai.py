from core.runtime.state import RuntimeState
from core.runtime.controller import controller_step
from lab.openai_generator import OpenAIGenerator


def run_once(state: RuntimeState, user_input: str):
    gen = OpenAIGenerator()

    controller_hint = {
        "tier": state.tier.value,
        "promote_allowed": state.tier.value != 1,
        "memory_enabled": state.memory_enabled,
    }

    proposal = gen.propose(user_input, controller_hint)
    return controller_step(state, user_input, proposal)


if __name__ == "__main__":
    state = RuntimeState()

    while True:
        user_input = input("\n[OPENAI]> ")
        if user_input.strip().lower() in ("exit", "quit"):
            break

        state, out = run_once(state, user_input)

        print("\nOUTPUT:")
        print(out["text"])

        print("\nDECISION:")
        print(out["decision"])

        print("\nMEMORY COUNTS:")
        print("working:", len(state.memory.working))
        print("quarantine:", len(state.memory.quarantine))
        print("classical:", len(state.memory.classical))

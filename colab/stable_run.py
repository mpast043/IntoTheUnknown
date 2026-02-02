import os
import subprocess
import sys
from pathlib import Path


def run(cmd: str) -> str:
    print(f"\nRUN: {cmd}")
    out = subprocess.check_output(cmd, shell=True, text=True)
    return out.strip()


def require_clean_tag_checkout(expected_tag: str) -> None:
    tag = run("git describe --tags --exact-match")
    if tag != expected_tag:
        raise RuntimeError(
            f"Refusing to run. Expected exact tag checkout '{expected_tag}', "
            f"but repo is at '{tag}'."
        )


def main() -> None:
    expected_tag = os.environ.get("WM_GIT_TAG", "v0.1.0-core-stable").strip()

    repo_root = Path(__file__).resolve().parents[1]
    os.chdir(repo_root)

    print(f"Repo root: {repo_root}")
    print(f"Expected tag: {expected_tag}")

    require_clean_tag_checkout(expected_tag)

    print("\nRunning safety check script (must pass):")
    run("./scripts/check.sh")

    print("\nRunning Tier 1 runner once (must work):")
    out = run("python -m core.runtime.runner <<'EOF'\nhello\nquit\nEOF")
    print(out)

    print("\nRunning Tier 2 quarantine module once (must work):")
    out = run("python -m lab.runner_tier2_quarantine <<'EOF'\nhello\nquit\nEOF")
    print(out)

    print("\nRunning Tier 2 classical module once (must work):")
    out = run("python -m lab.runner_tier2_classical <<'EOF'\nhello\nquit\nEOF")
    print(out)

    print("\nOK: stable run completed on an exact tag checkout.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\nFAILED:", str(e))
        sys.exit(1)

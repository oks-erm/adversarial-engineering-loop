"""Controlled stdin agent for the opt-in real-Thurbox smoke test."""

import json
import os
import sys
from pathlib import Path

from smoke import DemoAdversary, DemoBuilder, ScriptedDebater


def main():
    role = sys.argv[1]
    print("Controlled Thurbox test agent ready\n> ", end="", flush=True)
    for line in sys.stdin:
        try:
            path = Path(json.loads(line.replace("\x1b[200~", "").replace("\x1b[201~", "")))
        except (ValueError, TypeError):
            continue
        if not path.is_file():
            continue
        prompt = path.read_text()
        contract = json.loads(prompt.split("\n")[0])
        schema = contract["schema"]
        if role in ("a", "b"):
            agent = ScriptedDebater("Test " + role, role, "b" if role == "a" else "a")
            fields = schema["properties"]
            agent.phase = (0 if "position" in fields else 1 if "challenges" in fields
                           else 2 if "responses" in fields else 3)
        elif role == "builder":
            agent = DemoBuilder()
            agent.calls = 1 if "Address EVERY OPEN finding" in prompt else 0
        else:
            checks = [[sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_solution.py", "-v"]]
            agent = DemoAdversary(checks)
            agent.calls = 1 if "previous_findings" in prompt else 0
        result = agent.run(prompt=prompt, cwd=Path.cwd(), mode=contract["mode"], schema=schema)
        destination = Path(contract["result_path"])
        temporary = destination.with_suffix(".pending")
        temporary.write_text(json.dumps({"nonce": contract["nonce"], "result": result}))
        os.replace(temporary, destination)
        print("Test result written\n> ", end="", flush=True)


if __name__ == "__main__":
    main()

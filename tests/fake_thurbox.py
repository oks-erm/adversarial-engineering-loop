"""Subprocess contract double: only public CLI verbs used by the adapter."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

root = Path(os.environ["FAKE_THURBOX_ROOT"])
args = [arg for arg in sys.argv[1:] if arg != "--json"]
if os.environ.get("FAKE_CLI_ERROR"):
    if os.environ.get("FAKE_CLI_WARNING"):
        print("unrelated startup warning", file=sys.stderr)
    print(json.dumps({"error": "agent is not registered", "error_kind": "other"}))
    sys.exit(1)
with (root / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps(args) + "\n")


def option(flag):
    return args[args.index(flag) + 1]


if args[:2] == ["session", "create"]:
    identifier = "session-" + str(len(list(root.glob("session-*.json"))) + 1)
    cwd = Path(option("--repo-path"))
    worktrees = []
    if "--worktree-branch" in args:
        branch = option("--worktree-branch")
        path = root / (identifier + "-worktree")
        subprocess.run(["git", "-C", str(cwd), "worktree", "add", "-b", branch,
                        str(path), option("--base-branch")], check=True, capture_output=True)
        if os.environ.get("FAKE_BAD_WORKTREE") != "1":
            cwd = path
        worktrees = [dict(branch=branch, worktree_path=str(cwd))]
    result = dict(id=identifier, cwd=str(cwd), worktrees=worktrees)
    (root / (identifier + ".json")).write_text(json.dumps(result))
    print(json.dumps(result))
elif args[:2] == ["session", "send"]:
    prompt_path = Path(json.loads(args[3].split("\n")[0]))
    prompt = prompt_path.read_text()
    contract = json.loads(prompt.split("\n")[0])
    result_path = Path(contract["result_path"])
    mode = os.environ.get("FAKE_RESULT_MODE", "valid")
    if mode == "valid":
        reply = {"answer": "ok"}
        if os.environ.get("FAKE_REPLIES_PATH"):
            index_path = root / "reply-index"
            index = int(index_path.read_text()) if index_path.exists() else 0
            reply = json.loads(Path(os.environ["FAKE_REPLIES_PATH"]).read_text())[index]
            index_path.write_text(str(index + 1))
        result_path.write_text(json.dumps(dict(nonce=contract["nonce"], result=reply)))
    elif mode == "nonce":
        result_path.write_text(json.dumps(dict(nonce="old", result={"answer": "ok"})))
    elif mode == "malformed":
        result_path.write_text("not JSON")
    elif mode == "schema":
        result_path.write_text(json.dumps(dict(nonce=contract["nonce"], result={"wrong": True})))
    print(json.dumps({"submitted": True}))
elif args[:2] == ["session", "get"]:
    print(json.dumps({"state": "lost" if os.environ.get("FAKE_RESULT_MODE") == "crash" else "running"}))
elif args[:2] == ["session", "stop"]:
    if os.environ.get("FAKE_STOP_FAIL") == "1":
        sys.exit(1)
    print(json.dumps({"ok": True}))
else:
    raise SystemExit("unsupported fake command: " + repr(args))

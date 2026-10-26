"""Small agent contract, strict JSON schemas and atomic run persistence."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class Agent(Protocol):
    name: str

    def run(self, *, prompt: str, cwd: Path, mode: str, schema: dict) -> dict: ...


TEXT = {"type": "string", "minLength": 1}
TEXTS = {"type": "array", "items": TEXT}


def obj(**properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def sequence(item: dict) -> dict:
    return {"type": "array", "items": item}


def choice(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


def validate(value: Any, schema: dict, path: str = "result") -> None:
    kind = schema["type"]
    valid_type = {
        "object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": type(value) in (int, float),
    }[kind]
    if not valid_type:
        raise ValueError(f"{path}: expected {kind}")
    if kind == "object":
        properties = schema["properties"]
        if set(value) != set(properties):
            raise ValueError(f"{path}: fields must be {sorted(properties)}")
        for key, child in properties.items():
            validate(value[key], child, f"{path}.{key}")
    elif kind == "array":
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")
    elif kind == "string":
        if len(value.strip()) < schema.get("minLength", 0):
            raise ValueError(f"{path}: empty text")
        if "enum" in schema and value not in schema["enum"]:
            raise ValueError(f"{path}: expected one of {schema['enum']}")
    elif not math.isfinite(value) or not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf):
        raise ValueError(f"{path}: number out of range")


def unique_ids(items: list[dict], field: str = "id") -> set[str]:
    ids = [item[field] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {field}")
    return set(ids)


def redact(text: str) -> str:
    for key, value in os.environ.items():
        if re.search(r"TOKEN|SECRET|PASSWORD|CREDENTIAL|API_KEY|PRIVATE_KEY", key, re.I) and len(value) >= 8:
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"\b(?:sk-[\w-]{12,}|gh[pousr]_[\w]{12,}|github_pat_[\w]{12,})", "[REDACTED]", text)
    return re.sub(r"(?i)(authorization\s*:\s*bearer\s+)\S+", r"\1[REDACTED]", text)


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def atomic_write(path: Path, content: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    def __init__(self, root: Path, workflow: str, transitions: dict[str, set[str]]):
        self.root = root
        root.mkdir(parents=True, mode=0o700, exist_ok=False)
        self.transitions = transitions
        self.data = {"workflow": workflow, "state": "INITIALIZED", "history": ["INITIALIZED"],
                     "created_at": datetime.now(timezone.utc).isoformat()}
        self.save()

    def write(self, filename: str, content: str) -> None:
        if Path(filename).name != filename:
            raise ValueError("artifact filename must be a single path component")
        atomic_write(self.root / filename, redact(content))

    def json(self, filename: str, value: Any) -> None:
        # Redact values, not serialized JSON: secrets can contain JSON delimiters.
        def clean(item: Any) -> Any:
            if isinstance(item, str):
                return redact(item)
            if isinstance(item, list):
                return [clean(v) for v in item]
            if isinstance(item, dict):
                return {k: clean(v) for k, v in item.items()}
            return item
        atomic_write(self.root / filename, dumps(clean(value)) + "\n")

    def save(self) -> None:
        self.json("state.json", self.data)

    def transition(self, target: str, **fields: Any) -> None:
        current = self.data["state"]
        if target not in self.transitions.get(current, set()):
            raise ValueError(f"invalid transition {current} -> {target}")
        self.data.update(fields, state=target)
        self.data["history"].append(target)
        self.save()

    def fail(self, error: Exception) -> None:
        self.transition("FAILED", error=f"{type(error).__name__}: {error}", outcome="FAILED")


def turn(agent: Agent, *, prompt: str, cwd: Path, mode: str, schema: dict) -> dict:
    value = agent.run(prompt=prompt, cwd=cwd, mode=mode, schema=schema)
    validate(value, schema)
    return value


def sections(record: dict) -> str:
    """Render evidence fields, preserving recommendations instead of paraphrasing."""
    parts = []
    for key, value in record.items():
        heading = key.replace("_", " ").title()
        body = "\n".join(f"- {v}" for v in value) if isinstance(value, list) and all(isinstance(v, str) for v in value) else (
            dumps(value) if isinstance(value, (dict, list)) else str(value))
        parts.append(f"### {heading}\n\n{body}\n")
    return "\n".join(parts)

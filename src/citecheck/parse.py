"""Read a model answer into a ``WorkRecord`` and five reference strings."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from .records import WorkRecord, record_from_dict
from .render import STYLES


@dataclass
class Parsed:
    ok: bool
    record: WorkRecord | None = None
    citations: dict[str, str] = field(default_factory=dict)
    error: str = ""


def first_json_object(text: str) -> str | None:
    """The first balanced ``{...}`` block. Code fences and prose around it are ignored."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def parse_answer(raw: str, work_id: str) -> Parsed:
    block = first_json_object(raw or "")
    if block is None:
        return Parsed(False, error="no JSON object in the answer")
    try:
        data = json.loads(block)
    except json.JSONDecodeError as exc:
        return Parsed(False, error=f"invalid JSON: {exc.msg}")
    if not isinstance(data, dict):
        return Parsed(False, error="the JSON value is not an object")
    try:
        record = record_from_dict({**data, "id": work_id}, work_id)
    except ValidationError as exc:
        return Parsed(False, error=f"invalid fields: {exc.errors()[0]['msg']}")
    cites_in = data.get("citations") if isinstance(data.get("citations"), dict) else {}
    cites = {k.lower(): str(v) for k, v in cites_in.items() if isinstance(k, str) and k.lower() in STYLES and v}
    return Parsed(True, record, cites)

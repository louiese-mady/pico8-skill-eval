"""Assign UIDs to tasks whose task_uid is still 'TBD'.

Existing real UIDs are preserved (idempotent). Run this once after
saving a task-generation output before any downstream step.

Usage: python scripts/assign_task_uids.py tasks/bootyful_demake.json
"""
import json
import re
import secrets
import sys
from pathlib import Path

UID_RE = re.compile(r"^[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}$")


def make_uid() -> str:
    h = secrets.token_hex(8)
    return f"{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"


path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tasks/bootyful_demake.json")

if not path.exists():
    print(f"file not found: {path}")
    sys.exit(1)

data = json.load(open(path))
assigned = 0
preserved = 0

for task in data["tasks"]:
    current = task.get("task_uid", "TBD")
    if current == "TBD":
        task["task_uid"] = make_uid()
        assigned += 1
    elif UID_RE.match(current):
        preserved += 1
    else:
        print(f"WARN: malformed task_uid {current!r} — leaving alone")

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print(f"file:      {path}")
print(f"assigned:  {assigned} new UIDs")
print(f"preserved: {preserved} existing UIDs")
print(f"total:     {len(data['tasks'])} tasks")
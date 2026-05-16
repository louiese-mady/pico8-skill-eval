"""Quick sanity check on a tasks/<cart>.json file.

Usage: python scripts/check_tasks.py tasks/bootyful_demake.json
"""
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tasks/bootyful_demake.json")

if not path.exists():
    print(f"file not found: {path}")
    sys.exit(1)

data = json.load(open(path))
tasks = data["tasks"]

print(f"file:           {path}")
print(f"cart_uid:       {data['cart_uid']}")
print(f"tasks:          {len(tasks)}")
print(f"all TBD uids:   {all(t['task_uid'] == 'TBD' for t in tasks)}")
print(f"all assigned:   {all(t['task_uid'] != 'TBD' for t in tasks)}")

# Task-type distribution
types = {}
for t in tasks:
    types[t["task_type"]] = types.get(t["task_type"], 0) + 1
print(f"types:          {types}")

# k-level distribution
ks = {}
for t in tasks:
    ks[t["k_level"]] = ks.get(t["k_level"], 0) + 1
print(f"k-levels:       {ks}")

# Skill coverage
unique_skills = set()
for t in tasks:
    for s in t["skill_uids"]:
        unique_skills.add(s)
print(f"unique skills:  {len(unique_skills)} tagged across all tasks")
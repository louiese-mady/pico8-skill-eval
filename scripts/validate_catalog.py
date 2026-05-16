"""Validate that every skill_uid referenced in a task file exists in
the raw skill catalog. Flags hallucinated UIDs.

Usage: python scripts/validate_catalog.py tasks/bootyful_demake.json
"""
import json
import sys
from pathlib import Path

CATALOG = Path("extraction/raw/skills_raw.jsonl")

task_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tasks/bootyful_demake.json")

if not CATALOG.exists():
    print(f"catalog not found: {CATALOG}")
    sys.exit(1)
if not task_path.exists():
    print(f"task file not found: {task_path}")
    sys.exit(1)

# Load catalog
catalog_uids = {}
with open(CATALOG) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        catalog_uids[rec["uid"]] = rec["name"]

# Load tasks
data = json.load(open(task_path))
tasks = data["tasks"]

# Find every referenced UID and its source task
references = {}  # uid -> list of task indices
for i, t in enumerate(tasks):
    for u in t["skill_uids"]:
        references.setdefault(u, []).append(i)

# Audit
hallucinated = []
ok_count = 0
for uid, task_indices in references.items():
    if uid in catalog_uids:
        ok_count += 1
    else:
        hallucinated.append((uid, task_indices))

print(f"catalog size:        {len(catalog_uids)} skills")
print(f"unique skill refs:   {len(references)} in {len(tasks)} tasks")
print(f"verified in catalog: {ok_count}")
print(f"hallucinated:        {len(hallucinated)}")

if hallucinated:
    print()
    print("HALLUCINATED UIDs (not in catalog):")
    for uid, task_indices in hallucinated:
        print(f"  {uid}  — referenced by tasks {task_indices}")
    sys.exit(2)
else:
    print()
    print("all referenced skill UIDs are valid")

# Coverage stats
unused = set(catalog_uids) - set(references)
print()
print(f"coverage: {len(references)}/{len(catalog_uids)} skills tagged "
      f"({100*len(references)//len(catalog_uids)}%)")
print(f"untagged skills: {len(unused)}")
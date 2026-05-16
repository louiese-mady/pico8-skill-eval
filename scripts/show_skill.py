"""Look up a skill by UID prefix or name substring.

Usage:
    python scripts/show_skill.py 4e5d         # by UID prefix
    python scripts/show_skill.py world_offset # by name substring
"""
import json
import sys
from pathlib import Path

CATALOG = Path("extraction/raw/skills_raw.jsonl")

if len(sys.argv) < 2:
    print("usage: python scripts/show_skill.py <uid-prefix-or-name-substring>")
    sys.exit(1)

query = sys.argv[1].lower()

matches = []
with open(CATALOG) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if query in rec["uid"].lower() or query in rec["name"].lower():
            matches.append(rec)

if not matches:
    print(f"no skills match: {query}")
    sys.exit(1)

for rec in matches:
    print(f"uid:        {rec['uid']}")
    print(f"name:       {rec['name']}")
    print(f"k_level:    {rec['k_level']}")
    print(f"chunk:      {rec['source_chunk']}")
    print(f"definition: {rec['definition']}")
    print(f"evidence:   {rec['evidence']}")
    if "notes" in rec:
        print(f"notes:      {rec['notes']}")
    print()
print(f"({len(matches)} match{'es' if len(matches) != 1 else ''})")
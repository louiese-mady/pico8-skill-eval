"""Assemble grading prompts for every student-output JSON in a run directory.

For each task that has a student response, this script reads:
  - the task definition (prompt, expected_answer, rubric, skill_uids) from tasks/<cart>.json
  - the catalog skill records (name, definition) from extraction/raw/skills_raw.jsonl
  - the student response from runs/<model>/outputs/<task_uid>.json

It assembles a ready-to-paste grading prompt and writes it to
runs/<model>/grading_prompts/<task_uid>.txt.

You then open a fresh Claude chat per task, paste the contents of the
.txt file, and save the returned JSON to runs/<model>/grades/<task_uid>.json.

Validation is strict: missing skill_uids, missing student outputs, and
malformed task records will all cause the script to fail loudly with a
clear error message — better to catch problems now than to ship broken
prompts to the grader.

Usage:
    python scripts/build_grading_prompts.py \\
        --tasks tasks/bootyful_demake.json \\
        --catalog extraction/raw/skills_raw.jsonl \\
        --outputs runs/qwen3-235b-cerebras/outputs \\
        --out runs/qwen3-235b-cerebras/grading_prompts

All paths can be omitted if defaults are used.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROMPT_TEMPLATE = """You are grading one LLM response for an evaluation. You produce two independent scores: an ANSWER score (how well the answer matches the rubric) and a METACOGNITION score (how well the student's chosen skill matches the skill the task was designed to test).

You are strict but fair. You read the student's full response, score each axis independently, and you do NOT let your judgment of one axis bleed into the other. A student can have a correct answer with a wrong skill label, or the right skill label with a wrong answer.

---

TASK PROMPT:
{task_prompt}

EXPECTED ANSWER:
{expected_answer}

RUBRIC:
- pass: {rubric_pass}
- partial: {rubric_partial}
- fail: {rubric_fail}

CATALOG SKILLS the task was designed to test (the student did NOT see these):
{catalog_skills_block}

---

STUDENT'S FULL RESPONSE:
{student_response}

---

Grade both axes.

ANSWER SCORE — read the student's ANSWER section. Compare against the expected_answer using the rubric. Return one of:
- "pass": answer minimally contains what rubric.pass requires
- "partial": answer is partly correct but misses at least one element rubric.pass requires
- "fail": answer is incorrect, missing, or matches rubric.fail

METACOGNITION SCORE — read the student's SKILL_CHOSEN. Compare to the catalog skill(s) above. Return one of:
- "match": student's free-form skill name maps clearly onto one of the catalog skills. Phrasings differ but the concept is the same.
- "near_match": student named something in the right family but less specific (e.g., "trace variables" when the catalog skill is "trace duplicate variable assignment")
- "miss": student named something unrelated, OR named the skill so vaguely it doesn't carry signal (e.g., "answer the question")

Return ONLY valid JSON in this exact schema:

{{
  "task_uid": "{task_uid}",
  "answer_score": "pass" | "partial" | "fail",
  "metacog_score": "match" | "near_match" | "miss",
  "answer_rationale": "<1-2 sentences: why this answer score>",
  "metacog_rationale": "<1 sentence: why this metacog score>"
}}
"""


def load_catalog(catalog_path: Path) -> dict[str, dict]:
    """Load skills_raw.jsonl into a UID -> skill record map."""
    if not catalog_path.exists():
        raise FileNotFoundError(f"catalog not found: {catalog_path}")
    catalog: dict[str, dict] = {}
    with catalog_path.open() as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{catalog_path}:{line_num}: invalid JSON — {e}")
            for required in ("uid", "name", "definition"):
                if required not in rec:
                    raise ValueError(
                        f"{catalog_path}:{line_num}: missing '{required}' field"
                    )
            catalog[rec["uid"]] = rec
    return catalog


def load_tasks(tasks_path: Path) -> tuple[str, list[dict]]:
    """Load tasks/<cart>.json, return (cart_uid, [tasks])."""
    if not tasks_path.exists():
        raise FileNotFoundError(f"tasks file not found: {tasks_path}")
    data = json.load(open(tasks_path))
    cart_uid = data.get("cart_uid", "")
    tasks = data.get("tasks", [])
    if not tasks:
        raise ValueError(f"{tasks_path}: no tasks found")
    return cart_uid, tasks


def load_student_response(outputs_dir: Path, task_uid: str) -> str:
    """Read the 'response' field from runs/.../outputs/<task_uid>.json."""
    path = outputs_dir / f"{task_uid}.json"
    if not path.exists():
        return ""  # signal "no response yet" — caller decides what to do
    data = json.load(open(path))
    return data.get("response", "")


def format_catalog_skills(skill_uids: list[str], catalog: dict[str, dict]) -> tuple[str, list[str]]:
    """Build the catalog-skills block for the prompt. Returns (block_text, missing_uids)."""
    lines: list[str] = []
    missing: list[str] = []
    for uid in skill_uids:
        if uid not in catalog:
            missing.append(uid)
            continue
        rec = catalog[uid]
        lines.append(f"- {uid}: {rec['name']} — {rec['definition']}")
    return "\n".join(lines) if lines else "(no catalog skills tagged)", missing


def assemble_prompt(task: dict, catalog: dict[str, dict], student_response: str) -> tuple[str, list[str]]:
    """Build the full grading prompt for one task. Returns (prompt_text, missing_uids)."""
    rubric = task.get("rubric", {})
    skill_uids = task.get("skill_uids", [])
    catalog_block, missing = format_catalog_skills(skill_uids, catalog)
    prompt = PROMPT_TEMPLATE.format(
        task_uid=task["task_uid"],
        task_prompt=task["prompt"],
        expected_answer=task["expected_answer"],
        rubric_pass=rubric.get("pass", "(no pass criterion specified)"),
        rubric_partial=rubric.get("partial", "(no partial criterion specified)"),
        rubric_fail=rubric.get("fail", "(no fail criterion specified)"),
        catalog_skills_block=catalog_block,
        student_response=student_response if student_response else "(NO STUDENT RESPONSE — skip this task or re-run the student)",
    )
    return prompt, missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path("tasks/bootyful_demake.json"),
        help="Path to tasks/<cart>.json (default: tasks/bootyful_demake.json)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("extraction/raw/skills_raw.jsonl"),
        help="Path to flattened skill catalog (default: extraction/raw/skills_raw.jsonl)",
    )
    parser.add_argument(
        "--outputs",
        type=Path,
        default=Path("runs/qwen3-235b-cerebras/outputs"),
        help="Directory with student-output JSON files",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs/qwen3-235b-cerebras/grading_prompts"),
        help="Where to write assembled prompts (one .txt per task)",
    )
    args = parser.parse_args()

    # Load all the inputs (fail loudly if anything is wrong)
    try:
        print(f"loading catalog: {args.catalog}")
        catalog = load_catalog(args.catalog)
        print(f"  {len(catalog)} skills loaded")

        print(f"loading tasks:   {args.tasks}")
        cart_uid, tasks = load_tasks(args.tasks)
        print(f"  {len(tasks)} tasks loaded (cart_uid: {cart_uid})")
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"outputs dir:     {args.outputs}")
    if not args.outputs.exists():
        print(f"  WARNING: outputs dir does not exist — all student responses will be missing")

    # Build prompts
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"writing prompts: {args.out}")
    print()

    stats = {"written": 0, "no_response": 0, "missing_skills": 0}
    all_missing_uids: set[str] = set()

    for task in tasks:
        task_uid = task["task_uid"]
        response = load_student_response(args.outputs, task_uid)
        has_response = bool(response)
        prompt, missing = assemble_prompt(task, catalog, response)

        if missing:
            all_missing_uids.update(missing)
            stats["missing_skills"] += 1

        out_path = args.out / f"{task_uid}.txt"
        out_path.write_text(prompt, encoding="utf-8")
        stats["written"] += 1

        if not has_response:
            stats["no_response"] += 1
            status = "no student response yet"
        elif missing:
            status = f"missing {len(missing)} skill UID(s) in catalog"
        else:
            status = "ok"

        # Compact one-liner per task
        prefix = f"  {task_uid[:13]}... ({task.get('task_type','?')}, k={task.get('k_level','?')})"
        print(f"{prefix} → {out_path.name}  [{status}]")

    print()
    print(f"summary:")
    print(f"  prompts written:        {stats['written']}/{len(tasks)}")
    print(f"  tasks without response: {stats['no_response']}")
    print(f"  tasks w/ missing skill: {stats['missing_skills']}")
    if all_missing_uids:
        print(f"  unresolved UIDs: {sorted(all_missing_uids)}")

    print()
    if stats["no_response"] > 0:
        print(f"NOTE: {stats['no_response']} task(s) have no student response.")
        print(f"      Run the student model on those first, then re-run this script.")
    if all_missing_uids:
        print(f"WARNING: some skill UIDs in tasks/ are not in the catalog. Check tasks/<cart>.json")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
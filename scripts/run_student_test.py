"""Test the metacognitive runner on just ONE task.

Runs the first task in tasks/<cart>.json against Qwen3-8B via Ollama,
saves output to runs/_test/, and prints the response directly so you
can eyeball whether the 4-part structure is being followed before
committing to the full ~60-90 minute batch.

Usage:
    python scripts/run_student_test.py tasks/bootyful_demake.json

Requires Ollama running with qwen3-8b-eval registered.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_TAG = "qwen3-8b-eval"


def extract_lua_section(cart_path: Path) -> str:
    """Extract just the __lua__ section from a .p8 file."""
    content = cart_path.read_text(encoding="utf-8", errors="replace")
    if "__lua__" not in content:
        raise ValueError(f"{cart_path}: no __lua__ section found")
    after = content.split("__lua__", 1)[1]
    for marker in ("__gfx__", "__gff__", "__map__", "__sfx__", "__music__", "__label__"):
        if marker in after:
            after = after.split(marker, 1)[0]
    return after.strip()


def build_prompt(task: dict, cart_code: str) -> str:
    return f"""You are reading a PICO-8 Lua cart and answering a question about it.

CART CODE:
```lua
{cart_code}
```

QUESTION:
{task['prompt']}

Answer in this exact format:

SKILL_CANDIDATES:
- <name a cognitive operation you could apply to this question, in your own words>
- <name another candidate>
- <name another candidate, if applicable>

SKILL_CHOSEN: <pick exactly one from your candidates above>

RATIONALE: <one sentence: why did you pick that skill for this question?>

ANSWER:
<your actual answer to the question, reasoning through it clearly>

Important:
- Name skills as short verb-phrases (e.g., "trace variable across functions",
  "identify bug in control flow", "decode tile flag arithmetic").
- Do NOT skip the SKILL sections. They are part of your response.
- The RATIONALE should be specific to this question, not generic.
"""


def call_ollama(prompt: str, timeout: int = 900) -> dict:
    payload = {
        "model": MODEL_TAG,
        "prompt": prompt,
        "stream": False,
        "think": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Test runner on a single task.")
    parser.add_argument("tasks_file", type=Path, help="Path to tasks/<cart>.json")
    parser.add_argument(
        "--cart",
        type=Path,
        help="Path to the cart .p8 file. Inferred from tasks file stem if omitted.",
    )
    parser.add_argument(
        "--task-index",
        type=int,
        default=0,
        help="Which task to run (0-indexed). Default: 0 (the first task).",
    )
    args = parser.parse_args()

    if not args.tasks_file.exists():
        print(f"error: tasks file not found: {args.tasks_file}")
        return 1

    data = json.load(open(args.tasks_file))
    tasks = data["tasks"]

    if args.task_index >= len(tasks):
        print(f"error: task-index {args.task_index} out of range (have {len(tasks)} tasks)")
        return 1

    task = tasks[args.task_index]

    if args.cart is None:
        stem = args.tasks_file.stem
        args.cart = Path("corpus/carts") / stem / f"{stem}.p8"
    if not args.cart.exists():
        print(f"error: cart not found: {args.cart}")
        return 1

    cart_code = extract_lua_section(args.cart)

    print(f"=" * 60)
    print(f"TEST RUN — single task")
    print(f"=" * 60)
    print(f"cart:           {args.cart}")
    print(f"cart lua size:  {len(cart_code.splitlines())} lines, {len(cart_code)} chars")
    print(f"task index:     {args.task_index}")
    print(f"task_uid:       {task['task_uid']}")
    print(f"task_type:      {task['task_type']}")
    print(f"k_level:        {task['k_level']}")
    print(f"model:          {MODEL_TAG}")
    print(f"=" * 60)
    print(f"TASK PROMPT:")
    print(task["prompt"])
    print(f"=" * 60)
    print(f"calling Ollama (this may take 4-8 minutes)...")
    print()

    prompt = build_prompt(task, cart_code)
    start = time.time()
    try:
        response = call_ollama(prompt)
    except Exception as e:
        print(f"FAILED: {e}")
        return 2
    elapsed = time.time() - start

    response_text = response.get("response", "")
    thinking_text = response.get("thinking", "")

    # Save to test directory (separate from real runs)
    output_dir = Path("runs/_test/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{task['task_uid']}.json"
    record = {
        "task_uid": task["task_uid"],
        "model": MODEL_TAG,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "prompt_length_chars": len(prompt),
        "response": response_text,
        "thinking": thinking_text,
        "ollama_meta": {
            k: response.get(k)
            for k in (
                "total_duration",
                "load_duration",
                "prompt_eval_count",
                "prompt_eval_duration",
                "eval_count",
                "eval_duration",
            )
        },
    }
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(f"DONE in {elapsed/60:.1f} min ({elapsed:.0f}s)")
    print(f"saved to: {out_path}")
    print()
    print(f"=" * 60)
    print(f"THINKING TRACE ({len(thinking_text)} chars):")
    print(f"=" * 60)
    if thinking_text:
        # Show first 1000 chars to avoid flooding the terminal
        if len(thinking_text) > 1000:
            print(thinking_text[:1000])
            print(f"\n... [{len(thinking_text)-1000} more chars, see file]")
        else:
            print(thinking_text)
    else:
        print("(empty — thinking trace not captured separately)")

    print()
    print(f"=" * 60)
    print(f"FINAL RESPONSE ({len(response_text)} chars):")
    print(f"=" * 60)
    print(response_text)
    print(f"=" * 60)

    # Quick structural check
    has_candidates = "SKILL_CANDIDATES" in response_text
    has_chosen = "SKILL_CHOSEN" in response_text
    has_rationale = "RATIONALE" in response_text
    has_answer = "ANSWER" in response_text
    structure_ok = all([has_candidates, has_chosen, has_rationale, has_answer])

    print()
    print(f"structural check:")
    print(f"  SKILL_CANDIDATES present: {has_candidates}")
    print(f"  SKILL_CHOSEN present:     {has_chosen}")
    print(f"  RATIONALE present:        {has_rationale}")
    print(f"  ANSWER present:           {has_answer}")
    print(f"  4-part structure intact:  {structure_ok}")

    if not structure_ok:
        print()
        print("WARNING: structure incomplete — prompt may need tuning before full run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""Run Qwen3-235B-A22B via Cerebras API on every task in tasks/<cart>.json.

Cerebras free tier (personal account): 5 RPM, 30K TPM, 1M tokens/day on
qwen-3-235b-a22b-instruct-2507. The 5 RPM cap is the binding constraint;
we throttle 15s between calls to stay safely under it.

For each task, builds the metacognitive 4-part student prompt and calls
Cerebras's OpenAI-compatible /chat/completions endpoint. Saves output
to runs/qwen3-235b-cerebras/outputs/<task_uid>.json.

Auto-resumes: skips any task whose output file already exists.

Requires environment variable CEREBRAS_API_KEY.

Usage:
    python scripts/run_student_cerebras.py tasks/bootyful_demake.json
    python scripts/run_student_cerebras.py tasks/bootyful_demake.json --limit 1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
MODEL_TAG = "qwen-3-235b-a22b-instruct-2507"
MODEL_LABEL = "qwen3-235b-cerebras"

# Rate limit: 5 RPM = 1 request per 12s. Sleep 15s for safety margin.
SLEEP_BETWEEN_CALLS_S = 35


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
    """Metacognitive 4-part prompt. Hides catalog from student."""
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


def call_cerebras(prompt: str, api_key: str, timeout: int = 120) -> dict:
    """Call Cerebras's chat completions endpoint."""
    payload = {
        "model": MODEL_TAG,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 8000,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        CEREBRAS_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (pico8-skill-eval/0.1)",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_one_task(task: dict, cart_code: str, output_dir: Path, api_key: str) -> tuple[str, float]:
    """Run one task. Returns (status, elapsed_seconds)."""
    task_uid = task["task_uid"]
    out_path = output_dir / f"{task_uid}.json"

    if out_path.exists():
        return "skipped", 0.0

    prompt = build_prompt(task, cart_code)
    start = time.time()
    try:
        response = call_cerebras(prompt, api_key)
    except Exception as e:
        return f"error: {e}", time.time() - start
    elapsed = time.time() - start

    # OpenAI-compatible response shape
    choice = response.get("choices", [{}])[0]
    message = choice.get("message", {})
    response_text = message.get("content", "")
    reasoning_text = message.get("reasoning", "")  # captured if model returns thinking

    record = {
        "task_uid": task_uid,
        "model": MODEL_TAG,
        "model_label": MODEL_LABEL,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "prompt_length_chars": len(prompt),
        "response": response_text,
        "thinking": reasoning_text,
        "finish_reason": choice.get("finish_reason"),
        "api_meta": {
            "usage": response.get("usage"),
            "id": response.get("id"),
            "model": response.get("model"),
        },
    }
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return "ok", elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tasks_file", type=Path, help="Path to tasks/<cart>.json")
    parser.add_argument("--cart", type=Path, help="Path to .p8 cart (inferred if omitted)")
    parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    parser.add_argument("--limit", type=int, default=None, help="Run only first N tasks")
    args = parser.parse_args()

    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        print("error: CEREBRAS_API_KEY environment variable not set.")
        print("set it in PowerShell with: $env:CEREBRAS_API_KEY = 'csk-...'")
        return 1

    if not args.tasks_file.exists():
        print(f"error: tasks file not found: {args.tasks_file}")
        return 1

    data = json.load(open(args.tasks_file))
    tasks = data["tasks"]

    if args.cart is None:
        stem = args.tasks_file.stem
        args.cart = Path("corpus/carts") / stem / f"{stem}.p8"
    if not args.cart.exists():
        print(f"error: cart not found: {args.cart}")
        return 1

    cart_code = extract_lua_section(args.cart)

    output_dir = args.runs_root / MODEL_LABEL / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"cart:        {args.cart}")
    print(f"cart size:   {len(cart_code.splitlines())} lines, {len(cart_code)} chars")
    print(f"model:       {MODEL_TAG} (via Cerebras)")
    print(f"output dir:  {output_dir}")
    n_to_run = args.limit if args.limit else len(tasks)
    print(f"tasks:       {len(tasks)}{' (limit ' + str(args.limit) + ')' if args.limit else ''}")
    print(f"rate limit:  5 RPM, sleeping {SLEEP_BETWEEN_CALLS_S}s between calls")
    est_min = (n_to_run * SLEEP_BETWEEN_CALLS_S) / 60
    print(f"estimated:   ~{est_min:.1f} min for {n_to_run} tasks")
    print()

    total_start = time.time()
    statuses = {"ok": 0, "skipped": 0, "error": 0}

    for i, task in enumerate(tasks, 1):
        if args.limit and i > args.limit:
            break
        prefix = f"[{i}/{len(tasks)}] {task['task_uid'][:13]}... ({task['task_type']}, k={task['k_level']})"
        print(prefix, end=" ", flush=True)
        status, elapsed = run_one_task(task, cart_code, output_dir, api_key)
        if status == "ok":
            statuses["ok"] += 1
            print(f"done in {elapsed:.1f}s")
        elif status == "skipped":
            statuses["skipped"] += 1
            print("skipped (output exists)")
        else:
            statuses["error"] += 1
            print(f"FAILED ({status})")
        # Throttle for rate limit, but skip sleep on the final iteration
        if i < len(tasks) and not (args.limit and i >= args.limit):
            time.sleep(SLEEP_BETWEEN_CALLS_S)

    total_elapsed = time.time() - total_start
    print()
    print(f"total wall time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"results: {statuses['ok']} ok, {statuses['skipped']} skipped, {statuses['error']} errors")
    return 0 if statuses["error"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
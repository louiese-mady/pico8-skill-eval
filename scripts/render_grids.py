"""Render evaluation grids from grades, tasks, and skill catalog.

Produces three PNG files in results/grids/:

  grid_a_task_score.png    — per-task heatmap of answer + metacog scores,
                             sorted left-to-right by k-level (easy -> hard).
  grid_b_answer_metacog.png — 3x3 joint distribution of answer x metacog
                             with counts annotated in each cell.
  grid_c_skill_task.png    — skill-by-task tagging matrix, with cells
                             colored by the model's answer outcome.

Usage:
    python scripts/render_grids.py \\
        --tasks tasks/bootyful_demake.json \\
        --catalog extraction/raw/skills_raw.jsonl \\
        --grades runs/qwen3-235b-cerebras/grades \\
        --out results/grids \\
        --model-label "Qwen3-235B-A22B-Instruct (Cerebras)"

All paths default to the standard repo layout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no display required
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# Color palette: refined, high-contrast, print-friendly
COLOR_PASS = "#2d8659"        # deep green
COLOR_PARTIAL = "#d4a418"     # amber
COLOR_FAIL = "#b53737"        # deep red
COLOR_NA = "#ececec"          # light grey for "not tagged"
COLOR_TAGGED = "#1f3a5f"      # navy for binary tagging matrix
COLOR_MATCH = "#2d8659"       # same as pass
COLOR_NEAR = "#d4a418"        # same as partial
COLOR_MISS = "#b53737"        # same as fail

# Plot defaults for clean, refined look
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#444444",
    "axes.linewidth": 0.6,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})


def load_tasks(path: Path) -> list[dict]:
    data = json.load(open(path))
    return data["tasks"]


def load_catalog(path: Path) -> dict[str, dict]:
    catalog = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            catalog[rec["uid"]] = rec
    return catalog


def load_grades(dir_path: Path) -> dict[str, dict]:
    grades = {}
    for jf in dir_path.glob("*.json"):
        rec = json.loads(jf.read_text())
        grades[rec["task_uid"]] = rec
    return grades


def short_id(uid: str) -> str:
    """Shorten a UID for display: 'a1b2-c3d4-e5f6-7890' -> 'a1b2'."""
    return uid.split("-")[0]


def short_skill(name: str) -> str:
    """Truncate a 4-word skill name to roughly 28 chars for axis labels."""
    if len(name) <= 28:
        return name
    return name[:26] + "…"


# ---------------------------------------------------------------------------
# Grid A: Task × Score heatmap
# ---------------------------------------------------------------------------

def render_grid_a(tasks: list[dict], grades: dict[str, dict], model_label: str, out_path: Path) -> None:
    """Two-row heatmap: answer_score and metacog_score per task, sorted by k_level."""
    # Sort tasks: by k_level ascending, then by task_type for grouping
    type_order = {"localization": 0, "tracing": 1, "inference": 2}
    sorted_tasks = sorted(
        tasks,
        key=lambda t: (t["k_level"], type_order.get(t["task_type"], 99), t["task_uid"]),
    )

    n = len(sorted_tasks)
    answer_colors = []
    metacog_colors = []
    labels = []
    answer_texts = []
    metacog_texts = []

    for t in sorted_tasks:
        g = grades.get(t["task_uid"])
        labels.append(f"{short_id(t['task_uid'])}\nk={t['k_level']} • {t['task_type'][:3]}")
        if g is None:
            answer_colors.append(COLOR_NA)
            metacog_colors.append(COLOR_NA)
            answer_texts.append("?")
            metacog_texts.append("?")
            continue
        a = g.get("answer_score", "")
        m = g.get("metacog_score", "")
        answer_colors.append({"pass": COLOR_PASS, "partial": COLOR_PARTIAL, "fail": COLOR_FAIL}.get(a, COLOR_NA))
        metacog_colors.append({"match": COLOR_MATCH, "near_match": COLOR_NEAR, "miss": COLOR_MISS}.get(m, COLOR_NA))
        answer_texts.append({"pass": "P", "partial": "p", "fail": "F"}.get(a, "?"))
        metacog_texts.append({"match": "M", "near_match": "n", "miss": "X"}.get(m, "?"))

    fig, ax = plt.subplots(figsize=(max(8, n * 0.95), 3.6))

    cell_w = 1.0
    cell_h = 1.0
    for i, c in enumerate(answer_colors):
        ax.add_patch(plt.Rectangle((i, 1), cell_w, cell_h, facecolor=c, edgecolor="white", linewidth=2))
        ax.text(i + 0.5, 1.5, answer_texts[i], ha="center", va="center",
                fontsize=14, fontweight="bold", color="white")
    for i, c in enumerate(metacog_colors):
        ax.add_patch(plt.Rectangle((i, 0), cell_w, cell_h, facecolor=c, edgecolor="white", linewidth=2))
        ax.text(i + 0.5, 0.5, metacog_texts[i], ha="center", va="center",
                fontsize=14, fontweight="bold", color="white")

    ax.set_xlim(-0.05, n + 0.05)
    ax.set_ylim(-0.7, 2.1)
    ax.set_xticks([i + 0.5 for i in range(n)])
    ax.set_xticklabels(labels, fontsize=7.5, rotation=0)
    ax.set_yticks([1.5, 0.5])
    ax.set_yticklabels(["answer", "metacog"], fontsize=10)
    ax.tick_params(axis="x", length=0)
    ax.tick_params(axis="y", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        f"Grid A — per-task scores, sorted by complexity (k=1 → k=3)\n"
        f"model: {model_label}",
        fontsize=11, pad=14, loc="left",
    )

    # Legend
    legend_handles = [
        mpatches.Patch(color=COLOR_PASS, label="pass / match"),
        mpatches.Patch(color=COLOR_PARTIAL, label="partial / near-match"),
        mpatches.Patch(color=COLOR_FAIL, label="fail / miss"),
    ]
    ax.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, -0.28),
              ncol=3, frameon=False, fontsize=9)

    fig.savefig(out_path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Grid B: Answer × Metacog joint distribution
# ---------------------------------------------------------------------------

def render_grid_b(grades: dict[str, dict], model_label: str, out_path: Path) -> None:
    """3x3 heatmap of joint (answer_score, metacog_score) counts."""
    rows = ["pass", "partial", "fail"]
    cols = ["match", "near_match", "miss"]
    M = np.zeros((3, 3), dtype=int)
    for g in grades.values():
        a = g.get("answer_score")
        m = g.get("metacog_score")
        if a in rows and m in cols:
            M[rows.index(a), cols.index(m)] += 1

    fig, ax = plt.subplots(figsize=(6.5, 4.5))

    # Custom shading: brightness scales with count; hue distinguishes columns
    # Simple approach: just use a single colormap with annotations
    max_val = max(M.max(), 1)
    cmap = plt.cm.Blues
    im = ax.imshow(M, cmap=cmap, aspect="equal", vmin=0, vmax=max_val * 1.2)

    for i in range(3):
        for j in range(3):
            val = M[i, j]
            text_color = "white" if val > max_val * 0.55 else "#1a1a1a"
            ax.text(j, i, str(val), ha="center", va="center",
                    fontsize=22, fontweight="bold", color=text_color)

    ax.set_xticks(range(3))
    ax.set_yticks(range(3))
    ax.set_xticklabels(["match", "near-match", "miss"], fontsize=10)
    ax.set_yticklabels(["pass", "partial", "fail"], fontsize=10)
    ax.set_xlabel("metacognition score (skill naming)", fontsize=10, labelpad=8)
    ax.set_ylabel("answer score (rubric)", fontsize=10, labelpad=8)
    ax.set_title(
        f"Grid B — does the model know what it is doing?\n"
        f"model: {model_label}  •  n={int(M.sum())} tasks",
        fontsize=11, pad=14, loc="left",
    )

    # Light grid lines between cells
    ax.set_xticks(np.arange(-0.5, 3, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 3, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(which="major", length=0)

    fig.savefig(out_path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Grid C: Skill × Task tagging matrix
# ---------------------------------------------------------------------------

def render_grid_c(
    tasks: list[dict],
    catalog: dict[str, dict],
    grades: dict[str, dict],
    model_label: str,
    out_path: Path,
) -> None:
    """Heatmap: rows = catalog skills tagged on any task, cols = tasks.

    Cell color encodes the model's answer outcome on that task (only for
    cells where the skill was tagged). Untagged cells are light grey.
    """
    # Sort tasks left->right by k_level (same as Grid A)
    type_order = {"localization": 0, "tracing": 1, "inference": 2}
    sorted_tasks = sorted(
        tasks,
        key=lambda t: (t["k_level"], type_order.get(t["task_type"], 99), t["task_uid"]),
    )
    task_uids = [t["task_uid"] for t in sorted_tasks]

    # Find skills that appear on at least one task
    used_skill_uids: list[str] = []
    seen: set[str] = set()
    for t in sorted_tasks:
        for s in t["skill_uids"]:
            if s not in seen:
                seen.add(s)
                used_skill_uids.append(s)

    # Try to sort skills by their own k_level (ascending) for readability
    used_skill_uids.sort(
        key=lambda u: (
            catalog.get(u, {}).get("k_level", 99),
            catalog.get(u, {}).get("name", u),
        )
    )

    nrows = len(used_skill_uids)
    ncols = len(task_uids)

    fig_w = max(8.5, 0.95 * ncols + 4.5)
    fig_h = max(5, 0.42 * nrows + 2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    score_color = {
        "pass": COLOR_PASS,
        "partial": COLOR_PARTIAL,
        "fail": COLOR_FAIL,
    }

    for j, t in enumerate(sorted_tasks):
        task_skills = set(t["skill_uids"])
        g = grades.get(t["task_uid"])
        ans = g.get("answer_score") if g else None
        for i, sk in enumerate(used_skill_uids):
            y = nrows - 1 - i  # flip so first skill is top
            if sk in task_skills:
                color = score_color.get(ans, COLOR_NA)
                ax.add_patch(plt.Rectangle((j, y), 1, 1, facecolor=color, edgecolor="white", linewidth=1.5))
            else:
                ax.add_patch(plt.Rectangle((j, y), 1, 1, facecolor=COLOR_NA, edgecolor="white", linewidth=1.5))

    ax.set_xlim(-0.05, ncols + 0.05)
    ax.set_ylim(-0.05, nrows + 0.05)

    # X labels: task short id + k-level + type abbreviation
    xticks = [j + 0.5 for j in range(ncols)]
    xlabels = []
    for t in sorted_tasks:
        xlabels.append(f"{short_id(t['task_uid'])}\nk={t['k_level']} • {t['task_type'][:3]}")
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels, fontsize=7.5)
    ax.tick_params(axis="x", length=0)

    # Y labels: skill names (use names from catalog if present, fallback to UID)
    yticks = [nrows - 1 - i + 0.5 for i in range(nrows)]
    ylabels = []
    for sk in used_skill_uids:
        rec = catalog.get(sk, {})
        name = rec.get("name", sk)
        k = rec.get("k_level", "?")
        ylabels.append(f"{short_skill(name)}  (k{k})")
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=8.5)
    ax.tick_params(axis="y", length=0)

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        f"Grid C — skill × task tagging matrix (cell color = model outcome)\n"
        f"model: {model_label}  •  {nrows} skills tagged across {ncols} tasks",
        fontsize=11, pad=14, loc="left",
    )

    legend_handles = [
        mpatches.Patch(color=COLOR_PASS, label="task passed"),
        mpatches.Patch(color=COLOR_PARTIAL, label="task partial"),
        mpatches.Patch(color=COLOR_FAIL, label="task failed"),
        mpatches.Patch(color=COLOR_NA, label="skill not tagged on this task"),
    ]
    ax.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, -0.14),
              ncol=4, frameon=False, fontsize=9)

    fig.savefig(out_path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Summary stats printed to console
# ---------------------------------------------------------------------------

def print_summary(tasks: list[dict], grades: dict[str, dict]) -> None:
    n = len(tasks)
    counts_a = {"pass": 0, "partial": 0, "fail": 0}
    counts_m = {"match": 0, "near_match": 0, "miss": 0}
    by_k = {}
    for t in tasks:
        g = grades.get(t["task_uid"])
        if not g:
            continue
        a = g.get("answer_score")
        m = g.get("metacog_score")
        if a in counts_a:
            counts_a[a] += 1
        if m in counts_m:
            counts_m[m] += 1
        k = t["k_level"]
        by_k.setdefault(k, {"pass": 0, "partial": 0, "fail": 0, "n": 0})
        by_k[k]["n"] += 1
        if a in by_k[k]:
            by_k[k][a] += 1

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"tasks graded: {sum(1 for t in tasks if t['task_uid'] in grades)}/{n}")
    print()
    print("Answer-score distribution:")
    for k in ("pass", "partial", "fail"):
        bar = "█" * counts_a[k]
        print(f"  {k:8s}: {counts_a[k]:>2d}/{n}  {bar}")
    print()
    print("Metacog-score distribution:")
    for k in ("match", "near_match", "miss"):
        bar = "█" * counts_m[k]
        print(f"  {k:11s}: {counts_m[k]:>2d}/{n}  {bar}")
    print()
    print("By k-level (compositionality):")
    for k in sorted(by_k):
        r = by_k[k]
        print(f"  k={k}: pass={r['pass']}/{r['n']}  partial={r['partial']}/{r['n']}  fail={r['fail']}/{r['n']}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--tasks", type=Path, default=Path("tasks/bootyful_demake.json"))
    p.add_argument("--catalog", type=Path, default=Path("extraction/raw/skills_raw.jsonl"))
    p.add_argument("--grades", type=Path, default=Path("runs/qwen3-235b-cerebras/grades"))
    p.add_argument("--out", type=Path, default=Path("results/grids"))
    p.add_argument("--model-label", type=str, default="Qwen3-235B-A22B (Cerebras)")
    args = p.parse_args()

    for path in (args.tasks, args.catalog, args.grades):
        if not path.exists():
            print(f"error: required path not found: {path}", file=sys.stderr)
            return 1

    print(f"loading tasks:   {args.tasks}")
    tasks = load_tasks(args.tasks)
    print(f"  {len(tasks)} tasks loaded")

    print(f"loading catalog: {args.catalog}")
    catalog = load_catalog(args.catalog)
    print(f"  {len(catalog)} skills loaded")

    print(f"loading grades:  {args.grades}")
    grades = load_grades(args.grades)
    print(f"  {len(grades)} grade files loaded")
    print()

    args.out.mkdir(parents=True, exist_ok=True)

    grid_a_path = args.out / "grid_a_task_score.png"
    grid_b_path = args.out / "grid_b_answer_metacog.png"
    grid_c_path = args.out / "grid_c_skill_task.png"

    print(f"rendering Grid A → {grid_a_path}")
    render_grid_a(tasks, grades, args.model_label, grid_a_path)
    print(f"rendering Grid B → {grid_b_path}")
    render_grid_b(grades, args.model_label, grid_b_path)
    print(f"rendering Grid C → {grid_c_path}")
    render_grid_c(tasks, catalog, grades, args.model_label, grid_c_path)
    print()
    print_summary(tasks, grades)
    return 0


if __name__ == "__main__":
    sys.exit(main())
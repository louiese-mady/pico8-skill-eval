# pico8-skill-eval

Skill-extracted evaluation pipeline for game source code. Adapts the methodology of
[Instruct-SkillMix](https://arxiv.org/abs/2408.14774) and
[Metacognitive Capabilities of LLMs](https://arxiv.org/abs/2405.12205) from math problems to PICO-8 game cartridges.

## What this is

A working pipeline that takes a PICO-8 game cartridge and produces:
1. A named-skill catalog (33 skills for the v0.1 test cart)
2. A set of evaluation tasks tagged against those skills
3. Graded responses from a target LLM, scored on answer correctness AND metacognitive skill-naming
4. Three diagnostic grids visualizing model performance per skill

The pipeline is model-agnostic. Any LLM accepting text input can be the target model.

## v0.1 results

One cart (*Bootyful Demake*), one target model (Qwen3-235B via Cerebras), 10 evaluation tasks.

- Answer score: 7 pass / 2 partial / 1 fail
- Metacognition score: 6 match / 4 near-match / 0 miss

Three grids in `results/grids/`. Full writeup in `docs/V0_1_RESULTS.md`. Methodology decisions in `qa/audit_log.md`.

## Repository structure
corpus/                — source PICO-8 cart, manifest, licenses
docs/                  — framework spec, QA guideline, results writeup
extraction/raw/        — extracted skill catalog (JSON / JSONL)
tasks/                 — generated evaluation tasks per cart
runs/<model>/          — student responses, grading prompts, grades
results/grids/         — rendered evaluation visualizations (PNG)
scripts/               — pipeline scripts (Python)
qa/                    — audit log, QA verdicts

## Reproducing v0.1

Requirements: Python 3.10+, matplotlib, numpy. An API key for at least one LLM provider (Cerebras free tier was used for v0.1).

```bash
# 1. Run the student model on existing tasks
$env:CEREBRAS_API_KEY = "csk-..."
python scripts/run_student_cerebras.py tasks/bootyful_demake.json

# 2. Assemble grading prompts
python scripts/build_grading_prompts.py

# 3. Grade each task in a fresh Claude chat (manual, 10 chats)
#    Save each verdict to runs/qwen3-235b-cerebras/grades/<task_uid>.json

# 4. Render the three grids
python scripts/render_grids.py
```

## License

The pipeline code is MIT (see LICENSE). The corpus cart (Bootyful Demake by nate2squared) is CC-BY-NC-SA-4.0 — see `corpus/LICENSES/NOTICE.md` for attribution.
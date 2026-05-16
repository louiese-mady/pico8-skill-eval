# Skill-Based LLM Evaluation Framework

**Working title:** PICO-8 Skill Extraction & Metacognitive Evaluation
**Status:** Design specification, v0.2
**Date:** 2026-05-14

**Changelog from v0.1:**
- §10 corrected from three grids to four (separated `task × skill` tagging view from `model × task` outcome view).
- §11 (was §11) renumbered to §12; new §11 added on Phase 1.5 catalog clustering.
- §5.2 extended with explicit guidance on multi-file projects.
- Worked example from `Enichan/Pico8Platformer` dry run referenced.

---

## 1. Purpose and Scope

This document specifies an evaluation framework that measures a local LLM's ability to understand and reason about small, self-contained programs (PICO-8 cartridges) by decomposing performance along a catalog of named *skills*. The framework follows the methodology of Arora's group at Princeton — specifically Skill-Mix (Yu, Kaur, Gupta, Brown-Cohen, Goyal, Arora, ICLR 2024) for the skill-combination evaluation structure, and Didolkar et al. (NeurIPS 2024) for LLM-driven skill extraction and clustering.

The framework produces:

1. A persistent catalog of skills, each with a stable identifier.
2. A persistent catalog of tasks, each tagged with the skills it exercises.
3. A pass/fail tensor over `(model, task, skill)` triples, visualizable as three pivoted grids.
4. A reproducible protocol so the same evaluation can be re-run on different student models and compared.

## 2. The Pipeline

```
PICO-8 cart corpus
      │
      ▼
[Strong LLM (Claude)]  ──► Skill catalog: named skills, UIDs, semantic clusters
      │
      ▼
[Strong LLM (Claude)]  ──► Task instances, each tagged with required skills
      │
      ▼
[Local LLM (Qwen3-8B)] ──► Attempts task → produces CoT + answer
      │
      ▼
[Strong LLM (Claude)]  ──► Grades pass/fail against rubric; optionally labels CoT skill usage
      │
      ▼
(model × task × skill) tensor → three pivoted grids, color-coded
```

The strong LLM plays three roles — extractor, generator, grader — but **must not be the student**. The student never sees the skill catalog at inference time; otherwise the skill name leaks the answer (Skill-Mix explicitly deducts points when the skill name appears in the output).

## 3. Terminology

| Term | Definition |
|------|-----------|
| **Corpus** | The collection of source artifacts (PICO-8 carts) from which skills and tasks are derived. |
| **Skill** | A named, atomic-ish capability the student must exercise to solve a task (e.g., "trace variable across scopes," "identify draw callback"). |
| **Skill UID** | A stable identifier: `uint64` rendered as four dash-separated lower-case hex groups, e.g. `7f3a-9b12-0044-c1e8`. |
| **Task** | A concrete prompt + expected-answer pair derived from one cart, tagged with the skills it exercises. |
| **Task UID** | Same UID scheme as skill UID. |
| **Student** | The local LLM under test (Qwen3-8B via Ollama in the first run). |
| **Teacher / Grader** | The strong LLM that extracts skills, generates tasks, and grades outputs. |
| **CoT** | Chain-of-thought; the student's intermediate reasoning, captured for grading and for second-pass skill labeling. |
| **k** | Following Skill-Mix: the number of skills a task requires simultaneously. k=1 is atomic; k≥2 is compositional. |

## 4. UID Scheme

`uint64` rendered as `xxxx-xxxx-xxxx-xxxx` lower-case hex. Generation: cryptographic random (`secrets.token_hex(8)` in Python, formatted with dashes). Collision probability is negligible at the scales we're working at (less than ~10,000 skills + tasks combined).

Namespaces are flat — there's no semantic prefix distinguishing skill UIDs from task UIDs. Type is carried in the record, not in the ID. This avoids reorganization pain later when categories shift.

Two examples:

- Skill: `7f3a-9b12-0044-c1e8` — "identify-draw-callback"
- Task: `2c81-44ef-9a03-7b15` — comprehension question about `_draw()` in cart `celeste-classic.p8`

## 5. Corpus: How Many Carts Do We Need?

### 5.1 Reference points from the literature

Skill-Mix used **101 skills and 100 topics** drawn from books and Wikipedia, with the key design choice that the *skill set was hand-curated* rather than corpus-extracted. The Skill-Mix paper notes their initial experiments involved a set of 101 skills selected from books and Wikipedia, and that they identified 17 skills with high frequency in the common crawl corpus and recommend omitting them to make the evaluation harder.

Didolkar et al. extracted skills *from* the MATH and GSM8K datasets directly, then performed semantic clustering on the LLM-proposed labels to get a coarser, interpretable taxonomy. The catalog size after clustering was in the low dozens of coarse skills covering thousands of problems.

### 5.2 Recommended corpus size for the first run

The corpus serves two purposes: a *source* for skill extraction and a *source* for task generation. These have different size requirements.

For **skill extraction**, the marginal return diminishes quickly: after roughly 15–25 carts spanning different mechanics (platformer, shooter, puzzle, top-down, demoscene), most subsequent carts add no new skills, only new instances of skills already in the catalog. This is consistent with Didolkar et al.'s clustering: once you cluster, you converge to a coarse taxonomy that's stable.

For **task generation**, more is better but with caveats: every cart can yield ~5–10 reasonable comprehension tasks, so 20 carts gives you ~100–200 tasks, which is comfortable for a first-run eval. Skill-Mix evaluated each `(k skills, 1 topic)` combination across 30 instances; with ~100 tasks distributed across ~30–50 skills, you get adequate per-skill coverage.

**Concrete recommendation for v0.1:**

| Phase | Cart count | Rationale |
|-------|-----------|-----------|
| Pilot | 5 carts | Smoke-test the pipeline end-to-end before scaling. |
| Skill-extraction corpus | 15–25 carts | Saturates the skill catalog. |
| Task-generation corpus | 20–40 carts (overlaps with above) | Enough tasks per skill. |
| Future expansion | up to ~100 | Only if you want per-genre breakdowns. |

If you've already compiled "a couple of repos" of carts, **pick a stratified sample of 20–25 carts** for v0.1. Stratify across at least three of: platformers, shooters, puzzles, top-down adventures, demos. Avoid sampling 20 platformers — you'll get a lopsided skill catalog.

### 5.3 Don't optimize corpus size in isolation

The size that matters is *post-filtering*, after quality assurance (next section). Plan to lose 20–40% of candidate carts to QA. So if you want 25 carts for skill extraction, start by gathering ~35–40 candidates.

## 6. Quality Assurance of the Corpus

Two complementary approaches: a written guideline that you (and an LLM judge) apply, plus the LLM judge itself. Use both. Datasheets for Datasets, originally proposed by Gebru et al., explicitly recommend documenting motivation, composition, collection process, and recommended uses to facilitate transparency and reproducibility — the QA guideline below is the operational version of those questions.

### 6.1 Why write a guideline at all?

Three reasons:

1. **Reproducibility.** Someone else (or future-you) needs to be able to add carts to the corpus and apply the same standard.
2. **Auditing the LLM judge.** Without a written rubric, you can't tell whether the LLM is being lenient, strict, or inconsistent. A guideline lets you spot-check disagreements.
3. **Disclosure.** When you report results, you have to disclose what's in the corpus. A guideline is the basis of that disclosure.

### 6.2 Inclusion criteria (the guideline)

A cart qualifies for the corpus if **all** of the following are true:

| # | Criterion | How to check |
|---|----------|--------------|
| 1 | **License permits use.** Public-domain, CC-licensed, or explicitly redistributable. Lexaloffle BBS carts default to "all rights reserved" unless the author states otherwise — assume restrictive unless proven otherwise. | Read cart header comments and BBS post. |
| 2 | **`.p8` source is available** (not just `.p8.png`). | File extension. |
| 3 | **Code is reasonably idiomatic.** Heavy obfuscation (single-letter variables everywhere, packed expressions) makes both extraction and tasks unfair. | Visual inspection or LLM judge. |
| 4 | **Cart runs and is non-trivial.** Excludes empty templates and "hello world" demos. As a rough floor: > 80 tokens, > 200 chars per `INFO` output. | `pico-8 -run` or read code. |
| 5 | **No NSFW, hateful, or harmful content.** | Visual inspection. |
| 6 | **Distinct from other carts in the corpus.** No two carts that are forks of each other or visibly the same mechanic with reskinned sprites. | LLM judge with the existing corpus as context. |
| 7 | **Self-contained.** No `#include` of external files you don't also have. | Grep for `#include`. |

PICO-8's own limits give us a natural upper bound on cart size: PICO-8 carts are 32k data encoded as PNG files, the code is P8 Lua with a maximum of 8192 tokens, and when saving in .png or .rom format the compressed size of the code must be less than 15360 bytes so that the total data is <= 32k. So every qualifying cart is comfortably within any modern LLM's context window — the constraint is *output* and *reasoning* tokens, not input.

### 6.3 Recommended QA workflow

1. **Programmatic filter.** Reject obvious failures (missing `.p8`, too small, contains `#include` of missing files). Cheap, deterministic.
2. **LLM judge.** Pass each remaining cart to Claude with the inclusion criteria as the rubric. Output: JSON `{cart_id, pass: bool, criterion_scores: {...}, notes: "..."}`. Use **temperature 0** for reproducibility.
3. **Human spot-check on the borderline 20%.** Where the LLM gave a marginal score or flagged uncertainty, review by hand. Skill-Mix did exactly this for graders: they conducted a test to measure grading quality, where five Ph.D. students and postdocs in NLP and LLMs were given five GPT-4 outputs, asked to give individual points for criteria, and then they computed mean and standard deviation across human graders. The pattern — automated scoring + targeted human review — is the established practice.
4. **Record decisions.** Every reject gets a logged reason. This is the audit trail.

### 6.4 LLM judge prompt skeleton

```
You are a quality reviewer for a PICO-8 cart corpus used to evaluate LLM
code understanding. Score this cart against each criterion below. Be strict
on idiomatic code (criterion 3) — heavy obfuscation disqualifies.

CART:
<paste full .p8 contents>

CRITERIA: [list from §6.2]

Return JSON:
{
  "cart_filename": "...",
  "verdict": "include" | "exclude" | "borderline",
  "criterion_scores": { "license": "pass"|"fail"|"unknown", ... },
  "notes": "<1-3 sentences explaining the verdict>"
}
```

## 7. Context-Window and Reading-Accuracy Considerations

You asked how much I (the strong LLM) can correctly and accurately read. Three things matter, and they pull in different directions.

### 7.1 Hard ceiling vs. effective ceiling

PICO-8 carts are tiny relative to any modern LLM context window (8192 Lua tokens ≈ 20–30 KB of source). The hard ceiling is not the constraint. The *effective* ceiling — where retrieval and reasoning quality starts to degrade — is.

### 7.2 "Lost in the middle" and what's changed

The classic result is Liu et al. 2023, where retrieval accuracy follows a U-shaped curve over position — best at the start and end, worst in the middle. Empirically, models often over-weight local or recent tokens and miss salient information in the middle of long inputs, and scaling context windows to hundreds of thousands or even millions of tokens improves access to evidence but does not fully resolve interference issues.

More recent results are more nuanced: recent work finds that Gemini 2.5 Flash can answer needle-in-a-haystack questions with great accuracy regardless of document position including when the document is nearly at the input context limit, suggesting the lost-in-the-middle effect is not present for simple factoid Q&A in that model, but a 2025 study found that LLM performance drops sharply when the gold context is shorter — smaller gold contexts consistently degrade model performance and amplify positional sensitivity — across three diverse domains and seven state-of-the-art LLMs.

The practical implication for our framework: **single-cart tasks are safe** (a whole cart fits in a few thousand tokens, well below the regime where lost-in-the-middle bites). But if you ever feed *multiple carts* to the strong LLM in one prompt — e.g. "compare these five carts" — degradation is real and you should fall back to a one-cart-at-a-time loop with a synthesis pass at the end.

### 7.3 Operating rules for v0.1

- One cart per prompt during skill extraction. Don't batch carts to "save tokens."
- One cart per prompt during task generation. Same reason.
- When grading, the grader sees: the task prompt, the student's full output, the cart, and the rubric. That's it — no other tasks, no other students.
- Cap any single context at ~20K input tokens for v0.1. This is well under any modern model's limit but well within the "robust retrieval" regime for all known models.

## 8. Model Choice for the Student

### 8.1 Is Qwen3-8B a wise pick?

Yes, for the right reasons, and you should know what its weak points are.

**Reasons it's a good first-run student:**

- **Genuine capability at small scale.** Qwen3-8B/4B/1.7B-Base models even outperform larger size Qwen2.5-14B/7B/3B Base models on benchmarks, and Qwen3-8B shows significant enhancement in reasoning capabilities, surpassing previous QwQ in thinking mode and Qwen2.5 instruct models in non-thinking mode on mathematics, code generation, and commonsense logical reasoning.
- **Thinking/non-thinking mode toggle** lets you compare CoT-on vs CoT-off cleanly — this is exactly what you want for a metacognition study.
- **Context.** Context length is 32,768 natively and 131,072 tokens with YaRN. 32K natively is more than enough for one PICO-8 cart plus a task prompt plus generation budget.
- **Open weights, Apache-2.0**, runs locally on Ollama — reproducibility is automatic.
- **Sensible recommended settings exist.** For benchmarking on highly complex problems such as math and programming competitions, the recommended max output length is 81,920 tokens to provide sufficient space for detailed responses.

**Caveats:**

- 8B is a small model. Expect substantially lower pass rates than frontier models on k≥3 compositional tasks. That's *fine for an eval* — it's actually a feature, because a model that gets 95% on everything tells you nothing.
- Ollama defaults may quantize aggressively (typically Q4_K_M for an 8B model on consumer hardware). Quantization affects reasoning. A study on quantized reasoning models evaluated quantization strategies on benchmarks including AIME-120, MATH-500, GSM8K, GPQA-Diamond, and LiveCodeBench, comparing against BF16 baselines. **Record the exact quantization used** (e.g. `qwen3:8b-q4_K_M`) — it's part of the model identity.
- For long-horizon agentic code tasks, even Qwen's own coder line targets larger models; Qwen3-Coder-Next was specifically designed for agentic training that handles multi-step code editing, tool usage, and fault recovery in realistic development settings. 8B-non-coder is a reasonable starting point for *comprehension* tasks, less so for *generation* tasks.

### 8.2 Model-choice checklist

When picking or switching student models, score each candidate against this checklist:

| # | Criterion | What it means |
|---|----------|--------------|
| 1 | **Open weights or stable API.** | You need to re-run the same model six months from now. Closed model deprecations break longitudinal comparisons. |
| 2 | **Context window ≥ 16K tokens.** | Comfortable headroom over the biggest single-cart task. |
| 3 | **Native instruction-following.** | Base models without instruction tuning will fight you on output formatting. |
| 4 | **Reasoning/CoT mode available.** | You need CoT for the metacognition pass. Either built-in (Qwen3) or prompt-induced. |
| 5 | **Tokenizer documented.** | You need to count input/output tokens for cost and length budgeting. |
| 6 | **Runs in your inference stack.** | Ollama-compatible if local; vLLM/TGI-compatible if you scale. |
| 7 | **Quantization documented.** | Record the exact quant (Q4_K_M, Q8_0, FP16, BF16). This is part of the model's identity. |
| 8 | **Reasonable license for your use.** | Apache-2.0, MIT, Llama community license, etc. Avoid models with non-commercial or research-only clauses if you plan to publish. |
| 9 | **Benchmark numbers available.** | At minimum: HumanEval, MBPP, GSM8K, MMLU. Lets you sanity-check that your model performs as expected. |
| 10 | **Hardware fits your budget.** | 8B Q4 needs ~6 GB VRAM; 14B Q4 needs ~10 GB; 32B Q4 needs ~20 GB. |

A candidate is "ready" if it scores yes on all 10. Borderline candidates can be used but flag the gap in the report.

### 8.3 Recommended progression for your eval

1. **v0.1: Qwen3-8B (Ollama, document the quant).** Baseline. Establishes the pipeline.
2. **v0.2: same Qwen3-8B + a second model of similar scale** (e.g. Llama-3.1-8B-Instruct, Gemma-3-9B) for cross-model comparison. The grids only get interesting when you have multiple students.
3. **v0.3: scale up one size class** (14B or 27B) to see the k-skill compositionality curve predicted by Arora & Goyal (2023) — they argue model scale roughly doubles the k of skills the model can reliably combine.

## 9. Documenting the PICO-8 Carts You Used

Industry best practice for documenting a dataset used in an evaluation is **Datasheets for Datasets** (Gebru et al., CACM 2021). In the electronics industry, every component is accompanied by a datasheet describing standard operating characteristics, test results, and recommended usage; by analogy, every dataset should be accompanied with a datasheet documenting its motivation, creation, composition, intended uses, distribution, maintenance, and other information.

For our case the relevant fields, adapted to a code corpus, are:

### 9.1 Per-corpus datasheet (one document for the whole corpus)

- **Motivation.** Why we built this corpus, what question it answers.
- **Composition.** How many carts, what genres, source distribution.
- **Collection process.** Where we got the carts, what dates, what filter we applied.
- **Preprocessing.** Any transformations (e.g. stripping comments, normalizing whitespace) — for our eval, ideally none, since we want the cart as the author published it.
- **Uses.** What this corpus is intended for, what it shouldn't be used for.
- **Distribution.** Whether you redistribute the carts or just provide pointers + a build script.
- **Maintenance.** Who maintains it, how updates are versioned.
- **Ethical considerations.** Licensing, author attribution, any contact with authors.

### 9.2 Per-cart record (one row per cart in a manifest)

A `corpus_manifest.csv` (or JSONL) with one row per cart, columns:

| Column | Example | Notes |
|--------|---------|-------|
| `cart_uid` | `4d2e-1100-8a3f-9bb1` | UID in our scheme. |
| `filename` | `celeste-classic.p8` | As stored locally. |
| `title` | "Celeste Classic" | Human-readable. |
| `author` | "Maddy Thorson, Noel Berry" | As credited. |
| `source_url` | `https://www.lexaloffle.com/bbs/?tid=...` | Permalink. |
| `source_accessed` | `2026-05-14` | ISO date. |
| `license` | `CC-BY-NC-SA-4.0` or `all-rights-reserved` or `public-domain` | SPDX where applicable. |
| `genre` | `platformer` | Free text; controlled list helps. |
| `token_count` | `5832` | From PICO-8 `INFO` command. |
| `char_count` | `28104` | From `INFO`. |
| `compressed_bytes` | `12041` | From `INFO`. |
| `qa_verdict` | `include` | From the LLM judge. |
| `qa_notes` | "..." | Free text. |
| `sha256` | `...` | Of the `.p8` file contents. Pins the exact version. |

The `sha256` is non-negotiable. Carts get edited and re-uploaded; if you don't pin a hash, your eval isn't reproducible.

### 9.3 README and citation file

In the corpus directory, alongside the manifest:

- `README.md` — the datasheet content from §9.1 in human-readable form.
- `CITATION.cff` — machine-readable citation metadata (GitHub recognizes this format).
- `LICENSES/` — a copy of each distinct license under which carts are used, plus a NOTICE file mapping each cart to its license.

### 9.4 If you cannot redistribute

When carts are "all rights reserved" — which is the default on the Lexaloffle BBS — you can still document them and use them privately, but you cannot redistribute the cart files. The reproducible artifact then becomes: the manifest (with URLs and hashes) + a `fetch_carts.sh` script that re-downloads. Anyone re-running the eval downloads their own copy. This is the same pattern used by, e.g., academic NLP corpora like Common Crawl-based datasets.

## 10. Evaluation Output: The Four Grids

The underlying object is a tensor:

```
T[model, task, skill] ∈ {pass, partial, fail, n/a}
```

`n/a` means the skill isn't tagged on that task. There are four useful pivots — three outcome views and one structural view of the catalog itself. The fourth view (skill × task **for a given model**) is the diagnostic view: it answers "where did model M actually break on task T?"

| # | Grid | Rows | Columns | Cell | Use | Outcome or structural? |
|---|------|------|---------|------|-----|------------------------|
| 1 | **Model × Skill** | Models | Coarse skills | Pass rate on tasks tagged with this skill | Which models are strong at which skills | Outcome |
| 2 | **Task × Skill** | Tasks | Coarse skills | 1 if task is tagged with this skill, 0 otherwise | Task design view: what each task exercises | Structural (no model outcome) |
| 3 | **Model × Task** | Models | Tasks (sorted easy→hard) | Aggregate pass on the task | Standard leaderboard: head-to-head model comparison | Outcome |
| 4 | **Skill × Task for a given model M** | Coarse skills | Tasks | Pass/fail of M on each (skill, task) pair the task taps | Diagnosing where M broke: was it the skill, or task-specific noise? | Outcome, one model at a time |

Color coding for the three outcome grids: green = pass, yellow = partial credit (when grading rubric awards partial points, à la Skill-Mix's 3-point illustrate-the-skill + 1-point-on-topic + 1-point-coherent rubric), red = fail, grey = n/a. Grid 2 (task × skill) is a binary tagging matrix — black-filled cells indicate the tagging; no outcome colors apply.

"Sorted easy→hard" for tasks means: sort tasks by ascending pass rate of a reference model (initially Qwen3-8B). Once you have multiple models, you can sort by average across models. This gives the difficulty curve that Arora & Goyal's emergence theory predicts should shift with model scale.

**Default catalog axis: coarse skills.** All four grids use the coarse skill catalog produced by Phase 1.5 clustering (§11). The raw skill catalog is preserved for drill-down: when a coarse-skill cell looks anomalous, you can expand to see the raw skills inside it.

## 11. Phase 1.5: Skill Catalog Clustering

Between raw extraction and task generation, the catalog is coarsened. Skill-extraction at the chunk level produces narrow, evidence-rich skills (per QA_GUIDELINE_AND_PROMPTS.md §3.1), and across ~25 carts × ~5 chunks × ~10 skills, you accumulate roughly 1,000–1,500 raw skill names. Many are near-duplicates. The coarsening pass reduces the catalog to ~100–200 canonical skills suitable for task tagging and grid axes.

This is the same coarsening step Didolkar et al. used in the metacognition paper: fine-grained LLM-proposed skill labels are clustered semantically into compound, more abstract skills. They went from thousands of fine-grained labels to a few dozen coarse families.

The full procedure, including the LLM clustering prompt, is documented in QA_GUIDELINE_AND_PROMPTS.md §8. The key outputs:

- **Coarse catalog:** ~100–200 canonical skills, each with a UID and a four-word name.
- **Raw catalog:** preserved with `parent_uid` pointing at the coarse parent. Raw skills become aliases for diagnostic drill-down.

Both catalogs ship with the eval. Tasks are tagged with coarse skill UIDs; CoT analysis can map student reasoning to either level.

## 12. Phase 2: Synthetic Data Self-Improvement Loop

This is the second-stage idea from the original notes, included here for completeness but not part of v0.1:

For each (coarse skill, model) cell where the model performs poorly:

1. Generate N candidate task instances exercising that skill.
2. Run the student on each, capture CoT.
3. Have the grader rank the N outputs and keep the best K (e.g. N=16, K=4).
4. Use those K as training/fine-tuning examples.
5. Re-evaluate; measure delta.

This is conceptually the "rejection sampling fine-tuning" pattern, restricted to a target skill axis. The Didolkar et al. paper provides direct precedent for using skill labels to organize training-data selection.

## 13. v0.1 Deliverables Checklist

By end of v0.1 you should have, on disk:

- [ ] `corpus/` directory with 20–25 qualifying carts (or projects, per multi-file handling in QA §2.4), manifest, README, CITATION.cff, LICENSES.
- [ ] `skills_raw.jsonl` — one record per raw skill with UID, name, definition, evidence, k_level, source chunk.
- [ ] `skills_coarse.jsonl` — one record per coarse skill with UID, name, definition, and list of raw-skill UIDs assigned to it (Phase 1.5 output).
- [ ] `tasks.jsonl` — one record per task with UID, prompt, expected answer, rubric, tagged coarse-skill UIDs, source cart UID.
- [ ] `runs/qwen3-8b-q4_K_M/` — one directory per `(model, quantization)` containing per-task student outputs and grader verdicts.
- [ ] `results.parquet` — flattened `(model, task, coarse_skill) → verdict` tensor.
- [ ] Four rendered grids (HTML or notebook), color-coded per §10.
- [ ] `METHOD.md` — this document, kept up to date with what you actually did.

## 14. References

- Yu, Kaur, Gupta, Brown-Cohen, Goyal, Arora (2024). "Skill-Mix: A Flexible and Expandable Family of Evaluations for AI Models." ICLR 2024. <https://arxiv.org/abs/2310.17567>
- Didolkar, Goyal, Ke, Guo, Valko, Lillicrap, Rezende, Bengio, Mozer, Arora (2024). "Metacognitive Capabilities of LLMs: An Exploration in Mathematical Problem Solving." NeurIPS 2024. <https://arxiv.org/abs/2405.12205>
- Arora, Goyal (2023). "A Theory for Emergence of Complex Skills in Language Models." <https://arxiv.org/abs/2307.15936>
- Liu et al. (2023). "Lost in the Middle: How Language Models Use Long Contexts." <https://arxiv.org/abs/2307.03172>
- Hsieh et al. (2024). "RULER: What's the Real Context Size of Your Long-Context Language Models?" <https://arxiv.org/abs/2404.06654>
- Bianchi et al. (2025). "Lost in the Haystack: Smaller Needles are More Difficult for LLMs to Find."
- Gebru, Morgenstern, Vecchione, Wortman Vaughan, Wallach, Daumé III, Crawford (2021). "Datasheets for Datasets." CACM 64(12). <https://arxiv.org/abs/1803.09010>
- Qwen Team (2025). "Qwen3 Technical Report." <https://arxiv.org/abs/2505.09388>
- Lexaloffle (2024). "PICO-8 Manual." <https://www.lexaloffle.com/dl/docs/pico-8_manual.html>

## 15. Changelog

- **v0.2 (2026-05-14):** §10 corrected to four grids (separated structural task×skill view from outcome views, added skill×task-for-a-given-model diagnostic view). New §11 on Phase 1.5 clustering; old §11 (Phase 2) renumbered to §12. Multi-file project handling referenced from QA companion doc. Worked example from `Enichan/Pico8Platformer` dry run informs the calibration notes here.
- **v0.1 (2026-05-14):** Initial draft. Captures pipeline, UID scheme, corpus sizing, QA guideline, context-window guidance, model-choice checklist, datasheet structure, grid spec, deliverables.

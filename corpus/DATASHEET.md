# Datasheet: PICO-8 Skill-Extraction Corpus

**Version:** 0.1
**Date:** 2026-05-15
**Maintainer:** Louiese Nase
**Structure adapted from:** Gebru et al., "Datasheets for Datasets" (Communications of the ACM, 2021)

---

## Motivation

**For what purpose was the corpus created?**
To support skill-based evaluation of large language models on game source code. PICO-8 cartridges are small, self-contained Lua files covering a wide range of game mechanics, making them a tractable starting corpus for adapting the Skill-Mix and metacognition methodologies (originally developed for math) to code comprehension.

**Who created the corpus and on whose behalf?**
Louiese Nase, on a contract evaluation for a small AI + gamedev company. The corpus is intended as data-preparation infrastructure for the company's game-code AI training pipeline.

**Has it been used for any tasks already?**
v0.1 of the eval framework. Specifically: skill extraction (33 skills from one cart), task generation (10 tasks), one student-model run (Qwen3-235B-A22B-Instruct-2507), and rendering of three diagnostic grids. See `docs/V0_1_RESULTS.md`.

---

## Composition

**What do the instances represent?**
Each instance is one PICO-8 cartridge, stored as a `.p8` text file. A cartridge contains a complete game in Lua plus its sprite, map, sound, and music data.

**How many instances are there in total?**
1 (v0.1). The pipeline is designed to scale; v0.2 targets 5–10 carts.

**Does the corpus contain all possible instances or is it a sample?**
A purposive sample. The first cart was chosen for its readable code, multiple gameplay systems (platformer + key/door puzzles + enemy AI + collectibles), moderate size (1,055 lines of Lua), and permissive license. Selection criteria are documented in `docs/QA_GUIDELINE_AND_PROMPTS.md` §1.

**What does each instance consist of?**
A `.p8` text file containing the cart's full source: Lua code section (`__lua__`), sprite data (`__gfx__`), tile flags (`__gff__`), map data (`__map__`), sound effects (`__sfx__`), music (`__music__`), and optional cart label image (`__label__`). For skill extraction, only the `__lua__` section is used.

**Is there a label or target associated with each instance?**
Not in the raw corpus. Skills are extracted from each cart and stored separately under `extraction/raw/`. Evaluation tasks are generated separately under `tasks/`. The raw cart is the source artifact, not pre-labeled.

**Is any information missing from individual instances?**
For the v0.1 cart (Bootyful Demake), one chunk of the Lua source (`gameinit_and_helpers`) was not included in skill extraction. Several extracted skills reference data structures whose definitions live in that chunk. Documented in `qa/audit_log.md` entry 2026-05-14. v0.2 should run a supplementary extraction.

**Are relationships between instances made explicit?**
For v0.1 with a single cart, n/a. v0.2 onward, the corpus manifest (`corpus/manifest.jsonl`) records each cart's UID, license, source URL, and SHA-256 hash. Cross-cart skill clustering (Phase 1.5 of the framework) is planned for when the corpus exceeds 3 carts.

**Are there recommended data splits?**
Not applicable at v0.1. For multi-cart v0.2+, splits should be by cart (not by skill or task) to avoid leakage: a model evaluated on cart B should not have been trained on tasks derived from cart B.

**Are there any errors, sources of noise, or redundancies?**
- The chunking gap on Bootyful Demake (above) means the v0.1 skill catalog under-represents the cart's data-table structures.
- Skill extraction is performed by an LLM (Claude Opus 4.7) and may produce semantically overlapping skills that would consolidate under a clustering pass.
- The 4-word skill naming format occasionally forces compression that loses nuance (e.g., `match_world_screen_coords` originally was 5 words; meaning preserved, format compliant).

**Is the corpus self-contained?**
Yes. Each `.p8` file is fully self-contained Lua + binary asset sections. No external dependencies are required to read the cart's source code. To run the cart visually, PICO-8 (commercial software by Lexaloffle) is required, but this corpus's purpose is code comprehension, not gameplay.

**Does the corpus contain confidential or offensive data?**
No. All carts are publicly published on the Lexaloffle BBS under their authors' chosen licenses.

---

## Collection process

**How was the data acquired?**
Carts were downloaded from the Lexaloffle BBS (https://www.lexaloffle.com/bbs/) — the official PICO-8 community forum. Each download was an HTTP fetch of the cart's `.p8` text file from the URL listed in the BBS post.

**Over what timeframe was the data collected?**
2026-05-14 onward.

**What mechanisms or procedures were used to collect the data?**
Manual download from each cart's BBS post URL, after verifying license terms. The verification procedure is documented in `docs/QA_GUIDELINE_AND_PROMPTS.md` §1.6.

**Were any ethical review processes conducted?**
Not applicable — the corpus contains publicly published software released under permissive licenses by their original authors. No personal data, no human subjects.

---

## Preprocessing / cleaning / labeling

**Was any preprocessing or cleaning done?**
The cart's `__lua__` section is extracted programmatically by `scripts/run_student_cerebras.py` (and the original extraction prompts) before being passed to LLM inference. Other cart sections (sprites, music, map) are preserved in the source file but ignored for skill extraction.

**Was the "raw" data saved in addition to the cleaned data?**
Yes. The full `.p8` file is preserved at `corpus/carts/<cart_uid>/`. Extracted Lua and derived artifacts are stored separately under `extraction/raw/`.

---

## Uses

**Has the corpus been used for any tasks already?**
See "Composition" above.

**Is there a repository linking to publications and systems that use this corpus?**
This is the repository.

**What (other) tasks could the corpus be used for?**
- Fine-tuning an LLM for game-code generation
- Evaluating game-code understanding across model families
- Benchmarking game-specific reasoning skills (state machines, tile-flag arithmetic, frame-loop control flow)
- Comparative analysis of code-comprehension across programming languages and domains

**Is there anything about the composition or collection process that might impact future uses?**
PICO-8 carts are constrained to ~8K Lua tokens by the runtime. This is a feature for fitting in LLM context windows; it is a limitation if the goal is evaluating LLMs on full-scale game engines (Unity, Unreal, Godot). The skill methodology generalizes; the corpus does not.

**Are there tasks for which the corpus should NOT be used?**
- Commercial uses of individual carts may violate their licenses. See `corpus/LICENSES/NOTICE.md` for per-cart terms.
- Cross-cart skill comparisons before clustering (Phase 1.5) will produce inflated catalog sizes and inconsistent naming.

---

## Distribution

**Will the corpus be distributed to third parties?**
The corpus repository is shared with the contracting team. Individual cart files remain subject to their original licenses; the corpus does not relicense them.

**How will the corpus be distributed?**
Through the git repository. Cart files are stored directly in the repo because their licenses permit redistribution with attribution.

**Will the corpus be distributed under a copyright or other IP license?**
The pipeline code is MIT-licensed (see `LICENSE` in repo root). Each cart retains its original license, recorded in `corpus/LICENSES/NOTICE.md`.

---

## Maintenance

**Who is supporting / hosting / maintaining the corpus?**
Louiese Nase, for v0.1.

**How can the maintainer be contacted?**
Through the repository's issue tracker, or via the contracting platform.

**Will the corpus be updated?**
v0.2 is planned with additional carts. Updates will be tagged in git (e.g., `v0.2`, `v0.3`).

**If the corpus relates to people, are there applicable limits on the retention of the data?**
The corpus contains source code, not personal data. Author names are recorded for attribution as required by the carts' licenses.

**Will older versions of the corpus continue to be supported / hosted / maintained?**
Yes, via git tags. Earlier versions remain accessible at their tagged commits.
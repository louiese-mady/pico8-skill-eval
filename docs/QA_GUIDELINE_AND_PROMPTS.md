# PICO-8 Cart QA Guideline and LLM Prompts

**Companion to:** EVAL_FRAMEWORK_DOC.md
**Version:** 0.3
**Date:** 2026-05-14

**Changelog:**
- **v0.3:** Simplified §2 chunking strategy. PICO-8's size limits mean most carts don't need chunking; the rule is now "one chunk = one logical unit of authorship" (whole cart for single-file carts, one `.lua` file per module for `#INCLUDE` projects). Dropped the 50–200 line "sweet spot" framing as over-applied generic advice.
- **v0.2:** Added §2.4 on multi-file projects (now folded into §2.1). Added §3.1 explicit instruction on skill granularity. Refined skill-extraction prompt: chunk-size-dependent skill count, k_level criterion clarified, anti-generalization instruction. Added §7 worked example and §8 clustering phase.
- **v0.1:** Initial guideline + QA + skill-extraction prompts.

This document contains three things:

1. The full QA guideline for selecting PICO-8 carts into the evaluation corpus.
2. The chunking strategy for sending cart code to an LLM.
3. Two production-ready LLM prompts: one for QA judgment, one for skill extraction.

The skill-naming convention is fixed: **every skill name is exactly four words, lower-case, joined by underscores.** This convention applies everywhere skills appear — in extraction output, in the catalog, in task tags, and in CoT labels.

---

## 1. Quality Check for PICO-8 Cart Selection

A cart qualifies for inclusion in the evaluation corpus if and only if it passes **all seven** criteria below. Marginal or unclear cases are flagged `borderline` and reviewed by a human before being accepted or rejected.

### 1.1 Readable identifiers

Function names, variable names, and table keys must be human-readable English words or recognizable abbreviations. The goal is that a reader unfamiliar with the cart can guess what a function does from its name alone in the majority of cases.

- **Acceptable:** `player_health`, `enemy_update()`, `spawn_particle(x, y)`, `is_grounded`, `coyote_time`, `hp`, `dx`, `dy` (idiomatic short forms are fine).
- **Not acceptable:** `a()`, `b1()`, `xv2()`, single-letter function names used pervasively, deliberately scrambled identifiers, identifiers that are abbreviations no reasonable reader could decode (e.g., `qxz_p()`).

Borderline carts (e.g., short variable names that are nevertheless used consistently and locally — `i`, `j`, `n` as loop indices, `dt` as delta time) pass this criterion.

### 1.2 Multiple gameplay systems

The cart must implement at least **three** distinct gameplay or simulation systems drawn from the following list. The cart need not implement them well or completely — only that they are recognizably present:

- Movement (player control, physics, kinematics)
- Enemies or AI (state machines, pathing, hostile behaviors)
- Collision detection or response
- Particles, juice, or visual effects
- Scoring, progression, or game state
- Inventory, equipment, or resource management
- Level loading, map traversal, or scene transitions
- Audio reactivity (music sync, sfx triggers tied to gameplay)
- Input remapping, menus, or UI flow beyond a single title screen

Carts that are pure tech demos with only one system (e.g., a particle playground with no game loop) are excluded. Carts that are pure visualizations or screensavers are excluded. The aim is to capture programs with enough cognitive surface area to support multiple skills per task.

### 1.3 Moderate complexity

The cart's code size, measured by PICO-8's `INFO` command, must fall within both of these ranges:

- **Lua tokens:** between 500 and 6,000 (PICO-8's hard ceiling is 8,192).
- **Characters:** between 2,000 and 28,000 (PICO-8's hard ceiling is 65,535).

The lower bound excludes hello-world demos and trivial sketches that cannot support meaningful task generation. The upper bound excludes carts that pushed against PICO-8's limits and therefore had to minify or pack their code densely to fit — these are unfair to evaluate because their structure is distorted by the size constraint rather than chosen for clarity. Carts outside the range are excluded automatically; this is the only quantitative criterion and should be checked programmatically before any LLM review.

### 1.4 No heavy minification or compression

Even within the size range above, some carts are written in deliberately compact style — chained statements on single lines, unnecessary token-saving tricks, abuse of PICO-8's terse operator syntax beyond idiomatic use. This makes both skill extraction and task generation unreliable: the LLM is forced to disentangle compactness before it can identify what the code does, and tasks asked about minified code become tasks about decompression rather than about the underlying skill.

Indicators that disqualify a cart:

- Multiple unrelated statements separated by semicolons on the same line throughout the cart.
- Pervasive use of one-character variable names beyond loop counters.
- Inlined helper functions that should plainly be separate (e.g., a 40-character anonymous function used once).
- Use of PICO-8's compressed shorthand (`?` for `print`, `!=` written as `~=` and chained without spaces, etc.) to the point where reading slows substantially.

Idiomatic compactness that all PICO-8 programmers use — `for i=0,15 do`, single-line `if` statements for short conditions — is fine.

### 1.5 Not predominantly asset content

The cart's `.p8` file contains sections beyond the Lua code: `__gfx__` (sprite data), `__map__` (tilemap data), `__gff__` (sprite flags), `__sfx__` (sound effects), `__music__` (song patterns), and `__label__` (cover image). A cart qualifies for the corpus only if the `__lua__` section is the substantive part of the file by character count relative to the code-bearing portion. As a working rule: after stripping non-Lua sections, the remaining code must still meet criterion 1.3.

This criterion exists because some published carts are essentially asset packs with a thin Lua wrapper to display them. They are valid PICO-8 work but provide almost no surface for skill extraction.

### 1.6 License recorded

The cart's license must be identifiable and recorded in the corpus manifest. The aim is not to restrict the corpus to permissive licenses — for private evaluation, "all rights reserved" carts are acceptable — but to make license status explicit and auditable.

- **Permissive licenses** (CC-BY, CC-BY-SA, MIT, public domain, etc.): the cart can be redistributed with the corpus.
- **Restrictive licenses or unstated licenses** (the Lexaloffle BBS default is "all rights reserved" unless the author specifies otherwise): the cart is used for evaluation only, never redistributed, and the manifest stores the cart URL and hash instead of the cart file.

A cart with **no identifiable author and no findable source** is excluded — there is no audit trail and no way to honor takedown requests.

### 1.7 Substantively distinct

The cart must not be a near-duplicate of any cart already in the corpus. Specifically:

- Different game from any existing cart (not a reskin with identical mechanics).
- Different author or, if the same author, a substantively different game (not the same author's iterative versions of the same project).
- Different primary system mix (a third puzzle game with a grid and tile-matching adds little if two are already in the corpus; a first action-RPG adds a lot).

This criterion is checked relative to the existing corpus and so its judgment shifts as the corpus grows. Early carts have a low bar to clear; later carts must add genuinely new structure.

---

## 2. Chunking Strategy for LLM Prompts

**Short version: one chunk = one logical unit of authorship.**

For most PICO-8 carts, you don't need to chunk at all. PICO-8's hard ceiling is 8,192 Lua tokens / 65,535 characters per cart, which is ~25K LLM tokens at the absolute maximum — comfortably inside any modern strong model's high-fidelity reading regime. Lost-in-the-middle does not bite at this scale.

### 2.1 The rule

| Cart shape | What counts as one chunk |
|------------|--------------------------|
| **Single-file cart** (one `.p8` file, all code in its `__lua__` section) | The entire `__lua__` section. One chunk per cart. |
| **Multi-file `#INCLUDE` project** (e.g., Celeste 2) | One chunk per author-written `.lua` module file. |
| **Multi-cart project** (`1.p8`, `2.p8`, …) | The Lua section of each cart, treated like a single-file cart. Asset-only carts are skipped. |
| **The rare oversized single-file cart** (>1500 lines, no module split) | Split along the author's section comments. Each section is one chunk. |

In all four cases, the unit is **semantic**, not size-based. A chunk is whatever the author treated as one coherent piece of code.

### 2.2 What never goes into a chunk

- `__gfx__`, `__map__`, `__gff__`, `__sfx__`, `__music__`, `__label__` — asset sections.
- Vendored third-party libraries (e.g., `px9_comp.lua`/`px9_decomp.lua`, `pico8lib` modules, JSON or tween helpers copy-pasted from elsewhere). Skill extraction should hit the author's gameplay code, not generic library internals.
- Minified or transport-compressed versions of the code — always use the version the author wrote.

### 2.3 What to include alongside the chunk

- A one-line header naming the source cart and chunk identifier.
- The project summary if available (one or two sentences), so the LLM knows what role this chunk plays in the larger project. Only meaningful for multi-file projects.
- The chunk itself, in a fenced code block, with original whitespace preserved.

### 2.4 When does this produce a "chunk" larger than 400 lines?

Almost never — PICO-8's size limits prevent it. The cases where it can happen:

- A single-file cart that hits PICO-8's full 8192-token allowance with one giant section. Roughly equivalent to 800–1200 lines of moderately commented Lua. **Acceptable to send whole** unless you specifically want finer chunk_ids; the model handles it.
- A `#INCLUDE` project where the author put 1500 lines into a single `objects.lua`. **Split it** along comment-marked sections, but the split is for cognitive clarity in extraction, not for context-window pressure.

In practice: don't pre-emptively split. Send the natural unit. If extraction quality suffers (catalogues come back vague, evidence pointers are imprecise), then split. For v0.1, expect to split exactly zero times.

### 2.5 Why this differs from generic "chunk your code" LLM advice

Generic advice assumes arbitrary-sized codebases. PICO-8 carts are already small by construction. The right rule for this corpus is "respect the author's modularity," not "split into 200-line slices." Earlier versions of this section over-applied the generic rule.

---

### 2.6 Manifest example for a multi-file project

```yaml
cart_uid: 4d2e-1100-8a3f-9bb1
project_name: Celeste Classic 2
project_type: include_based   # or multi_cart, or single_file
author: Maddy Thorson, Noel Berry, Lena Raine
source_url: https://github.com/ExOK/Celeste2
license: CC-BY-NC-SA-4.0
chunks:
  - path: main.lua
    sha256: ...
  - path: player.lua
    sha256: ...
  - path: gamestate.lua
    sha256: ...
  # px9_comp.lua, px9_decomp.lua excluded: third-party compression library
```

---

## 3. Skill Naming Convention

---

## 3. Skill Naming Convention

Every skill in the catalog has a name in the form:

```
word_word_word_word
```

Exactly four words, lower-case, joined by underscores. No prefixes, no suffixes, no parenthetical qualifiers. Examples:

- `identify_draw_callback_function`
- `trace_variable_across_scopes`
- `detect_collision_response_pattern`
- `parse_state_machine_logic`
- `recognize_particle_emission_pattern`
- `infer_player_input_handling`
- `locate_initialization_versus_update`
- `match_function_call_signatures`

Why four words: it forces the namer to commit to a specific, narrow capability (one word is too vague, two words tends to be too generic — `parse_code` could mean anything). It is generous enough to distinguish closely related skills (`identify_draw_callback_function` vs `identify_update_callback_function`). And the uniform shape makes the catalog easy to scan visually.

Verb placement: the first word is a verb (`identify`, `trace`, `parse`, `infer`, `locate`, `recognize`, `match`, `derive`, `predict`, `explain`). The remaining three words specify the object and scope.

Each skill name maps to a UID in the form `xxxx-xxxx-xxxx-xxxx`. The name is for humans; the UID is for storage and references.

### 3.1 Granularity strategy: extract narrow, cluster later

A common failure mode at extraction time is to pre-emptively generalize — proposing one broad skill (`recognize_collision_handling`) where four narrow ones (`detect_horizontal_wall_collision`, `detect_floor_landing_event`, `detect_ceiling_blockage_check`, `interpret_slope_height_offset`) would be more diagnostic. Always prefer narrow at extraction time. The skill catalog will be reduced and coarsened in a separate clustering pass (see §8), following Didolkar et al.'s coarsening procedure where fine-grained LLM-proposed skills are grouped into broader families by semantic clustering. Extraction is the divergent step; clustering is the convergent step. Conflating them in one prompt loses information.

A useful heuristic: if a skill could be evidenced by exactly one specific line or function in the chunk, it is appropriately narrow. If it would be evidenced by "the whole file," it is too broad.

---

## 4. LLM Prompt: Cart QA Judgment

This prompt is sent to a strong LLM (e.g., Claude) with a single cart attached. The LLM applies the seven criteria from §1 and returns a structured verdict.

```
SYSTEM:
You are a quality reviewer for a PICO-8 cart corpus used to evaluate LLM
code-understanding capabilities. You apply seven inclusion criteria strictly
and return a structured JSON verdict. You are not lenient on borderline
cases — you flag them for human review rather than guessing.

USER:
Apply the seven criteria below to the cart provided. For each criterion,
return one of: "pass", "fail", "borderline", or "unknown" (the last when
the criterion cannot be determined from the cart contents alone, e.g.
license).

The seven criteria:

1. READABLE_IDENTIFIERS. Function and variable names are human-readable
   English words or idiomatic short forms. Single-letter function names
   used pervasively, or deliberately scrambled identifiers, fail.

2. MULTIPLE_GAMEPLAY_SYSTEMS. The cart implements at least three distinct
   gameplay or simulation systems from: movement, enemies/AI, collision,
   particles/effects, scoring/progression, inventory/resources, level/map
   traversal, audio reactivity, UI/menus beyond a title screen.

3. MODERATE_COMPLEXITY. Lua tokens between 500 and 6,000 AND characters
   between 2,000 and 28,000. If the cart's INFO output is not embedded
   in the prompt, return "unknown" for this criterion and note that
   programmatic check is required.

4. NO_HEAVY_MINIFICATION. The cart is not written in compressed style:
   no pervasive same-line statement chaining, no one-character variable
   names beyond loop counters, no aggressive inlining or PICO-8
   shorthand abuse that slows reading.

5. NOT_PREDOMINANTLY_ASSETS. After mentally stripping non-__lua__
   sections, the remaining code is still substantive enough to support
   skill extraction. Pure asset packs with thin Lua wrappers fail.

6. LICENSE_RECORDED. The cart's license is identifiable from the cart
   contents or the surrounding metadata. If the cart has author
   attribution and findable source, the criterion can pass even if the
   license is "all rights reserved" (private use is allowed). A cart
   with no author and no source fails.

7. SUBSTANTIVELY_DISTINCT. The cart is not a near-duplicate of any cart
   already in the corpus. If no existing corpus is provided in this
   prompt, return "unknown" and note that this criterion is checked at
   corpus assembly time, not per-cart.

OVERALL VERDICT RULES:
- All seven "pass" or ("pass" with at most two "unknown" for criteria 3,
  6, or 7 specifically): verdict is "include".
- Any "fail": verdict is "exclude".
- Otherwise: verdict is "borderline".

Return ONLY valid JSON in this schema, no commentary outside the JSON:

{
  "cart_filename": "<as provided>",
  "verdict": "include" | "exclude" | "borderline",
  "criterion_scores": {
    "readable_identifiers": "pass" | "fail" | "borderline" | "unknown",
    "multiple_gameplay_systems": "pass" | "fail" | "borderline" | "unknown",
    "moderate_complexity": "pass" | "fail" | "borderline" | "unknown",
    "no_heavy_minification": "pass" | "fail" | "borderline" | "unknown",
    "not_predominantly_assets": "pass" | "fail" | "borderline" | "unknown",
    "license_recorded": "pass" | "fail" | "borderline" | "unknown",
    "substantively_distinct": "pass" | "fail" | "borderline" | "unknown"
  },
  "notes": "<2-4 sentences explaining the verdict, citing specific
            evidence from the cart>",
  "systems_observed": ["<system name>", ...],
  "approximate_lua_lines": <integer>
}

CART:
<paste the full .p8 file contents here, including all sections>
```

**Sampling parameters when calling the API:** temperature = 0, top_p = 1, max_tokens sized to ~600 (the JSON is short). Run the same cart through the prompt three times if you want to check stability; at temperature 0 with the same prompt, you should get identical output, but minor wording drift in `notes` is acceptable.

---

## 5. LLM Prompt: Skill Extraction from a Code Chunk

This prompt is sent to a strong LLM with one code chunk (per §2). The LLM proposes the skills a reader must exercise to understand the chunk, in the four-word naming convention.

```
SYSTEM:
You extract a list of NAMED SKILLS that a reader must exercise to fully
understand a chunk of PICO-8 Lua code. You are extracting skills FROM
THE READER'S PERSPECTIVE — what cognitive operations the reader performs
on the code — not skills that the code's protagonist character exercises.

Every skill name follows a strict format:

  word_word_word_word

Exactly four words, lower-case, joined by underscores. The first word is
a verb. Examples of valid skill names:

  identify_draw_callback_function
  trace_variable_across_scopes
  detect_collision_response_pattern
  parse_state_machine_logic
  recognize_particle_emission_pattern
  infer_player_input_handling
  locate_initialization_versus_update
  match_function_call_signatures
  predict_loop_termination_condition
  derive_table_indexing_pattern

Skills must be NARROW and CONCRETE. They name a specific cognitive
operation, not a broad topic. "Understand Lua" is too broad. "Read code"
is too broad. "Trace variable across scopes" is the right grain.

USER:
Extract the named skills exercised by a reader of the code chunk below.

How many skills to propose, scaled to chunk size:
- Chunks under 100 lines: propose 3 to 6 skills.
- Chunks between 100 and 400 lines: propose 6 to 12 skills.
- Chunks over 400 lines (typically a whole single-file cart): propose
  10 to 18 skills.
Over-extraction is preferred to under-extraction at this stage; a later
clustering pass merges duplicates. Do NOT pre-emptively generalize. If
four narrow skills could be one broad skill, propose the four narrow ones.

For each skill, provide:
- name: the four-word skill name
- definition: one sentence describing the cognitive operation
- evidence: a specific line or function name from the chunk where the
  skill is exercised
- k_level: the number of distinct cognitive operations the reader must
  combine to apply the skill. NOT the number of lines or functions in
  the code. A pattern that occupies many lines but is recognized in one
  step is k=1; a pattern that occupies few lines but requires composing
  multiple recognitions (e.g., reading bit-packed flags THEN applying
  them to geometry) is k=3.
  - k=1: atomic, single-step recognition.
  - k=2: requires composing two atomic operations.
  - k=3: requires three or more.

Return ONLY valid JSON in this schema:

{
  "chunk_id": "<as provided>",
  "skills": [
    {
      "name": "word_word_word_word",
      "definition": "<one sentence>",
      "evidence": "<line range or function name in the chunk>",
      "k_level": 1 | 2 | 3
    },
    ...
  ],
  "chunk_summary": "<one sentence: what this chunk does, in plain English>"
}

DISCIPLINE CHECKS — before returning:
- Confirm every name is EXACTLY four words separated by underscores. If
  not, rename.
- Confirm the first word of every name is a verb.
- Confirm no two skills are paraphrases of each other. If two are nearly
  identical, merge them. (Sibling concepts at similar abstraction levels
  — e.g., one skill for input-grace-period and one for ground-grace-period
  — are NOT paraphrases; keep both.)
- Confirm each skill has specific evidence from the chunk, not generic
  reasoning. "This function has loops" is not evidence; "lines 142-148
  iterate over collision tiles" is evidence.
- Confirm no skill is too broad to be evidenced by a specific line or
  function. If a skill would be evidenced by "the whole file," it is
  too broad — split it or drop it.
- Confirm k_level reflects cognitive composition, not code size.

CHUNK:
chunk_id: <e.g. "celeste_classic.p8 :: player_update">
source_cart: <e.g. "celeste_classic.p8">
chunk_summary_from_human: <optional, one sentence; leave blank if none>

```lua
<paste 50–400 lines of Lua here, original whitespace preserved>
```
```
```
```
SYSTEM:
You extract a list of NAMED SKILLS that a reader must exercise to fully
understand a chunk of PICO-8 Lua code. You are extracting skills FROM
THE READER'S PERSPECTIVE — what cognitive operations the reader performs
on the code — not skills that the code's protagonist character exercises.

Every skill name follows a strict format:

  word_word_word_word

Exactly four words, lower-case, joined by underscores. The first word is
a verb. Examples of valid skill names:

  identify_draw_callback_function
  trace_variable_across_scopes
  detect_collision_response_pattern
  parse_state_machine_logic
  recognize_particle_emission_pattern
  infer_player_input_handling
  locate_initialization_versus_update
  match_function_call_signatures
  predict_loop_termination_condition
  derive_table_indexing_pattern

Skills must be NARROW and CONCRETE. They name a specific cognitive
operation, not a broad topic. "Understand Lua" is too broad. "Read code"
is too broad. "Trace variable across scopes" is the right grain.

USER:
Extract the named skills exercised by a reader of the code chunk below.

How many skills to propose, scaled to chunk size:
- Chunks under 100 lines: propose 3 to 6 skills.
- Chunks between 100 and 400 lines: propose 6 to 12 skills.
- Chunks over 400 lines (typically a whole single-file cart): propose
  10 to 18 skills.
Over-extraction is preferred to under-extraction at this stage; a later
clustering pass merges duplicates. Do NOT pre-emptively generalize. If
four narrow skills could be one broad skill, propose the four narrow ones.

For each skill, provide:
- name: the four-word skill name
- definition: one sentence describing the cognitive operation
- evidence: a specific line or function name from the chunk where the
  skill is exercised
- k_level: the number of distinct cognitive operations the reader must
  combine to apply the skill. NOT the number of lines or functions in
  the code. A pattern that occupies many lines but is recognized in one
  step is k=1; a pattern that occupies few lines but requires composing
  multiple recognitions (e.g., reading bit-packed flags THEN applying
  them to geometry) is k=3.
  - k=1: atomic, single-step recognition.
  - k=2: requires composing two atomic operations.
  - k=3: requires three or more.

Return ONLY valid JSON in this schema:

{
  "chunk_id": "<as provided>",
  "skills": [
    {
      "name": "word_word_word_word",
      "definition": "<one sentence>",
      "evidence": "<line range or function name in the chunk>",
      "k_level": 1 | 2 | 3
    },
    ...
  ],
  "chunk_summary": "<one sentence: what this chunk does, in plain English>"
}

DISCIPLINE CHECKS — before returning:
- Confirm every name is EXACTLY four words separated by underscores. If
  not, rename.
- Confirm the first word of every name is a verb.
- Confirm no two skills are paraphrases of each other. If two are nearly
  identical, merge them. (Sibling concepts at similar abstraction levels
  — e.g., one skill for input-grace-period and one for ground-grace-period
  — are NOT paraphrases; keep both.)
- Confirm each skill has specific evidence from the chunk, not generic
  reasoning. "This function has loops" is not evidence; "lines 142-148
  iterate over collision tiles" is evidence.
- Confirm no skill is too broad to be evidenced by a specific line or
  function. If a skill would be evidenced by "the whole file," it is
  too broad — split it or drop it.
- Confirm k_level reflects cognitive composition, not code size.

CHUNK:
chunk_id: <e.g. "bootyful_demake.p8 :: whole_cart">
source_cart: <e.g. "bootyful_demake.p8">
chunk_summary_from_human: <optional, one sentence; leave blank if none>

```lua
<paste one logical unit of Lua code: for single-file carts, the entire
 __lua__ section; for multi-file projects, one .lua module file.
 Original whitespace preserved.>
```
```

**Sampling parameters:** temperature = 0.2 (slight non-zero so the model is willing to propose distinct skill names rather than collapsing to one canonical phrasing it has seen before; the discipline checks at the end of the prompt enforce uniformity), top_p = 1, max_tokens ≈ 1500. The output is short but the model needs room to draft and revise skill names before the final JSON.

**After extraction:** the raw extracted skills are merged into the running catalog. Two skills with the same name are the same skill (assign the same UID). Two skills with different names but the same definition are merged manually or by a second clustering pass (this is Didolkar et al.'s coarsening step) — when merged, one name is chosen as canonical and the other becomes an alias.

---

## 6. Operational Notes

### 6.1 Run each prompt in isolation

Per the conventions set in EVAL_FRAMEWORK_DOC.md §11, every QA judgment is independent of every other QA judgment, and every skill extraction is independent of every other skill extraction. For manual review using the chat interface, this means **a new chat per batch of judgments**, not per cart, but the prompt must enumerate all carts/chunks at once and ask the model to score them independently. For automated runs through the API, every call is a fresh conversation by construction.

### 6.2 Audit a sample

For every 25 LLM judgments or extractions, manually review at least 5 (20%). Where you disagree with the LLM, log the disagreement and check whether the prompt or the guideline needs to be revised. This is the same human-spot-check pattern Skill-Mix used for their grader validation.

### 6.3 Version the prompts

The QA prompt above is v0.1; the skill-extraction prompt above is v0.2 (refinements documented in the changelog at top). When you revise either prompt, increment the version and re-run any judgments/extractions whose downstream use is still active. The version of the prompt that produced each record is part of that record's provenance.

---

## 7. Worked Example: Skill Extraction on `Enichan/Pico8Platformer/platformer.lua`

This is the v0.1 dry-run output, retained as a calibration reference. The chunk is a 353-line, 294-LOC single-file PICO-8 platformer engine (MIT-licensed) with gravity, jump buffering, coyote time, slope handling, four-directional tile collision, and a deadzone camera.

**Input header:**

```
chunk_id: enichan_pico8platformer.platformer.lua
source_cart: Enichan/Pico8Platformer
chunk_summary_from_human: A self-contained PICO-8 platformer engine
  sample featuring gravity, jump buffering, coyote time, slope handling,
  four-directional tile collision, and a snap-back camera.
```

**Extracted output (10 skills, distribution: 2 atomic, 5 at k=2, 3 at k=3):**

```json
{
  "chunk_id": "enichan_pico8platformer.platformer.lua",
  "skills": [
    {
      "name": "identify_pico8_callback_functions",
      "definition": "Recognize PICO-8's three reserved entry-point functions _init, _update, and _draw and infer per-frame execution order from their presence.",
      "evidence": "function _init() ~line 12; function _update() ~line 70; function _draw() ~line 340",
      "k_level": 1
    },
    {
      "name": "trace_jump_buffer_logic",
      "definition": "Follow the per-frame counter pattern (jumpframes incremented each frame, reset to 0 on press, compared against jumpbuffer) that lets a press shortly before landing still trigger a jump.",
      "evidence": "jumpframes = min(jumpbuffer+1, jumpframes+1); if jumpframes <= jumpbuffer then jump(player)",
      "k_level": 2
    },
    {
      "name": "recognize_coyote_time_pattern",
      "definition": "Identify the grace-period idiom where a counter (fallingframes) tracks time since leaving the ground so a jump remains legal for a few frames after walking off a ledge.",
      "evidence": "fallingframes = min(jumpgrace+1, fallingframes+1); if player.onground or fallingframes <= jumpgrace then ...",
      "k_level": 2
    },
    {
      "name": "decode_axis_aligned_collision_boxes",
      "definition": "Parse the nested collision.box table (horizontal, floor, ceiling) and understand that the entity maintains three separately-sized boxes used for different collision directions.",
      "evidence": "function updatecollisionbox constructs box.horizontal, box.floor, box.ceiling from size.horizontal and size.vertical",
      "k_level": 2
    },
    {
      "name": "infer_substepped_physics_integration",
      "definition": "Recognize the loop that divides movement into multiple sub-steps based on speed magnitude so fast-moving entities cannot tunnel through tiles in a single frame.",
      "evidence": "local steps=1; if highestspeed>=0.25 then steps=ceil(highestspeed/0.25) end; for i=1,steps do entity.x += speed.x/steps; ...",
      "k_level": 3
    },
    {
      "name": "parse_slope_flag_encoding",
      "definition": "Decode the bit-packed sprite-flag layout where flag 7 marks slope tiles, flag 6 marks reversal, bits 0-2 encode height, and bits 3-5 encode vertical offset.",
      "evidence": "band(flags,128)==128 (slope marker); reversed = band(flags,64)==64; height = (band(flags,7)+1)/tilesize; offset = band(lshr(flags,3),7)/tilesize",
      "k_level": 3
    },
    {
      "name": "interpret_linear_interpolation_application",
      "definition": "Recognize the lerp(v0,v1,t) helper and follow how it is used to compute the height of a slope at the player's fractional x-position within a tile.",
      "evidence": "function lerp at top of file; local slopeheight = lerp(slope.offset, slope.offset+slope.height, alpha)",
      "k_level": 2
    },
    {
      "name": "trace_tile_iterator_closure",
      "definition": "Follow a Lua closure that captures box bounds and returns an iterator yielding one tile record per call, used in for tile in gettiles(...) do.",
      "evidence": "function gettiles returns an inner function() ... end that advances x,y and returns tile records",
      "k_level": 3
    },
    {
      "name": "identify_camera_deadzone_logic",
      "definition": "Recognize the deadzone/snap-back camera pattern: while the player is inside camerasnap bounds the camera follows lazily; when outside, the camera shifts by exactly the overshoot.",
      "evidence": "camerasnap = {left=40, top=16, right=..., bottom=...}; if screenx < camerasnap.left then cam.x += screenx - camerasnap.left elseif ...",
      "k_level": 2
    },
    {
      "name": "match_animation_state_dispatch",
      "definition": "Trace the three-way conditional that selects an animation set (jumping/walking/standing) from the entity's physical state and the per-frame index advancement.",
      "evidence": "function animate: if not entity.onground then setanim(entity,'jumping') elseif entity.speed.x~=0 then setanim(entity,'walking') else setanim(entity,'standing')",
      "k_level": 1
    }
  ],
  "chunk_summary": "A self-contained PICO-8 platformer engine: _init configures player physics constants and collision boxes; _update reads input, applies jump buffering and coyote-time grace, integrates substepped physics with slope-aware tile collision in four directions, and pans a deadzone camera; _draw renders the map and player sprite."
}
```

**Calibration notes from this run:**

- Skill count (10) sits at the upper bound of the recommended range for a 294-LOC chunk. Comfortable.
- The 4-word constraint held without padding on any skill name.
- `trace_jump_buffer_logic` and `recognize_coyote_time_pattern` are sibling concepts (input-grace vs. ground-grace) — kept separate at extraction time, will likely cluster under a shared parent during §8.
- PICO-8-specific skills emerge naturally (`identify_pico8_callback_functions`, `parse_slope_flag_encoding`). Expected and desirable.
- `interpret_linear_interpolation_application` is borderline narrow — evidenced by one helper function. Kept per §3.1's "extract narrow" rule.

---

## 8. Phase 1.5: Skill Catalog Clustering

Between raw skill extraction and downstream task generation, the catalog is **coarsened**. This is not optional — at ~10 skills per chunk × ~5 chunks per cart × ~25 carts, you can expect on the order of 1,000–1,500 raw skill names. Many will be near-duplicates with slightly different phrasings, and many narrow skills cluster into broader families that are more useful for task tagging and for diagnostic grids.

This is the same coarsening step Didolkar et al. used: GPT-4 generated a list of fine-grained skills, then they asked the LLM to group these fine-grained skills into a smaller cluster of more compound, or abstract, skills. Their result was a coarse catalog of a few dozen skills covering thousands of problems.

### 8.1 Clustering procedure

1. **Collect.** Concatenate all extracted skills into one file. Each record retains its raw name, definition, evidence, k_level, and source chunk.
2. **Embed (optional).** For large catalogs, compute sentence embeddings of `name + definition` and run a clustering algorithm (HDBSCAN, agglomerative, k-means with elbow). For catalogs under ~500 raw skills, an LLM-driven grouping pass (next step) suffices alone.
3. **LLM grouping pass.** Send the strong LLM the full list of raw skills and a prompt asking it to propose canonical four-word names for clusters of related skills, with each raw skill assigned to exactly one cluster. Prompt skeleton in §8.3 below.
4. **Manual review.** For every cluster, a human checks: (a) does the canonical name fairly represent the cluster? (b) are any merges incorrect? (c) should any cluster be split?
5. **Persist.** Store both the raw and coarse catalogs. Raw skills become **aliases** of their coarse parent. Both have UIDs.

### 8.2 What "coarse" means in practice

Expect coarsening to reduce the catalog by roughly 5-10×. Examples from our dry-run domain:

| Raw skills (extracted from various chunks) | Coarse parent |
|---|---|
| `detect_horizontal_wall_collision`, `detect_floor_landing_event`, `detect_ceiling_blockage_check` | `detect_aabb_tile_collision` |
| `trace_jump_buffer_logic`, `recognize_coyote_time_pattern`, `interpret_input_buffer_window` | `recognize_grace_period_idiom` |
| `parse_slope_flag_encoding`, `decode_tile_property_flags`, `interpret_sprite_flag_bits` | `decode_bit_packed_flags` |

The raw skills are kept (they carry the evidence) but tasks are tagged with **coarse** skills primarily. Raw skills become useful when you need fine-grained diagnostic information ("the model passed `detect_aabb_tile_collision` overall but failed every `detect_ceiling_blockage_check` instance").

### 8.3 Clustering prompt skeleton

```
SYSTEM:
You are coarsening a catalog of finely-extracted code-reasoning skills
into a smaller catalog of canonical parents. Each canonical parent name
follows the same four-word, verb-first, underscore-joined format as the
raw skills. You assign every raw skill to exactly one canonical parent.
You do not invent new skills; you only group existing ones.

USER:
Below is a catalog of <N> raw skills extracted from a corpus of PICO-8
carts. Each skill has a name, a one-line definition, and an example
evidence line.

Your task:
1. Propose a set of canonical parent skills, in four-word format.
2. Assign each raw skill to exactly one canonical parent.
3. Provide a one-sentence definition for each canonical parent.

Target catalog size: reduce by roughly 5x to 10x. Do not over-collapse
(do not propose one parent that swallows half the catalog); do not
under-collapse (do not preserve raw skills as their own singleton
parents unless genuinely unique).

Return JSON:

{
  "canonical_skills": [
    {
      "name": "word_word_word_word",
      "definition": "<one sentence>",
      "raw_skill_ids": [<list of raw skill UIDs assigned to this parent>]
    },
    ...
  ],
  "unassigned": [<UIDs of raw skills that did not fit any cluster — flag for human review>]
}

RAW CATALOG:
<paste the raw catalog here, one skill per JSON object>
```

**Sampling parameters:** temperature = 0, top_p = 1, max_tokens scaled to catalog size (~3000 for a 200-skill catalog). Coarsening is convergent; randomness hurts.

### 8.4 Where this sits in the overall pipeline

```
QA filter        →  ~25 carts
Skill extraction →  raw catalog (~1000-1500 skills)
Clustering (§8)  →  coarse catalog (~100-200 skills)   ← Phase 1.5, this section
Task generation  →  tasks tagged with coarse skills
Evaluation       →  pass/fail tensor over (model, task, coarse skill)
```

The four grids documented in EVAL_FRAMEWORK_DOC.md §10 are built on the **coarse** catalog by default. Raw skills are available for drill-down.

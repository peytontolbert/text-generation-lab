# Stage8681 Program-State Multimodality Contract

This recovers an important missing abstraction:

> repo = tokenized executable state-space

The 100M maintainer should not treat a codebase as one flat text stream. It should learn aligned views of the same software system:

- source text
- CST / AST
- symbol table
- import/export graph
- dependency graph
- type/signature map
- call graph
- data-flow graph
- control-flow graph
- compiler/intermediate representations
- docs/comments/README
- tests/fixtures/CI
- runtime traces and stack traces
- verifier logs
- git diffs/commits/patch history
- dependency capability cards

This is **program-state multimodality**: each modality is a different observation channel over the same underlying repo state.

## Why This Matters

The current spine already says:

intent/build strategy -> repo graph -> symbol binding -> edit localization -> patch operator -> verifier repair -> bounded decode

Program-state multimodality is the representation layer under that spine.

Without these modalities, the model sees mostly surface strings. With them, the model can learn:

- which symbol a call refers to
- which import exposes a capability
- which tests cover a function
- which dependency version changes an API
- which runtime trace points to which file/symbol
- which patch operator is legal
- whether a generated patch is grounded in repo state

## Modalities To Recover

### 1. Source Text

Purpose:

- bounded edits
- local code style
- small patch arguments

Risk:

- can leak target text
- can dominate structured objectives if not masked

Use:

- decoder only after budget, leakage, route, and loss-mask gates pass

### 2. CST / AST

Purpose:

- syntax structure
- node-local edit targets
- language-aware patch operators

Needed fields:

- node kind
- span
- parent/child edge
- enclosing symbol
- language family

### 3. Symbol Table

Purpose:

- bind names to definitions
- expose imports/exports
- prevent hallucinated symbols

Needed fields:

- symbol id
- symbol kind
- file/module owner
- signature
- visibility/export status
- aliases

### 4. Import / Dependency Graph

Purpose:

- choose allowed imports
- reject blocked imports
- decide build-on-top vs from-scratch
- understand dependency capabilities

Needed fields:

- package name
- version
- exported symbols
- usage patterns
- known errors
- allowed/blocked policy

### 5. Type / Signature Map

Purpose:

- avoid invalid calls
- guide adapter/wrapper construction
- support cross-language equivalence

Needed fields:

- parameter names
- parameter types if available
- return type
- exception/result behavior
- mutability/ownership hints

### 6. Call Graph

Purpose:

- impact radius
- edit localization
- failure-to-symbol binding

Needed fields:

- caller
- callee
- callsite span
- dynamic/unknown call flag

### 7. Data-Flow Graph

Purpose:

- bug propagation
- unsafe value paths
- wrong argument binding
- source/sink tracking

Needed fields:

- value source
- value sink
- argument position
- assignment/return edge

### 8. Control-Flow Graph

Purpose:

- branch/loop edits
- exception paths
- verifier failure diagnosis

Needed fields:

- block id
- branch edge
- exception edge
- terminal condition

### 9. Compiler / IR Modalities

Purpose:

- cross-language semantic compression
- C/Rust/Python runtime behavior clues

Examples:

- Python AST / bytecode hints
- Rust HIR / MIR hints
- LLVM IR hints

Rule:

- IR is one modality, not the source of truth. It can erase names and intent.

### 10. Docs / Comments / README

Purpose:

- design intent
- usage conventions
- public API behavior

Risk:

- stale docs can mislead; must be verifier-checked where possible

### 11. Tests / Fixtures / CI

Purpose:

- behavior specification
- edit validation
- failure-to-repair rows

Needed fields:

- test target
- fixture dependencies
- assertion shape
- expected failure/pass state

### 12. Runtime Traces / Stack Traces

Purpose:

- bind failures to code
- normalize verifier failures
- generate repair state

Needed fields:

- exception type
- failing frame
- source span
- normalized failure class

### 13. Git Diffs / Patch History

Purpose:

- realistic maintenance transformations
- patch operator examples
- regression risk

Needed fields:

- before state
- after state
- changed object
- verifier outcome
- commit/PR metadata when clean and allowed

### 14. Dependency Capability Cards

Purpose:

- portable dependency knowledge
- import/build strategy selection

Example fields:

- package/version
- exports
- common calls
- contracts
- usage examples
- common errors
- platform constraints
- verifier tests

## Mapping To Current Objective Families

- `intent_to_build_strategy`: source text, dependency cards, import policy, repo capability summaries
- `repo_state_graph_v1`: nodes/edges over files, symbols, imports, tests, configs, failures
- `symbol_binding`: symbol table, import graph, call graph, test graph, failure traces
- `edit_localization`: AST/CST, symbol table, call graph, test graph, failure trace
- `patch_operator`: AST/CST, type/signature map, control-flow, data-flow, dependency policy
- `verifier_repair`: tests, runtime traces, CI logs, patch history
- `bounded_decoder_arguments`: localized source spans, operator arguments, target shape
- `output_repair_denoise`: bad output, verifier failure, target surface, clean output

## Required Anti-Cheat Rules

- IDs must be opaque and row-local.
- Objective labels must not appear in graph IDs, node IDs, edge IDs, or visible text.
- Raw source may not be included in structured objectives unless explicitly allowed.
- Target text may not appear in model input.
- Dependency cards must be versioned.
- Locked eval sources must not become training rows.
- Graph degree or node kind alone must not solve the target.
- Query kind alone must not solve binding action.
- Retrieval evidence must beat metadata-only and evidence-removed controls.

## Current Implementation Status

Recovered:

- repo graph node/edge schema
- source inventory lineage
- shared feature normalizer
- symbol-binding seed
- retrieval baselines
- locked eval packs
- leakage/shortcut audits

Missing:

- AST/CST extractor card
- symbol table extractor card
- import/dependency graph extractor card
- type/signature extractor card
- call/data/control-flow extractor cards
- dependency capability card builder
- runtime/stack trace normalizer
- patch-history modality builder
- cross-modal alignment audit
- modality dropout/ablation audit

## Next Best Step

Do not mine general data yet.

First recover executable extractor contracts:

1. AST/CST modality contract
2. symbol table modality contract
3. import/dependency graph modality contract
4. test/failure trace modality contract
5. cross-modal alignment audit

Then feed those into the unified junk/OOD ranker and cluster/slice detector.

All model execution, decoder CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion remain closed.

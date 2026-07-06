# Long-Context Transition Dataset Spec

## Goal

This pipeline builds research datasets for direct long-context state-transition
learning.

The target task is not generic long-context QA. The target task is:

```text
state_t+1 = F(state_t, incoming_context_chunk_t)
```

where the model must update latent state correctly over very large context,
including:

- sparse decisive updates
- contradictions and revisions
- obligations opened and closed far apart
- alias/entity merges across sources
- irrelevant-span resistance

The first implementation target is a runnable pipeline that can emit:

- normalized chunks
- linked entities
- latent transition programs
- rendered long-context examples
- shortcut/quality audits

## Source Roots

Expected roots:

- `/data/repository_library/exports/corpus/papers`
- `/arxiv/repositories`
- `/arxiv/datasets`

Optional roots may be added later.

## Artifacts

Artifacts are written under:

```text
runs/local/artifacts/long_context_transition/
```

Primary outputs:

- `chunks.jsonl`
- `source_inventory.json`
- `entities.jsonl`
- `entity_aliases.json`
- `links.jsonl`
- `links_summary.json`
- `programs.jsonl`
- `examples_*.jsonl`
- `quality_audits.jsonl`

## Quick Start

Single-command pipeline:

```bash
python scripts/build_stage8800_long_context_transition_dataset.py \
  --papers-root /data/repository_library/exports/corpus/papers \
  --repos-root /arxiv/repositories \
  --datasets-root /arxiv/datasets \
  --output-dir runs/local/artifacts/long_context_transition \
  --max-files-per-root 200 \
  --num-programs 5000 \
  --target-context-tokens 100000
```

This emits:

- `chunks.jsonl`
- `source_inventory.json`
- `entities.jsonl`
- `entity_aliases.json`
- `links.jsonl`
- `links_summary.json`
- `programs.jsonl`
- `examples.jsonl`
- `quality_audits.jsonl`
- `examples_accepted.jsonl`

## Normalized Chunk Schema

Each row in `chunks.jsonl` must follow:

```json
{
  "chunk_id": "repo_oneformer_demo_main_py_00001",
  "source_type": "repo",
  "source_id": "OneFormer",
  "doc_id": "demo/main.py",
  "modality": "code",
  "token_count": 412,
  "text": "...",
  "metadata": {
    "path": "demo/main.py",
    "language": "python",
    "section_name": null,
    "title": null,
    "symbol_names": ["main"],
    "imports": ["torch"],
    "method_terms": [],
    "benchmark_terms": [],
    "error_terms": []
  }
}
```

Required fields:

- `chunk_id`
- `source_type`
- `source_id`
- `doc_id`
- `modality`
- `token_count`
- `text`
- `metadata`


## Natural Mining

The miner should discover examples from the full indexed corpus and then measure
their natural closure size. Context length is treated as an observed property of
a mined example, not a top-down requirement.

The initial graph artifacts are:

- `chunks.jsonl`
- `entities.jsonl`
- `links.jsonl`

Candidate mining and evidence-closure expansion should operate over that graph.

## Entity Schema

Each row in `entities.jsonl` must follow:

```json
{
  "entity_id": "ent_streaming_update",
  "entity_type": "capability",
  "canonical_name": "streaming update",
  "aliases": ["online update", "incremental update"],
  "mentions": ["paper_foo_0001", "repo_bar_0007"],
  "source_type_counts": {
    "paper": 1,
    "repo": 1
  }
}
```

## Program Schema

Programs encode latent state transitions over chunk arrivals.

```json
{
  "program_id": "prog_000001",
  "template_family": "claim_revision",
  "state_variables": [
    {"name": "claim_valid", "type": "bool"}
  ],
  "initial_state": {
    "claim_valid": false
  },
  "transitions": [
    {
      "transition_id": "t1",
      "trigger_chunk_id": "paper_x_0001",
      "kind": "claim",
      "effects": {"claim_valid": true}
    },
    {
      "transition_id": "t2",
      "trigger_chunk_id": "trace_y_0004",
      "kind": "revision",
      "effects": {"claim_valid": false}
    }
  ]
}
```

## Example Schema

Examples render one latent program into a long context with distractors.

```json
{
  "example_id": "lcx_000001",
  "program_id": "prog_000001",
  "context_length_target": 5000000,
  "rendered_chunk_ids": ["noise_1", "paper_x_0001", "noise_2", "trace_y_0004"],
  "query": {
    "query_family": "final_state",
    "text": "Is the claim still valid after all evidence?"
  },
  "targets": {
    "final_answer": false,
    "final_state": {
      "claim_valid": false
    },
    "supporting_chunk_ids": ["paper_x_0001", "trace_y_0004"]
  },
  "aux_targets": {
    "state_probe_points": [
      {
        "after_chunk_id": "paper_x_0001",
        "state": {
          "claim_valid": true
        }
      }
    ]
  }
}
```

## Quality Audit Schema

Each example audit row must include:

```json
{
  "example_id": "lcx_000001",
  "single_chunk_pass": false,
  "last_chunk_pass": false,
  "lexical_topk_pass": false,
  "counterfactual_flip_pass": true,
  "state_order_sensitive": true,
  "accepted": true
}
```

## Template Families

The first implementation supports:

- `claim_revision`
- `rule_exception`
- `alias_merge`
- `obligation_chain`
- `paper_repo_benchmark`

The first runnable version may implement only a subset, but all programs must
declare `template_family`.

## Acceptance Criteria

An example is accepted only if:

- it contains at least two transitions
- no single transition chunk trivially determines the full answer
- removing a critical transition changes the answer or state
- relevant transition order matters when the template requires it

## Research Metrics

Dataset construction metrics:

- chunk counts by source type
- entity counts by type
- program counts by template family
- accepted example rate
- rejection reasons by audit

Model metrics:

- final-state accuracy
- state-probe accuracy
- contradiction-resolution accuracy
- retention accuracy vs transition distance
- failure rate by template family

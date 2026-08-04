# RecurrentGemma Maintainer Integration

## Decision

Use `google/recurrentgemma-2b-it` as a separate decoder-only sidecar. Do not
replace the recovered 100M encoder-decoder, reuse its 1506-token tokenizer, or
write RecurrentGemma outputs into artifacts labeled as Gemma-3 12B.

The implementation is
`legacy_src/agentkernel_lite/modeling_recurrent_gemma.py`. It exposes raw causal
vocabulary logits and adds the existing software-maintainer structured heads on
the final valid causal token.

## System Placement

```text
retrieval + repo graph + verifier state
-> 100M structured controller
-> deterministic decode gate
-> RecurrentGemma bounded candidate sidecar
-> parser / typecheck / tests / security checks
-> rank, repair, accept, or abstain
```

RecurrentGemma fits three roles:

1. Bounded candidate decoder after the controller authorizes generation.
2. Frozen pretrained backbone for structured-maintainer head experiments.
3. Teacher for distilling accepted policy distributions and candidates into the
   100M student.

It must not decide its own execution authority or count toward a standalone
100M result.

## Why This Boundary

RecurrentGemma is a causal decoder with its own 256k-token vocabulary and chat
template. The current student is a 1506-token encoder-decoder with cross-attention
and explicit structured policy heads. Loading RecurrentGemma weights into that
class is not shape-compatible and would erase the meaning of existing checkpoints.

The sidecar boundary also preserves benchmark identity. Existing comparisons use
Ollama `gemma3:12b`; RecurrentGemma-2B-IT is a different architecture, scale, and
checkpoint. Its output paths and score names must say `recurrentgemma2b`.

## Loading

Checkpoint loading is lazy and never occurs during import:

```python
import json
from pathlib import Path

import torch

from legacy_src.agentkernel_lite import (
    RecurrentGemmaMaintainerConfig,
    RecurrentGemmaMaintainerModel,
)

payload = json.loads(
    Path("configs/model/recurrentgemma_2b_it_maintainer.json").read_text()
)
config = RecurrentGemmaMaintainerConfig.from_json(payload)
model = RecurrentGemmaMaintainerModel.from_pretrained(
    config,
    dtype=torch.bfloat16,
    device_map={"": "cuda:2"},
    local_files_only=True,
)
```

Remove `local_files_only=True` only after the Gemma license is accepted, the exact
revision is pinned, enough disk is reserved, and a download is explicitly
authorized. Never let `device_map="auto"` place this model on GPUs used by active
training jobs.

## Training Sequence

Start with the backbone frozen and train only structured heads. This provides a
cheap test of whether pretrained causal features help label prediction without
altering public weights. Record base checkpoint revision, tokenizer revision,
head vocabulary hashes, split hashes, and parameter counts in every run card.

If frozen-head results survive root-clustered heldout, counterfactual, and leakage
checks, add parameter-efficient adapters in a separate experiment. Do not default
to full fine-tuning: optimizer state for a roughly 3B-parameter model exceeds the
practical free memory currently available on the host.

For the final 100M product, distill only accepted examples:

```text
same visible evidence packet
+ RecurrentGemma structured distribution or bounded candidate
+ deterministic verifier results
-> keep verified examples
-> quarantine ambiguous or leaking examples
-> train the 100M controller/student
```

## Tokenization And Batching

Use the checkpoint tokenizer and `tokenizer.apply_chat_template` for the IT model.
Do not feed AgentKernel token IDs to RecurrentGemma. Render the existing canonical
`_row_text` surface as user content, tokenize with padding, and pass the resulting
attention mask. The adapter pools the last valid token correctly for both left-
and right-padded batches.

For generation, prefer left padding, deterministic decoding, explicit
`max_new_tokens`, and a stop contract. Structured-label tasks should constrain or
parse against the frozen label vocabulary and treat anything else as abstention,
not silently normalize arbitrary text to a valid label.

## Deployment

Run the sidecar in its own process with a fixed GPU and expose a narrow generation
or scoring API. A separate service prevents its recurrent cache and allocator from
competing with the 100M trainer. The in-process adapter is intended for head
training, offline distillation, and controlled smoke tests.

Current host constraints observed during integration:

- Three RTX 3090 GPUs with 24 GB each.
- Roughly 20 to 21 GB was already allocated on every GPU.
- `/data` had about 41 GB free and was 99 percent full.
- The checkpoint was not already present in the inspected Hugging Face caches.

Do not download or load the public weights until capacity is deliberately freed.

## Verification Contract

Before production use, require:

- exact checkpoint and tokenizer revision pins
- gated-license acceptance and offline cache verification
- one-GPU bf16 load and deterministic generation smoke
- full-sequence versus cached-generation parity
- left/right padding batch parity
- structured-head gradient isolation while frozen
- raw-vocabulary-logit shape checks
- same-manifest comparisons under a new RecurrentGemma-specific identity
- parser, typecheck, test, security, and budget gates on every generated candidate

"""RecurrentGemma backbone adapter for the software-maintainer model stack.

The adapter keeps RecurrentGemma separate from the 100M encoder-decoder. It can
serve as a bounded causal decoder, a frozen feature backbone for structured
heads, or a teacher whose outputs are distilled into the smaller controller.
Loading Transformers and checkpoint weights is intentionally lazy.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any, Mapping

import torch
from torch import nn
import torch.nn.functional as F

from .modeling_transformer import DEFAULT_STRUCTURED_HEAD_DIMS


DEFAULT_RECURRENT_GEMMA_MODEL_ID = "google/recurrentgemma-2b-it"


@dataclass
class RecurrentGemmaMaintainerConfig:
    """Configuration for a pretrained RecurrentGemma maintainer sidecar.

    The instruction-tuned checkpoint is the default because this integration is
    used for prompted bounded decisions and generation. The base checkpoint is
    more appropriate when continuing causal-language-model pretraining.
    """

    model_name_or_path: str = DEFAULT_RECURRENT_GEMMA_MODEL_ID
    structured_head_dims: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_STRUCTURED_HEAD_DIMS)
    )
    freeze_backbone: bool = True
    classifier_dropout: float = 0.0
    require_recurrent_gemma: bool = True

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "RecurrentGemmaMaintainerConfig":
        """Build a runtime config from the checked-in model contract."""

        model = payload.get("model") if isinstance(payload.get("model"), Mapping) else payload
        heads = payload.get("structured_head_dims")
        return cls(
            model_name_or_path=str(
                model.get("name_or_path", DEFAULT_RECURRENT_GEMMA_MODEL_ID)
            ),
            structured_head_dims=(
                {str(name): int(size) for name, size in heads.items()}
                if isinstance(heads, Mapping)
                else dict(DEFAULT_STRUCTURED_HEAD_DIMS)
            ),
            freeze_backbone=bool(model.get("freeze_backbone", True)),
            classifier_dropout=float(model.get("classifier_dropout", 0.0) or 0.0),
            require_recurrent_gemma=bool(model.get("require_recurrent_gemma", True)),
        )


def pool_last_valid_token(
    hidden_states: torch.Tensor,
    attention_mask: torch.Tensor | None,
) -> torch.Tensor:
    """Pool the final non-padding token for left- or right-padded batches.

    RecurrentGemma is causal, so a final-token representation contains the
    preceding prompt context. A masked mean would mix early, less contextualized
    positions and is therefore a poorer default for maintainer policy heads.
    """

    if hidden_states.ndim != 3:
        raise ValueError("hidden_states must have shape [batch, sequence, hidden]")
    batch_size, sequence_length, hidden_size = hidden_states.shape
    if sequence_length == 0:
        raise ValueError("cannot pool an empty sequence")
    if attention_mask is None:
        return hidden_states[:, -1, :]
    if attention_mask.ndim != 2 or attention_mask.shape[0] != batch_size:
        raise ValueError("attention_mask must have shape [batch, sequence]")
    if attention_mask.shape[1] < sequence_length:
        raise ValueError("attention_mask cannot be shorter than hidden_states")

    # Cached decoding can return hidden states only for the newest tokens while
    # the attention mask still describes the complete prefix.
    mask = attention_mask[:, -sequence_length:].to(
        device=hidden_states.device,
        dtype=torch.bool,
    )
    if not bool(mask.any(dim=1).all()):
        raise ValueError("every sequence must contain at least one valid token")
    positions = torch.arange(sequence_length, device=hidden_states.device)
    positions = positions.unsqueeze(0).expand(batch_size, -1)
    last_positions = positions.masked_fill(~mask, -1).max(dim=1).values
    gather_index = last_positions.view(batch_size, 1, 1).expand(-1, 1, hidden_size)
    return hidden_states.gather(dim=1, index=gather_index).squeeze(1)


class RecurrentGemmaMaintainerModel(nn.Module):
    """Add maintainer policy heads to a Hugging Face RecurrentGemma causal LM.

    The wrapped backbone continues to return raw vocabulary logits. Structured
    heads consume the final valid token and never authorize an action directly;
    deterministic gates and verifiers remain outside this module.
    """

    def __init__(
        self,
        backbone: nn.Module,
        config: RecurrentGemmaMaintainerConfig | None = None,
    ) -> None:
        """Attach structured heads to an already constructed causal LM."""

        super().__init__()
        self.config = config or RecurrentGemmaMaintainerConfig()
        self.backbone = backbone
        backbone_config = getattr(backbone, "config", None)
        model_type = str(getattr(backbone_config, "model_type", ""))
        if self.config.require_recurrent_gemma and model_type != "recurrent_gemma":
            raise ValueError(
                "expected a RecurrentGemma backbone with model_type='recurrent_gemma', "
                f"received {model_type!r}"
            )
        hidden_size = int(getattr(backbone_config, "hidden_size", 0) or 0)
        if hidden_size <= 0:
            raise ValueError("backbone.config.hidden_size must be a positive integer")

        self.classifier_dropout = (
            nn.Dropout(self.config.classifier_dropout)
            if self.config.classifier_dropout > 0.0
            else nn.Identity()
        )
        self.structured_heads = nn.ModuleDict(
            {
                name: nn.Linear(hidden_size, int(output_size))
                for name, output_size in self.config.structured_head_dims.items()
            }
        )
        self._reset_structured_heads()
        self.set_backbone_trainable(not self.config.freeze_backbone)

    @classmethod
    def from_pretrained(
        cls,
        config: RecurrentGemmaMaintainerConfig | None = None,
        **pretrained_kwargs: Any,
    ) -> "RecurrentGemmaMaintainerModel":
        """Load public weights through Transformers without importing it eagerly.

        Callers should pass deployment choices such as ``device_map``, ``dtype``,
        and ``local_files_only`` explicitly. This prevents an import or unit test
        from unexpectedly downloading a multi-gigabyte gated checkpoint.
        """

        runtime_config = config or RecurrentGemmaMaintainerConfig()
        try:
            from transformers import AutoModelForCausalLM
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError(
                "Transformers with RecurrentGemma support is required to load weights"
            ) from exc
        pretrained_kwargs.setdefault("trust_remote_code", False)
        backbone = AutoModelForCausalLM.from_pretrained(
            runtime_config.model_name_or_path,
            **pretrained_kwargs,
        )
        return cls(backbone=backbone, config=runtime_config)

    def _reset_structured_heads(self) -> None:
        """Initialize newly added task heads without altering public weights."""

        for head in self.structured_heads.values():
            nn.init.normal_(head.weight, mean=0.0, std=0.02)
            if head.bias is not None:
                nn.init.zeros_(head.bias)

    def set_backbone_trainable(self, trainable: bool) -> None:
        """Freeze or unfreeze all backbone parameters as one explicit policy."""

        self.config.freeze_backbone = not trainable
        self.backbone.requires_grad_(trainable)
        if not trainable:
            self.backbone.eval()

    def train(self, mode: bool = True) -> "RecurrentGemmaMaintainerModel":
        """Keep a frozen backbone deterministic while task heads train."""

        super().train(mode)
        if self.config.freeze_backbone:
            self.backbone.eval()
        return self

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        labels: torch.Tensor | None = None,
        *,
        position_ids: torch.Tensor | None = None,
        past_key_values: Any | None = None,
        use_cache: bool = False,
        **backbone_kwargs: Any,
    ) -> dict[str, Any]:
        """Return causal vocabulary logits plus structured maintainer logits."""

        gradient_context = torch.no_grad() if self.config.freeze_backbone else nullcontext()
        with gradient_context:
            outputs = self.backbone(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
                position_ids=position_ids,
                past_key_values=past_key_values,
                use_cache=use_cache,
                output_hidden_states=True,
                return_dict=True,
                **backbone_kwargs,
            )
        hidden_states = outputs.hidden_states[-1]
        pooled = pool_last_valid_token(hidden_states, attention_mask)
        task_features = self.classifier_dropout(pooled)
        result = {
            "decoder_logits": outputs.logits,
            "structured_logits": {
                name: head(task_features) for name, head in self.structured_heads.items()
            },
            "pooled": pooled,
            "past_key_values": getattr(outputs, "past_key_values", None),
        }
        lm_loss = getattr(outputs, "loss", None)
        if lm_loss is not None:
            result["decoder_loss"] = lm_loss
        return result

    def structured_loss(
        self,
        structured_logits: Mapping[str, torch.Tensor],
        targets: Mapping[str, torch.Tensor],
        *,
        ignore_index: int = -100,
    ) -> torch.Tensor:
        """Average cross-entropy over structured fields with active targets."""

        losses: list[torch.Tensor] = []
        for name, target in targets.items():
            if name not in structured_logits:
                raise KeyError(f"missing structured logits for field {name!r}")
            active = target.ne(ignore_index)
            if bool(active.any()):
                losses.append(F.cross_entropy(structured_logits[name][active], target[active]))
        if losses:
            return torch.stack(losses).mean()
        anchor = next(iter(structured_logits.values()), None)
        if anchor is None:
            raise ValueError("structured_logits cannot be empty")
        return anchor.sum() * 0.0

    def parameter_summary(self) -> dict[str, int]:
        """Report total and trainable parameters for run-card provenance."""

        parameters = list(self.parameters())
        return {
            "total": sum(parameter.numel() for parameter in parameters),
            "trainable": sum(
                parameter.numel() for parameter in parameters if parameter.requires_grad
            ),
            "backbone": sum(parameter.numel() for parameter in self.backbone.parameters()),
            "structured_heads": sum(
                parameter.numel() for parameter in self.structured_heads.parameters()
            ),
        }

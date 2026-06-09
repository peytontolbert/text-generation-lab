import importlib.util
from pathlib import Path


def _load_train_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "legacy_src" / "scripts" / "train_agentkernel_lite_encdec.py"
    spec = importlib.util.spec_from_file_location("train_agentkernel_lite_encdec", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _TinyTokenizer:
    pad_token_id = 0
    eos_token_id = 2
    vocab_size = 128

    def __init__(self):
        self._ids: dict[str, int] = {"<pad>": 0, "<s>": 1, "</s>": 2}
        self._pieces: dict[int, str] = {0: "<pad>", 1: "<s>", 2: "</s>"}

    def __len__(self):
        return self.vocab_size

    def _id(self, piece: str) -> int:
        if piece not in self._ids:
            token_id = len(self._ids) + 1
            self._ids[piece] = token_id
            self._pieces[token_id] = piece
        return self._ids[piece]

    def __call__(
        self,
        text,
        *,
        max_length: int,
        padding="max_length",
        truncation=True,
        add_special_tokens=True,
    ):
        pieces = str(text or "").split()
        ids = [self._id(piece) for piece in pieces]
        if add_special_tokens:
            ids = [1, *ids, 2]
        if truncation:
            ids = ids[:max_length]
        mask = [1] * len(ids)
        if padding == "max_length":
            while len(ids) < max_length:
                ids.append(self.pad_token_id)
                mask.append(0)
        return {"input_ids": ids, "attention_mask": mask}

    def decode(self, ids):
        return " ".join(self._pieces.get(int(token_id), "") for token_id in ids)


def test_retrieval_structured_key_text_uses_primary_key():
    module = _load_train_module()

    text = (
        "<AK_OP_ENTITY_CONTEXT> op=entity_context domain=domain_003 "
        "entity=entity_003_003 bind_key=entity_context|domain_003|entity_003_003"
    )

    assert module._retrieval_structured_key_text(text) == (
        "op=entity_context bind_key=entity_context|domain_003|entity_003_003"
    )


def test_encode_encdec_row_emits_structured_key_tokens():
    module = _load_train_module()
    tokenizer = _TinyTokenizer()
    row = {
        "encoder_text": "query",
        "decoder_text": "answer",
        "retrieval_query_text": (
            "<AK_OP_ENTITY_CONTEXT> op=entity_context domain=domain_003 "
            "entity=entity_003_003 bind_key=entity_context|domain_003|entity_003_003"
        ),
        "retrieval_doc_text": (
            "<AK_OP_ENTITY_CONTEXT> entity_context_card domain=domain_003 entity=entity_003_003"
        ),
        "operation": "entity_context",
    }

    encoded = module._encode_encdec_row(
        row,
        tokenizer=tokenizer,
        max_encoder_tokens=16,
        max_decoder_tokens=16,
        max_retrieval_query_tokens=16,
        max_retrieval_doc_tokens=16,
        max_retrieval_negatives=0,
        pad_token_id=tokenizer.pad_token_id,
        decoder_start_token_id=1,
    )

    assert encoded["retrieval_pair_mask"].item() is True
    assert encoded["retrieval_structured_key_attention_mask"].sum().item() > 0
    key_text = tokenizer.decode(encoded["retrieval_structured_key_ids"].tolist())
    assert "op=entity_context" in key_text
    assert "bind_key=entity_context|domain_003|entity_003_003" in key_text

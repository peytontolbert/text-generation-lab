# Stage9042 Long Context Corpus Index Guard Audit

Passed: `True`

This stage preserves the long-context Parquet corpus-index utilities as guarded infrastructure only.
Production corpus scans, `/arxiv` writes, Hugging Face uploads, mining, model execution, decoder CE, and training remain closed.

Required CLI guards:

- `--allow-corpus-scan`
- `--allow-arxiv-output`
- `validate_corpus_index_request`
- `CorpusIndexSafetyError`
- `FORBIDDEN_CORPUS_ROOTS`

Next: Keep corpus indexing closed. If needed, design a separate active corpus-root ticket before scanning /arxiv, repository_library, writing Parquet under /arxiv, or uploading to Hugging Face.


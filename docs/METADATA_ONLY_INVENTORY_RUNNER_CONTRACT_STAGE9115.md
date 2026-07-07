# Stage9115 Metadata-Only Inventory Runner Contract

Passed: `True`

Designs the future runner contract. This stage does not execute the runner or access `/arxiv`.

Required CLI flags:

- `--datasets-root`
- `--repositories-root`
- `--output-dir`
- `--max-depth`
- `--metadata-only`
- `--no-row-reads`
- `--no-source-body-reads`
- `--no-arxiv-writes`
- `--no-follow-symlinks`
- `--require-ticket-audit`

Required runtime assertions:

- `datasets_root_is_arxiv_datasets`
- `repositories_root_is_arxiv_repositories`
- `output_dir_under_runs_local_artifacts`
- `metadata_only_flag_required`
- `row_reads_disabled`
- `source_body_reads_disabled`
- `parquet_group_reads_disabled`
- `arxiv_write_disabled`
- `symlink_follow_disabled`
- `max_depth_enforced`
- `ticket_audit_summary_passed`

Next: Audit the metadata-only inventory runner contract with negative cases before implementing or executing it.

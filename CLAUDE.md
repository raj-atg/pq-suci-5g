# pq-suci-5g: project conventions

Research prototype: post-quantum (ML-KEM) SUCI on Open5GS + UERANSIM. See README.md and docs/.

## Hard rules
- NO EM DASHES (U+2014) anywhere: code, comments, docs, commit messages, plot labels, file names.
  Use commas, colons, parentheses or plain hyphens. Enforced by `scripts/hooks/pre-commit`,
  `scripts/hooks/commit-msg` (enable with `git config core.hooksPath scripts/hooks`) and a
  Claude Code PostToolUse hook in `.claude/settings.json`.
- Never invent numbers. Every number in docs must come from a file under `results/`.
- Do not state specific 3GPP/GSMA post-quantum standardization status unless verified.
- Keys in `config/keys/` are TEST ONLY.

## Code style
- Python 3.11+, type hints, docstrings, small functions, no dead code. `ruff check` and
  `ruff format` must be clean. Tests with `pytest`.
- Shell: `set -euo pipefail`, idempotent, shellcheck clean.
- Commits: conventional (`feat:`, `fix:`, `docs:`, `exp:`, `chore:`). Never force push.

## Layout
- `src/pqsuci/`: crypto package (kdf, ecies, kem_suci, suci_format, schemes, cli).
- `experiments/`: e1..e6 runners; raw output to `results/raw/`, CSV to `results/processed/`.
- `third_party/`: upstream clones and local installs (gitignored). Patches in `patches/`.
- Protection scheme IDs: 0 null, 1 Profile A, 2 Profile B, 12 ML-KEM-768, 13 X25519+ML-KEM-768.

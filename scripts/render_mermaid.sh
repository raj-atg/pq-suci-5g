#!/usr/bin/env bash
# Render the Mermaid diagrams in docs/ to PNG and PDF in results/figures/, for use outside
# GitHub (Word, PDF, slides). The Markdown files stay the only source: each diagram is cut out
# of its ```mermaid block, saved as .mmd next to the images, and rendered with mermaid-cli.
#
# Needs Node.js (npx). mermaid-cli runs a headless Chromium, which on Ubuntu needs
# libnss3, libnspr4 and libasound2t64. Without sudo, unpack them into a folder
# (apt-get download + dpkg -x) and point MERMAID_LIB_DIR at its usr/lib/x86_64-linux-gnu.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/results/figures"
MMDC_VERSION="11.4.2"

# doc file : n-th mermaid block in that file (1-based) : output name
DIAGRAMS=(
  "docs/09-technical-deep-dive.md:1:fig8_registration_sequence"
  "docs/09-technical-deep-dive.md:2:fig8b_pq_changes"
  "docs/01-5g-architecture.md:1:fig8c_core_architecture"
  "docs/02-suci-explained.md:1:fig8d_registration_overview"
)

if [[ -n "${MERMAID_LIB_DIR:-}" ]]; then
  export LD_LIBRARY_PATH="$MERMAID_LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

for entry in "${DIAGRAMS[@]}"; do
  IFS=: read -r doc n name <<<"$entry"
  awk -v want="$n" '
    /^```mermaid/ { k++; inside = (k == want); next }
    inside && /^```/ { exit }
    inside { print }
  ' "$ROOT/$doc" >"$OUT/$name.mmd"
  if [[ ! -s "$OUT/$name.mmd" ]]; then
    echo "render_mermaid: block $n not found in $doc" >&2
    exit 1
  fi
  for fmt in png pdf; do
    npx -y "@mermaid-js/mermaid-cli@$MMDC_VERSION" -q \
      -i "$OUT/$name.mmd" -o "$OUT/$name.$fmt" -b white -s 3 --pdfFit
  done
  echo "rendered $name (from $doc)"
done

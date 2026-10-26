#!/usr/bin/env bash
# Create patched copies of Open5GS and UERANSIM (git worktrees of the pinned tags), apply
# patches/*.patch and build them. The stock builds are left untouched. Idempotent.
#   third_party/open5gs-pq  -> third_party/install/open5gs-pq
#   third_party/UERANSIM-pq -> third_party/UERANSIM-pq/build
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TP="$ROOT/third_party"
LOGS="$ROOT/build/logs"
OQS="$TP/install/liboqs"
mkdir -p "$LOGS"
export PKG_CONFIG_PATH="$OQS/lib/pkgconfig:${PKG_CONFIG_PATH:-}"

[[ -f "$OQS/lib/liboqs.so" ]] || { echo "liboqs missing, run scripts/build_all.sh first" >&2; exit 1; }

worktree_with_patch() {  # upstream_dir worktree_dir patch_file
  local up="$1" wt="$2" patch="$3"
  if [[ ! -d "$wt" ]]; then
    git -C "$up" worktree add --detach "$wt" HEAD >/dev/null
  fi
  if git -C "$wt" apply --reverse --check "$patch" 2>/dev/null; then
    echo "already applied: $(basename "$patch")"
  else
    git -C "$wt" apply "$patch"
    echo "applied: $(basename "$patch")"
  fi
}

worktree_with_patch "$TP/open5gs" "$TP/open5gs-pq" "$ROOT/patches/open5gs-v2.8.0-pq-suci.patch"
worktree_with_patch "$TP/UERANSIM" "$TP/UERANSIM-pq" "$ROOT/patches/ueransim-v3.3.0-pq-suci.patch"

# Open5GS (patched)
cd "$TP/open5gs-pq"
[[ -d build ]] || meson setup build --prefix="$TP/install/open5gs-pq" >"$LOGS/open5gs-pq-setup.log"
ninja -C build -j3 >"$LOGS/open5gs-pq.log"
ninja -C build install >>"$LOGS/open5gs-pq.log"

# UERANSIM (patched)
cd "$TP/UERANSIM-pq"
cmake -S . -B cmake-build-release -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  >"$LOGS/ueransim-pq-cmake.log"
cmake --build cmake-build-release -j3 >"$LOGS/ueransim-pq.log"
mkdir -p build
cp -f cmake-build-release/nr-gnb cmake-build-release/nr-ue cmake-build-release/nr-cli build/
echo "patched builds ready: $TP/install/open5gs-pq/bin, $TP/UERANSIM-pq/build"

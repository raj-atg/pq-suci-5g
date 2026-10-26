#!/usr/bin/env bash
# Build liboqs, Open5GS and UERANSIM from pinned tags into third_party/. Idempotent.
# Usage: scripts/build_all.sh [liboqs] [open5gs] [ueransim]   (default: all, sequentially)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TP="$ROOT/third_party"
INSTALL="$TP/install"
LOGS="$ROOT/build/logs"
JOBS=3
mkdir -p "$TP" "$INSTALL" "$LOGS"

LIBOQS_TAG=0.16.0
OPEN5GS_TAG=v2.8.0
UERANSIM_TAG=v3.3.0

clone() { # url tag dir
  if [[ -d "$3/.git" ]]; then
    echo "clone: $3 exists, skipping"
  else
    git clone --depth 1 --branch "$2" "$1" "$3"
  fi
}

build_liboqs() {
  if [[ -e "$INSTALL/liboqs/lib/liboqs.so" ]]; then
    echo "liboqs: already installed, skipping"
    return
  fi
  clone https://github.com/open-quantum-safe/liboqs.git "$LIBOQS_TAG" "$TP/liboqs"
  {
    cmake -S "$TP/liboqs" -B "$TP/liboqs/build" -G Ninja \
      -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DOQS_DIST_BUILD=ON \
      -DCMAKE_INSTALL_PREFIX="$INSTALL/liboqs"
    ninja -C "$TP/liboqs/build" -j"$JOBS"
    ninja -C "$TP/liboqs/build" install
  } 2>&1 | tee "$LOGS/liboqs.log"
}

build_open5gs() {
  if [[ -x "$INSTALL/open5gs/bin/open5gs-udmd" ]]; then
    echo "open5gs: already installed, skipping"
    return
  fi
  clone https://github.com/open5gs/open5gs.git "$OPEN5GS_TAG" "$TP/open5gs"
  {
    if [[ ! -d "$TP/open5gs/build" ]]; then
      (cd "$TP/open5gs" && meson setup build --prefix="$INSTALL/open5gs")
    fi
    ninja -C "$TP/open5gs/build" -j"$JOBS"
    ninja -C "$TP/open5gs/build" install
  } 2>&1 | tee "$LOGS/open5gs.log"
}

build_ueransim() {
  if [[ -x "$TP/UERANSIM/build/nr-ue" && -x "$TP/UERANSIM/build/nr-gnb" && -x "$TP/UERANSIM/build/nr-cli" ]]; then
    echo "ueransim: already built, skipping"
    return
  fi
  clone https://github.com/aligungr/UERANSIM.git "$UERANSIM_TAG" "$TP/UERANSIM"
  {
    cd "$TP/UERANSIM"
    CMAKE_BUILD_PARALLEL_LEVEL="$JOBS" make -j"$JOBS"
  } 2>&1 | tee "$LOGS/ueransim.log"
}

steps=("$@")
[[ ${#steps[@]} -eq 0 ]] && steps=(liboqs open5gs ueransim)
for s in "${steps[@]}"; do
  "build_$s"
done
echo "build_all: done"

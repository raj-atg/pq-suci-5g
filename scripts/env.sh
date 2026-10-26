#!/usr/bin/env bash
# Shared paths for the core scripts. Source this file; do not run it.
# shellcheck disable=SC2034
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="$ROOT/runtime"
KEYS="$ROOT/config/keys"
# CORE=stock (default): upstream Open5GS v2.8.0 and UERANSIM v3.3.0.
# CORE=pq: the patched builds from scripts/apply_patches.sh (Profile B on the UE, scheme 12).
CORE="${CORE:-stock}"
if [[ "$CORE" == pq ]]; then
  O5GS_PREFIX="${O5GS_PREFIX:-$ROOT/third_party/install/open5gs-pq}"
  UERANSIM="${UERANSIM:-$ROOT/third_party/UERANSIM-pq/build}"
  CONFIG_SUFFIX="-pq"  # config/open5gs/<nf>-pq.yaml overrides <nf>.yaml when present
else
  O5GS_PREFIX="${O5GS_PREFIX:-$ROOT/third_party/install/open5gs}"
  UERANSIM="${UERANSIM:-$ROOT/third_party/UERANSIM/build}"
  CONFIG_SUFFIX=""
fi
O5GS_SRC="$ROOT/third_party/open5gs"
OQS_INSTALL_PATH="${OQS_INSTALL_PATH:-$ROOT/third_party/install/liboqs}"
export OQS_INSTALL_PATH
NFS=(nrf scp amf smf upf ausf udm udr pcf nssf bsf)
# Library search path for the locally installed Open5GS and liboqs.
export LD_LIBRARY_PATH="$O5GS_PREFIX/lib/x86_64-linux-gnu:$O5GS_PREFIX/lib:$OQS_INSTALL_PATH/lib:${LD_LIBRARY_PATH:-}"

#!/usr/bin/env bash
# Shared paths for the core scripts. Source this file; do not run it.
# shellcheck disable=SC2034
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="$ROOT/runtime"
KEYS="$ROOT/config/keys"
O5GS_PREFIX="${O5GS_PREFIX:-$ROOT/third_party/install/open5gs}"
O5GS_SRC="$ROOT/third_party/open5gs"
UERANSIM="${UERANSIM:-$ROOT/third_party/UERANSIM/build}"
OQS_INSTALL_PATH="${OQS_INSTALL_PATH:-$ROOT/third_party/install/liboqs}"
export OQS_INSTALL_PATH
NFS=(nrf scp amf smf upf ausf udm udr pcf nssf bsf)
# Library search path for the locally installed Open5GS and liboqs.
export LD_LIBRARY_PATH="$O5GS_PREFIX/lib/x86_64-linux-gnu:$O5GS_PREFIX/lib:$OQS_INSTALL_PATH/lib:${LD_LIBRARY_PATH:-}"

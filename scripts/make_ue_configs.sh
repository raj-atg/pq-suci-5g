#!/usr/bin/env bash
# Render the UERANSIM UE configs from config/ueransim/ue-template.yaml and the TEST keys.
set -euo pipefail
# shellcheck source=scripts/env.sh
source "$(dirname "$0")/env.sh"

render() {  # name scheme key_id pubkey_hex
  sed -e "s|@SCHEME@|$2|" -e "s|@KEYID@|$3|" -e "s|@PUBKEY@|$4|" \
    "$ROOT/config/ueransim/ue-template.yaml" > "$ROOT/config/ueransim/$1.yaml"
}
# The null scheme ignores the key, but stock UERANSIM requires a 64-hex-digit value.
render ue-null 0 0 "$(cat "$KEYS/profile-a-1.pub.hex")"
render ue-profileA 1 1 "$(cat "$KEYS/profile-a-1.pub.hex")"
render ue-profileB 2 2 "$(cat "$KEYS/profile-b-2.pub.hex")"
render ue-pq 12 3 "$(cat "$KEYS/mlkem768-3.pub.hex")"
echo "UE configs written to config/ueransim/"

#!/usr/bin/env bash
# Add test subscribers (UERANSIM sample credentials) with Open5GS's dbctl. Idempotent:
# IMSIs that already exist are skipped.
# Usage: add_subscribers.sh [COUNT]   (default 120: IMSI 999700000000001 .. 999700000000120)
set -euo pipefail
# shellcheck source=scripts/env.sh
source "$(dirname "$0")/env.sh"

COUNT="${1:-120}"
KI=465B5CE8B199B49FAA5F0A2EE238A6BC
OPC=E8ED289DEBA952E4283B54E88E6183CA
DBCTL="$O5GS_SRC/misc/db/open5gs-dbctl"

missing_imsis() {
  local existing imsi i
  existing="$(mongosh --quiet mongodb://localhost/open5gs \
    --eval 'db.subscribers.find({}, {imsi: 1, _id: 0}).toArray().map(d => d.imsi).join("\n")')"
  for i in $(seq 1 "$COUNT"); do
    imsi="$(printf '9997%011d' "$i")"
    grep -qx "$imsi" <<<"$existing" || echo "$imsi"
  done
}

# dbctl uses a 2 s server selection timeout, which can expire on a loaded laptop, so retry.
for pass in 1 2 3; do
  mapfile -t missing < <(missing_imsis)
  echo "pass $pass: ${#missing[@]} subscribers to add (of $COUNT)"
  [[ ${#missing[@]} -eq 0 ]] && break
  printf '%s\n' "${missing[@]}" | xargs -P 4 -I{} "$DBCTL" add {} "$KI" "$OPC" >/dev/null || true
done
mongosh --quiet mongodb://localhost/open5gs --eval 'print("total subscribers: " + db.subscribers.countDocuments())'

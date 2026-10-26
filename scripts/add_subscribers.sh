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

existing="$(mongosh --quiet mongodb://localhost/open5gs \
  --eval 'db.subscribers.find({}, {imsi: 1, _id: 0}).toArray().map(d => d.imsi).join("\n")')"

missing=()
for i in $(seq 1 "$COUNT"); do
  imsi="$(printf '9997%011d' "$i")"
  grep -qx "$imsi" <<<"$existing" || missing+=("$imsi")
done
echo "subscribers: ${#missing[@]} to add (of $COUNT)"
if [[ ${#missing[@]} -gt 0 ]]; then
  printf '%s\n' "${missing[@]}" | xargs -P 4 -I{} "$DBCTL" add {} "$KI" "$OPC" >/dev/null
fi
mongosh --quiet mongodb://localhost/open5gs --eval 'print("total subscribers: " + db.subscribers.countDocuments())'

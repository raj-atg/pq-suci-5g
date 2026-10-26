#!/usr/bin/env bash
# Install system dependencies (approved in P0, see docs/decisions.md). Idempotent.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
APT_PKGS=(
  build-essential cmake ninja-build meson flex bison pkg-config git
  libsctp-dev lksctp-tools libgnutls28-dev libgcrypt20-dev libssl-dev libidn-dev
  libmongoc-dev libbson-dev libyaml-dev libnghttp2-dev libmicrohttpd-dev
  libcurl4-gnutls-dev libtins-dev libtalloc-dev
  python3-venv python3-dev tshark sysstat shellcheck gh nodejs npm
  iproute2 iputils-ping gnupg curl
)

echo "wireshark-common wireshark-common/install-setuid boolean false" | sudo debconf-set-selections
sudo apt-get update -qq
sudo apt-get install -y -qq "${APT_PKGS[@]}"

# MongoDB 9.0 from the official repository for this Ubuntu release.
MONGO_KEY=/usr/share/keyrings/mongodb-server-9.gpg
MONGO_LIST=/etc/apt/sources.list.d/mongodb-org-9.0.list
CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
if [[ ! -s "$MONGO_KEY" ]]; then
  curl -fsSL https://pgp.mongodb.com/server-9.asc | sudo gpg --batch --yes --dearmor -o "$MONGO_KEY"
fi
if [[ ! -f "$MONGO_LIST" ]]; then
  echo "deb [ arch=amd64,arm64 signed-by=$MONGO_KEY ] https://repo.mongodb.org/apt/ubuntu ${CODENAME}/mongodb-org/9.0 multiverse" \
    | sudo tee "$MONGO_LIST" >/dev/null
  sudo apt-get update -qq
fi
sudo apt-get install -y -qq mongodb-org

# uv (user-local)
if ! command -v uv >/dev/null && [[ ! -x "$HOME/.local/bin/uv" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo "setup_deps: done"

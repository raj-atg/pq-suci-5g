# 04. Setup and reproduction

## Requirements

- Linux x86-64 (Ubuntu 26.04 tested; WSL2 or native).
- SCTP kernel module, `/dev/net/tun`, `sudo`.
- About 10 GB of disk, at least 4 GB of RAM, internet access for the first build.

## Install

Native Ubuntu and WSL2 use the same steps.

```bash
git clone https://github.com/raj-atg/pq-suci-5g.git
cd pq-suci-5g
sudo modprobe sctp     # load SCTP (needed by the gNB to AMF link)
make setup             # scripts/setup_deps.sh, then creates .venv with uv
make build             # scripts/build_all.sh, then scripts/apply_patches.sh
make keys              # scripts/gen_test_keys.sh, scripts/make_ue_configs.sh
make test
```

What each step does:

- `make setup` installs apt packages (compilers, SCTP, MongoDB 9.0 from MongoDB's official repository, tshark) and uv, then installs the `pqsuci` package into `.venv`.
- `make build` builds liboqs, Open5GS v2.8.0 and UERANSIM v3.3.0 into `third_party/`, then makes patched copies (`third_party/open5gs-pq`, `third_party/UERANSIM-pq`). Versions are in [versions.md](versions.md).
- `make keys` creates TEST ONLY home network keys and the UE configs `config/ueransim/ue-*.yaml`.

WSL2 notes:

- The WSL kernel must provide SCTP. If `sudo modprobe sctp` fails, see the SCTP entry under common errors.
- systemd is not required. `scripts/start_core.sh` starts MongoDB itself.
- Keep the repository in the Linux filesystem (for example `~/pq-suci-5g`), not under `/mnt/c`. Builds there are slow.

## Running the core

Start the core and add subscribers:

```bash
make core-up          # MongoDB plus NRF, SCP, AMF, SMF, UPF, AUSF, UDM, UDR, PCF, NSSF, BSF
make subscribers      # 120 test subscribers, IMSI 999700000000001 to 999700000000120
```

Register one UE (starts a capture, a gNB and a UE, waits for the PDU session, then pings):

```bash
experiments/run_registration.sh -c config/ueransim/ue-profileA.yaml -o /tmp/demo -p
```

Other UE configs: `ue-null.yaml`, `ue-profileB.yaml`, `ue-pq.yaml`. Options: `-n N` for N UEs, `-t` for the timeout in seconds. Output: `/tmp/demo.pcap`, `.ue.log`, `.gnb.log`, `.ping.log`, `.status`.

With `-p`, the UE tunnel is placed in its own network namespace and the script runs `ping -I uesimtun0 10.45.0.1` inside it. Do this by hand with:

```bash
sudo ip netns list
sudo ip netns exec <namespace> ping -I uesimtun0 -c 3 10.45.0.1
```

Stop everything:

```bash
make core-down
```

## Where things are

| What | Where |
|---|---|
| NF logs | `runtime/log/<nf>.stdout` and the Open5GS log files in `runtime/log` |
| MongoDB log and data | `runtime/log/mongod.log`, `runtime/db/` |
| Rendered NF configs | `runtime/open5gs/*.yaml` (from `config/open5gs/`) |
| PID files | `runtime/pid/` |
| Captures | the `-o` prefix you gave to `run_registration.sh` (`.pcap`) |
| Build logs | `build/logs/` |

Open a `.pcap` in Wireshark to see NGAP and SBI messages. `make clean-runtime` removes `runtime/`.

## Cleaning up the host

`make clean-host` stops the core and runs `scripts/cleanup_host.sh` (needs sudo). It removes the
policy routing rules that UERANSIM adds for every UE tunnel and never removes (after the full
experiment set there were over a thousand), the `ogstun` interface, and `/etc/iproute2/` if it
only holds the distro default `rt_tables` plus UERANSIM's entries. The `ogstun` interface also
disappears when WSL restarts.

## Common errors and fixes

| Problem | Cause and fix |
|---|---|
| MongoDB repository key fails to download | The key URL is `https://pgp.mongodb.com/server-9.asc` for MongoDB 9.0. `scripts/setup_deps.sh` uses it. |
| `mongosh` server selection timeout during `open5gs-dbctl` | dbctl uses a 2 second timeout that can expire under load. `scripts/add_subscribers.sh` retries. Run `make subscribers` again if it still fails. |
| UERANSIM: `homeNetworkPublicKey is too small` with the null scheme | Stock UERANSIM requires a 64-hex-digit key even for scheme 0. `scripts/make_ue_configs.sh` puts the Profile A public key in `ue-null.yaml`. |
| UE tunnel setup fails: `/etc/iproute2/rt_tables` missing | Ubuntu 26.04 only ships `/usr/share/iproute2/rt_tables`. Run `sudo mkdir -p /etc/iproute2 && sudo cp /usr/share/iproute2/rt_tables /etc/iproute2/` (decision D8 in [decisions.md](decisions.md)). |
| tshark cannot write the capture file | Run as root, tshark cannot open files in the home directory. `run_registration.sh` writes the capture to stdout and redirects it as your user. |
| `ping 10.45.0.1` from the normal shell fails or never uses GTP-U | On a single host the UPF owns 10.45.0.1, so the ping is local. Use the UE namespace (`-p`, see above). |
| `liboqs-python` prints text to stdout on import | `src/pqsuci/_oqs.py` filters it so CLI output stays clean. |
| SCTP module missing | Run `sudo modprobe sctp`, then `lsmod \| grep sctp`. On WSL2 the kernel must be built with SCTP. If it is not, install a WSL kernel that has it. |

## Environment checks

Recorded during P0 (2026-10-26):

| Check | Command | Result |
|---|---|---|
| Passwordless sudo | `sudo -n true` | OK (temporary rule, removed at the end of the task) |
| Location | `pwd` | `~/pq-suci-5g` (Linux filesystem, not `/mnt/c`) |
| SCTP | `sudo modprobe sctp; lsmod \| grep sctp` | module `sctp` loaded; `SCTP` and `SCTPv6` in `/proc/net/protocols` |
| TUN | `ls -l /dev/net/tun` | present (`crw-rw-rw- 10, 200`) |
| Internet | `curl -sI https://github.com` | `HTTP/2 200` |
| Disk | `df -h ~` | 955 GB free |
| OS | `/etc/os-release` | Ubuntu 26.04.1 LTS (resolute), kernel 6.18.54.1-microsoft-standard-WSL2 |
| Init | `ps -p 1 -o comm=` | systemd (not relied on, see decisions D3) |
| Hardware | `nproc`, `free -h`, `lscpu` | 4 vCPU, 3.7 GiB RAM, Intel Core i3-1005G1 @ 1.20 GHz |

MongoDB repository check: `repo.mongodb.org` has an official `resolute` repository for MongoDB
9.0 (9.0.4) and 8.0, but not for 8.2. We use 9.0.

Package notes for Ubuntu 26.04: `libmongoc-dev`/`libbson-dev` are version 2.x and provide the
pkg-config name `mongoc2`. Open5GS v2.8.0 accepts this (`lib/dbi/meson.build` falls back from
`libmongoc-1.0` to `mongoc2`). The system Python is 3.14.

## Build workarounds

None were needed. `scripts/build_all.sh` builds liboqs 0.16.0, Open5GS v2.8.0 and UERANSIM v3.3.0
unmodified with gcc 15.2.0 and cmake 4.2.3 (no build errors; UERANSIM's `cmake_minimum_required(VERSION 3.17)`
is accepted by cmake 4.2). Open5GS finds libmongoc through the `mongoc2` pkg-config fallback.
Builds use at most 3 parallel jobs. Logs: `build/logs/{liboqs,open5gs,ueransim}.log`.
Run a single step with `scripts/build_all.sh open5gs` (steps: liboqs, open5gs, ueransim).

Install locations: Open5GS binaries in `third_party/install/open5gs/bin/`, default configs in
`third_party/install/open5gs/etc/open5gs/*.yaml`, DB tool at `third_party/open5gs/misc/db/open5gs-dbctl`.
UERANSIM binaries in `third_party/UERANSIM/build/` (nr-gnb, nr-ue, nr-cli, nr-binder, libdevbnd.so).

# 04. Setup and reproduction

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
| Init | `ps -p 1 -o comm=` | systemd (not relied on, see decisions D4) |
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

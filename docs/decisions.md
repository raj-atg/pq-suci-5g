# Decisions log

Short entries: context, decision, reason.

## D1. Install set (P0)
- Context: Ubuntu 26.04.1 (resolute) on WSL2 with nothing preinstalled for building.
- Decision: the user approved one batch: build toolchain, Open5GS libraries, tshark, sysstat,
  shellcheck, gh, nodejs/npm (for mermaid-cli), MongoDB 9.0 from the official resolute repo, uv.
- Reason: MongoDB 9.0.4 is the newest stable line and has an official repository for this
  release, so no fallback repository or container was needed.

## D2. Windows figures folder
- Decision: `<Windows Documents folder>` (`<Windows Documents folder>`).
  The export copies only and never deletes.

## D3. Publishing
- Decision: private GitHub repository `pq-suci-5g`, pushed after each milestone tag.

## D4. No systemd dependency
- Context: systemd is PID 1 in this WSL instance, but this is not guaranteed elsewhere.
- Decision: start mongod (`--fork`, local dbpath) and every Open5GS NF from our own scripts.
- Reason: reproducible on any WSL setup.

## D5. Parallel build jobs
- Context: 4 CPUs, 3.7 GiB RAM.
- Decision: use `-j3` for C/C++ builds and build the projects one after another.
- Reason: avoid running out of memory (UERANSIM C++ units are heavy).

## D6. Git identity
- Context: no global git identity was configured.
- Decision: repo-local `user.name=raj`, `user.email` = the account email. Hooks enabled with
  `git config core.hooksPath scripts/hooks`.

## D7. Subagents and hooks created mid-session
- Context: `.claude/agents/*.md` and `.claude/settings.json` hooks are read when a Claude Code
  session starts, so files created during this session were not active yet (a live test of the
  denylist hook with a harmless dummy did not block). The hook scripts themselves were tested by
  piping JSON into them: every denylist pattern blocked, safe commands passed.
- Decision: run each subagent brief through the built-in general-purpose agent pinned to the
  Sonnet model, with an instruction to follow the matching `.claude/agents/<name>.md` file.
- Reason: same model and same rules without restarting the session.

## D8. Profile B on the UE side (user decision)
- Context: UERANSIM v3.3.0 implements only the null scheme and Profile A
  (`src/ue/nas/mm/identity.cpp`, `generateSuci()`: other schemes log "not implemented").
- Decision (asked the user): Tier 1 runs null and Profile A on stock code. Profile B is added to
  UERANSIM by our own patch (OpenSSL P-256), kept in `patches/` next to scheme 12, then used for
  the interop check, E3 and E4.
- Reason: keeps Profile B as a real-core baseline while making clear it relies on our patch.

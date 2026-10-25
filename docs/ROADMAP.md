# Roadmap

What comes next, in order. Tick a box when it lands on main (with the
release it came in). Sizes compare to one of the four hardening
milestones of October (conn.py, keepalive.py, fair uploads, password
checks): **L** is about one of them, **M** about half.

Smaller things noticed along the way go in [TODO.md](TODO.md).

## 1. Cleanup review (M)

Clear out what's stale before building on it. **No change in
behaviour**: the full suite stays green and the golden outputs stay
identical throughout.

- [x] Dead code: functions nothing calls, unused imports, config keys
      nothing reads; HF-002 (the awaiting-slot upload) removed
- [x] Duplicates: escaping and URL encoding in one place (webtext.py,
      two drifted copies were bugs); every JSON save whole or not at all
      (store.py: a dozen wrote in place)
- [x] barkeep.py split: one handler per route; /admin in admin_web.py,
      loaded on first use
- [x] Provisioner: reviewed (no dead menus); the firmware zip is named
      with its release (`Stump-1.0.0-beta.35.zip`)
- [x] i18n: keys nothing uses (12 removed)
- [x] Docs: the root copies (CLIENT_QUICKSTART, HIDDEN_FEATURES, REF)
      point to final_firmware/docs
- [x] Docs: changelog, README (mpy-cross), engineering notes (the code's
      layout)
- [x] Tests: reviewed, none checking the same thing twice
- [x] The board gets its modules compiled (.mpy): 1,429 KB of source
      sent as 589 KB, nothing compiled at boot
- [x] On LaBuche (1.0.0-beta.35, compiled): ~450 KB of modules on the
      board (was ~1.4 MB of source), 7,467,280 bytes free after start,
      ~10 s from the crypto line to serving (the baseline from here)

Done in 1.0.0-beta.35.

## 2. Chain hardening and interoperability (L)

Make the chain a solid base for everything built on it (chain storage,
NomadNet over the chain).

- [x] A chain protocol version (2) in the beacon, `/node.json` and
      `/chain.json`; older and newer Stumps keep working, `/admin` says
      which to update
- [x] Capabilities in the beacon: release, access mode, radio, storage,
      plugins (the groundwork for chain storage)
- [x] No `TX failed` warning for a chain link with nobody on it
- [x] Only a good hello keeps a Stump in (a packet used to); refusals
      shown in `/chain.json` and `/admin`
- [x] Everyone in `#wifi-mesh` listed on every Stump, quiet people too
- [x] Recovery when a Stump in the middle restarts or the chain secret
      changes (pc_three_stumps); its Wi-Fi lost: chain_failover,
      pc_parent_moves
- [x] Nothing lost and nothing doubled across hops: messages, DMs,
      names (pc_three_stumps)
- [x] Mixed chains: a computer first and a CAM below (pc_chain), a CAM
      first and a computer below (pc_joins_cam), a Stump in the middle
      (pc_three_stumps, a computer with two networks)
- [ ] On the bench: a CAM in the middle of a real chain
- [x] The path matrix across 1, 2 and 3 Stumps: DM to DM, room to room,
      client to Stump, visitors, and the paths that must not exist
      (identity_matrix, pc_two_stumps, pc_three_stumps)

## 3. Pentest hardening (L)

From the attacker's side, after the cleanup (less code to review).

- [x] Every route's input: sizes, encodings, paths (`..`, odd names),
      JSON depth (web_fuzz; bodies that aren't UTF-8 fixed)
- [x] Auth and sessions: cookies, `/hello` replay, constant-time
      compares; lockouts are per Stump (THREAT_MODEL.md)
- [x] The chain as a way in: forged beacons ignored, profiles marked
      with the secret, the parent's answer signed (chain_proto)
- [x] LoRa: floods, malformed packets, a fuzzer on urns' parsers
      (urns_fuzz; msgpack depth and LXMF shape fixed)
- [x] Plugins and packs: hash checks, what an update can overwrite (a
      pack can't replace the core or a built-in plugin)
- [x] A short threat model: docs/THREAT_MODEL.md

Done in 1.0.0-beta.37.

## 4. Enhancements (after 1-3)

- [ ] Storage layer (M-L): one place for SD, the board's flash, none,
      and the chain; storage profiles in features.py; files stored on a
      chain Stump that has room (needs 2)
- [ ] NomadNet pack (L): shelved for now
- [ ] Browser flasher back (M), as one page saved on the computer: from
      file://, Chrome and Edge allow Web Serial with no certificate
      (checked: serial-check.html, macOS Chrome 156). The CAM only
      (MicroPython is MIT, like the Stump; RNode is GPL-3, the Heltec
      stays with the Provisioner). final_firmware/docs/FLASHER.md
  - [x] Stump-Flasher-<release>.html: MicroPython 1.28, the Stump
        compiled, a setup form (name, admin password, home Wi-Fi, the
        Heltec), or an update that keeps the settings
        (scripts/build_flasher.py; tests/flasher_test.py)
  - [x] Built by CI (an artifact) and attached to each release
  - [x] One page for the Provisioner's board jobs too: Settings (read,
        change, save -- by the firmware's settings.py, as /admin; a
        copy kept, one put back) and Check (restart, listen, sum up)
  - [ ] The SD card: Tools, packs, wipe (slow over USB: say so)
  - [ ] On the bench: a CAM made with it, then one updated
  - [ ] Windows: serial-check.html, then the flasher
  - [x] MicroPython's SHA-256 pinned in build_flasher.py (as micropython.org served it to CI)
  - [ ] Offered from the Stump: the Tools page (/sd/tools/flasher/),
        for a visitor's laptop to download and open
- [ ] More boards (M each): one Provisioner profile per board (flash,
      PSRAM, radio, SD pins)

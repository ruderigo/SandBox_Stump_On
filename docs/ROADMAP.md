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

- [ ] Dead code: functions nothing calls, fallbacks for paths that no
      longer exist, config keys nothing reads (HF-002, the awaiting-slot
      upload, removed)
- [ ] Duplicates: the same helper written more than once (time and
      ticks, escaping, JSON answers, settings lookups)
- [ ] barkeep.py split into smaller modules (pages, routes, admin)
- [ ] Provisioner: menus and paths left from older flows
- [x] i18n: keys nothing uses (12 removed)
- [ ] Docs: behaviour that changed; the two CLIENT_QUICKSTART copies
      made from one source
- [ ] Tests: ones that check the same thing twice
- [ ] RAM and flash on the CAM measured before and after

## 2. Chain hardening and interoperability (L)

Make the chain a solid base for everything built on it (chain storage,
NomadNet over the chain).

- [ ] A chain protocol version in the beacon and `/node.json`, and what
      a Stump does with an older or newer neighbour
- [ ] One capabilities message per Stump: storage, radio, access mode,
      plugins (the groundwork for chain storage)
- [ ] Recovery when a Stump in the middle restarts, loses its Wi-Fi, or
      the chain secret changes
- [ ] Nothing lost and nothing doubled across hops: messages, DMs,
      `[NAMES]`
- [ ] Mixed chains: CAM and computer Stumps, in every order
- [ ] The path matrix across 1, 2 and 3 Stumps: DM to DM, room to room,
      client to Stump, visitors, and the paths that must not exist

## 3. Pentest hardening (L)

From the attacker's side, after the cleanup (less code to review).

- [ ] Every route's input: sizes, encodings, paths (`..`, odd names),
      JSON depth
- [ ] Auth and sessions: cookies, `/hello` replay, `/auth` timing,
      admin lockouts across a chain
- [ ] The chain as a way in: a fake Stump on the chain Wi-Fi, forged
      beacons, the chain secret
- [ ] LoRa: floods, oversized resources, malformed packets, a fuzzer on
      urns' parsers
- [ ] Plugins and packs: hash checks, what an update can overwrite
- [ ] A short threat model (docs), shared with the pentesters and the
      client teams

## 4. Enhancements (after 1-3)

- [ ] Storage layer (M-L): one place for SD, the board's flash, none,
      and the chain; storage profiles in features.py; files stored on a
      chain Stump that has room (needs 2)
- [ ] NomadNet pack (L): browse NomadNet nodes from the Stump's web
      pages, and serve the Stump as a NomadNet node; a plugin page can
      be a navigation button
- [ ] Browser flasher back (M): HF-001 in HIDDEN_FEATURES.md, linked
      from /tools again; its catalog kept in step with the Provisioner's
      firmware; images that may be shipped (RNode is GPL-3: its source
      offer comes with it); WebSerial needs HTTPS or a Chrome flag
- [ ] More boards (M each): one Provisioner profile per board (flash,
      PSRAM, radio, SD pins)

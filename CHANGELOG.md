# Changelog

## 1.0.0-beta.2 — 2026-10-13
- **Chained Stumps over Wi-Fi** (`docs/CHAIN.md`): each Stump serves its
  own Wi-Fi on its own range (`192.168.<n>.1`) and joins the one before
  it; they relay Reticulum for each other, so files cross the chain over
  Wi-Fi. A chain secret keeps visitors out (HMAC hellos). PCs join with
  a plain UDP interface (`scripts/chain_hello.py` with a secret). The
  Provisioner asks about the chain, and whether the Stump has a Heltec
  at all. `/admin` → Stump chain, `GET /chain.json`.
- **Big transfers stay off LoRa:** a Stump relays at most 48 KB of file
  data per link every 10 minutes onto a radio interface.
- **UDP interfaces drain their socket** in batches instead of one packet
  per 10 ms with a full garbage collection each (which capped them at
  well under 100 packets a second).
- Tests: a three-Stump chain on loopback (with an intruder and two PCs),
  the radio cap, chain settings.
- **Faster relaying**, measured on a CAM first (`bench/`): file and
  channel packets inside a link the Stump carries are forwarded from
  their raw bytes, without building a Packet or hashing it (the general
  path took 6.8 ms a packet); a packet's hash is computed once, not
  twice; per-packet debug strings are only built when they'll be
  printed; HMAC pads are XORed in C instead of byte by byte (~1.3 ms
  saved per HMAC: link encryption, HKDF, propagation stamps).
  `tests/mp/relay_fastpath.py` checks the fast path forwards exactly
  what the general path does.
- `bench/`: relay, profiling and Wi-Fi benchmarks for chaining Stumps.
- The release zip also carries `docs/RELEASE.md`, the public signing
  key and `scripts/sign_release.py`, to check a release offline.
- **Client docs** (`CLIENT_QUICKSTART.md`): what changed for clients
  since beta.1, chained Stumps' addresses (use the gateway, not a fixed
  `192.168.4.1`), the `stump.node` beacon's forward compatibility.
- Docs: the field-test checklist and the README's quick start start
  from the release download; the README lists the pack commands.

## 1.0.0-beta.1
First beta-test release from this repository: Stump **Beta A** with
everything since the `beta-a` tag on LaBuche-Stump (Oct 9).

- **Plugin API** (`plugins.py`, `docs/PLUGINS.md`). Plugins register
  commands (`/roll` and `!roll`), gates with an explicit priority (0–19
  reserved for access control), listeners, `on_result` hooks, pages under
  `/p/<plugin>/` with home-page cards, timers, services, their own
  settings, storage folder (`/sd/plugins/<name>/`) and translations —
  instead of patching `rrc.handle_input`. Every callback is guarded,
  timed and rate-limited; mesh replies are capped to keep airtime down.
  `GET /plugins.json` lists what's running.
- **Off switch and safe mode.** `/admin <password> plugin off <name>`
  or `/admin` → Plugins (state, RAM, last error). A plugin that resets
  or hangs the node while starting is switched off at the next boot.
- **stumpid and fservbot moved onto the API.** Every reply is unchanged
  (checked line by line against the previous build), except `/help`,
  which now ends with the symbol key. stumpid's gate runs at priority 10
  and the core asks it about access through the `identity` service
  instead of importing it. Password-taking commands are slash-only.
- **Packs** (`docs/PACKS.md`): plugins plus a theme, a bot persona and
  SD-card files in one download. The Provisioner finds them in `packs/`,
  shows author, licence and every file's hash, refuses incompatible ones,
  warns about calls that would hold the node, and installs them
  (`--install-pack`, `--list-packs`, `--remove-plugin`, `--hash-pack`).
  The core manifest now covers the core only; plugins carry their own
  hashes.
- **Two packs**: *tavern* (`!roll`, `!8ball`, `!slap`, `!seen`, `!quote`,
  `!vote` with a results page, a flood guard, a Tavern theme) and *rnfs*
  (the Reticulum file system installable with no internet from the Tools
  page, a link spotter, `!shelf`).
- **Voice notes** on the web chat and over LoRa: Opus (FireFly's default)
  and Codec 2, recorded in the browser (or the phone's recorder) and
  played back; 15 s, 16 KB at most.
- **LXMF propagation node** (store-and-forward for offline phones),
  switched on from `/admin`, with a test mailbox and "leave a message".
- **HTTPS** with your own certificate (`docs/HTTPS_SETUP.md`), checked by
  the browser before it moves a page there.
- **`/admin` → Radio**: TX power, frequency, bandwidth, SF, CR, sent to
  the Heltec.
- **Home-page branding** from a `home/` folder on the SD card, placed
  above, under or beside the buttons (`docs/HOME_BRANDING.md`).
- **JSON** answers for billboard posts and uploads, `/tools.json`,
  and UTF-8 / Latin-1 file names that survive the trip.
- **Navigation**: icon rows on every page, one card per row on the home
  page, About and Tools mirror the public site, FireFly apps on the node.
- **Fixed**: fservbot's saved dialogues were never reloaded after a
  reboot (plugins started before the SD card was mounted).
- **Tests and releases**: `tests/run.py` (firmware on single-precision
  MicroPython, plugins, packs, Provisioner) on every push; tagged
  releases are tested, built reproducibly, hashed and signed
  (`docs/RELEASE.md`).

# Tests

```
sh scripts/build_micropython.sh ~/micropython-f32       # once, ~1 minute
MICROPYTHON=~/micropython-f32/micropython python3 tests/run.py
```

`build_micropython.sh` builds the MicroPython Unix port at a pinned
commit with **single-precision floats**, like the ESP32-S3: code that
round-trips an exact value through a float passes with doubles and fails
on the board. Each firmware test runs in a fresh copy of
`final_firmware/`, so nothing is written to the source tree.

| Test | |
|---|---|
| `chat_golden`, `access_golden`, `mesh_golden` | Fixed scripts of chat lines (web, access modes and tiers with a real Ed25519 `/auth`, the LoRa bridge); the replies must match `expected/`. These were checked line by line against the build before the plugin API |
| `plugin_api`, `plugin_web` | Every hook, budget and failure rule, with the test plugins in `plugins/` |
| `safe_mode` | Boots after a crash while starting, and while running |
| `fservbot_storage` | Data moved to `/sd/plugins/`, the timer notice |
| `packs_chat`, `packs_web` | The tavern and rnfs packs, chat and pages |
| `relay_fastpath` | The relay fast path forwards exactly what the general path does: every packet type, context, direction and hop count |
| `chain` | Three Stumps chained on loopback addresses (root, middle, end) plus an intruder with the wrong chain secret: the end Stump sends a file to the root through the middle one, which relays it; the intruder is kept out |
| `chain_config` | Chain settings, interface configs, `/chain.json`, the `/admin` section |
| `json_api`, `latin1_names` | JSON answers; accented, Latin-1 and emoji file names |
| `config.py` | The fixed configuration every firmware test runs with (not the repository's own `final_firmware/config.py`, which is a real node's) |
| `provisioner` | CPython: the manifest is current, plugins and packs verify, a pack install and an upload against a simulated board |

Snapshot tests compare normalised output (random nonces and signatures,
clock values and log lines removed). After an intended change:
`python3 tests/run.py --update`, then read the diff of `tests/expected/`
before committing it.

**Changed a firmware file?** The Provisioner checks every file against
its manifest, so rebuild it (and re-hash a plugin you changed):

```
python3 provisioner.py --hash-plugin final_firmware/stumpid     # if you changed a plugin
python3 scripts/update_manifest.py
```

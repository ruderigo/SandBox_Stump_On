# Changelog

## Unreleased
- **macOS: Wi-Fi names and the local network.** macOS hides the names
  of the networks around from the Terminal unless it has Location
  access, and never asks for it: the Wi-Fi picker now lists the networks
  this Mac has joined before instead of nothing. And when macOS stops
  the Terminal reaching the local network ("No route to host", though a
  browser works), the chain check says so and where to allow it
  (Privacy & Security > Local Network: Python). A Stump that doesn't answer on a
  shared Wi-Fi gets "its address may have changed" and `--get-ip`, not
  advice about its own Wi-Fi.
- **Updating a computer Stump notices a new Heltec.** `--pc` on an
  existing Stump used to keep `config.py` without a word and go straight
  to the chain: plugging in a Heltec by USB changed nothing. It now shows
  the settings (name, Heltec, chain), offers a Heltec found on USB
  (keeping everything else), and asks whether to change the rest.
- **The About page says what a Stump is**, in French, English and
  Spanish, as the README now does: its three setups (ESP32-S3-CAM +
  Heltec V3; a macOS/Windows/Linux computer + Heltec V3; a computer
  with no radio, reaching LoRa through a chained Stump), how Stumps
  chain (`#wifi-mesh`, `#lora-mesh`), and who connects (FireFly on
  Android or the R36S/R36MAX handheld, each with its own Heltec V3, and
  any browser).

## 1.0.0-beta.4
- **Chat column you can widen.** Drag the bar between the room list
  and the chat to make room for long names (kept on that device;
  double-click puts it back); a cut-off name shows whole on hover.
  The other Stumps of the chain are grouped at the bottom of the column
  under *Stumps* (*Buches* in French), each with a 🪵.
- **Scroll bars out of sight until used**, on every page: the bar shows
  while something scrolls and fades back right after.
- **#wifi-mesh works when the Stumps start at different times.** A Stump
  knew another one as a Stump only from its beacon, sent at boot and
  then every half hour: the one started second never heard the first's,
  so nothing crossed in #wifi-mesh and a DM to the other Stump landed in
  #lora-mesh. Now a new chain link makes both ends announce themselves right
  away, a Stump is also recognised by what it sends, and anyone reached
  over the chain lands in #wifi-mesh, never #lora-mesh.
- **DMs between people on different Stumps.** People seen in #wifi-mesh
  on another Stump are DM contacts as `rod@LaBuche`; `/msg rod@LaBuche
  ...` reaches rod privately, who answers the same way. A DM to a Stump
  itself shows in that Stump's #wifi-mesh, addressed to it (`@LaBuche ...`).
- **`#wifi-mesh`: the Stumps of a chain talk among themselves, `#lora-mesh`
  stays for LoRa.** (Room names that read the same in every language and name the
  transport, so others can follow.) On a Stump in a chain, the other Stumps are taken
  into `#wifi-mesh` as soon as their beacon is heard over the chain --
  no one has to message them first -- and anyone on any Stump can
  `/join wifi-mesh`. Only chat lines cross between Stumps: each Stump
  sends its own people's lines, shown as `<nick@thatstump>` on the
  others, never relayed twice, without the joins, parts and renames
  that used to arrive glued together on one line (and the doubled
  `<macOS> <macOS> hello`). Mesh users (phones, handhelds) still land
  in the mesh room. Fixed on the way: announces heard in a Stump's
  first seconds were missed by the chat bridge until the next
  re-announce.
- **`#lxmf` is now `#lora-mesh`.** The old name still works (`/join lxmf`,
  `#lxmf text`, `/admin <pw> room lxmf hybrid`, `?room=lxmf`, a saved
  tier); replies use the new one. (Room names are lowercase.)
- **A computer joins the chain without leaving its Wi-Fi.** The first
  Stump of a chain, with a chain secret, also takes chain links on the
  Wi-Fi it joined (`WIFI_SSID`): a computer on that same network (home,
  office) joins at the Stump's address there and keeps its internet.
  The Provisioner asks which way ("On the Wi-Fi it's on now" or "By
  joining the Stump's own Wi-Fi"), a CAM's summary says where computers
  join, and the chain check says when a Stump doesn't take links on that
  network and why. `CHAIN_LAN = False` turns it off; `/chain.json` gains
  `lan_ip`.
- **A computer joining a CAM: the right address.** The wizard says the
  Stump's address is the *Router* in the computer's Wi-Fi details, and
  refuses the computer's own address; the chain check, given its own
  address, says it was checking itself instead of reporting a secret
  mismatch.
- **Joining a CAM from a computer: "Connection refused" explained.**
  The Provisioner now reaches a Stump directly, never through a proxy
  from the system settings (a VPN or filter app can't reach the
  Stump's Wi-Fi). When the Stump's Wi-Fi is up but its web server
  refuses, it waits up to a minute (a CAM still starting), then says
  so: its program has most likely stopped, power-cycle it, and where
  its boot log says why.
- **Which version, at a glance.** The Provisioner's first box says which
  release this folder installs and whether GitHub has newer commits
  ("quit, run git pull, start again"); a firmware folder remembered from
  an earlier run that isn't this download's is pointed out. A CAM's
  *Verify* reads the release back from the board and fails on a
  mismatch ("re-upload the Stump files"), and so does `--diag`.
  `python3 provisioner.py --version [PORT]` prints all of it. On the
  node, the About page and `/admin` show `Stump Beta A · <release>`
  (also in `GET /node.json` and the boot log's first line).

## 1.0.0-beta.3
- **The Provisioner no longer edits your checkout.** A CAM's generated
  `config.py` used to be written into `final_firmware/config.py`, which
  made every later `git pull` refuse ("Your local changes ... would be
  overwritten") and left the old Provisioner running. It's now saved as
  `~/.provisioner/profiles/<node>.config.py`. At start, the Provisioner
  warns if a changed `final_firmware/config.py` would block a pull.
- **The Tools page copy is a question.** In a CAM's section 3: copy the
  Tools page's files (firmware bundle, Provisioner) to the card, ~20-25
  minutes the first time and after each update, since they change with
  it; no keeps the node working the same. The card says so.
- **A CAM's setup asks everything first.** Section 3, *Questions*, asks
  them all (flash or not, the wizard, diagnostics at the end); sections
  4-7 then run by themselves, about 25 minutes, and the Provisioner keeps
  the computer awake meanwhile (macOS, Windows). The route card marks
  each section *you* or *auto*, totals both, and says why it's slow: the
  board takes files at about 1 KB/s on its SD card, and the Tools page's
  ~1 MB is most of it, the first time only.
- **BarKeep is back, as the node's librarian (HF-003).** Visitors ask it
  what's on the node in French, English or Spanish ("do you have a
  movie?", "as-tu un livre sur le jardinage ?") from an *Ask BarKeep*
  drawer on the Files and Billboard pages and `/concierge`, and get the
  matching files (linked), notices and apps; `!find <words>` asks it in
  the chat, on one short line. `librarian.py`: accents folded, filler
  dropped, kinds of file / billboard / apps spotted, the rest matched.
  The Files page sorts and filters (kind pills, as-you-type, Enter asks
  BarKeep); the Billboard searches titles and bodies and sorts; both in
  the browser. `/files.json` and `/billboard.json` take `?q=`, `?cat=`,
  `?sort=`; `/files.json` rows gain `cat` and `mtime`; `POST /chat`
  answers JSON when asked. Notices past 72 hours are no longer shown
  before the next post prunes them.
- **A shorter README (H-09).** From about 2,400 lines to about 1,100:
  each feature is a short reference now, and the bug stories and test
  write-ups it had collected moved, word for word, to
  `docs/ENGINEERING_NOTES.md`. Out-of-date passages fixed on the way
  (the mesh landing room, the LXMF signature warning).
- **HTTPS only where it's needed (H-01).** With a certificate, the chat
  and the other pages now stay on plain HTTP: the chat polls every 2 s,
  and over HTTPS each poll was a new secure handshake for the CAM. Voice
  notes record in a small HTTPS window (`/rrc/rec`) that hands the
  recording back to the chat; `/admin` still moves to HTTPS (a password
  is typed there). The chat opened over HTTPS goes back to HTTP.
  `bench/tls_probe.py`, which `docs/HTTPS_SETUP.md` step 0 runs, is in
  the repo now.
- **Hardening (October 2026 review, H-02 to H-08).**
  - **Forged LXMF messages are dropped.** A message whose signature
    doesn't match its sender never reaches the chat or the propagation
    node's mailbox. Without the native Ed25519 module, signatures used to
    go unchecked *and* the message was marked verified (which could also
    set the clock); now they're always checked. A sender not yet heard
    from (no key to check with) is still taken on an open node, and
    refused in hybrid or mandatory mode.
  - **Speed limits** (`guard.py`): chat lines that reach others, on the
    web and over the mesh, 3 at once then one every 2 s (`CHAT_BURST`,
    `CHAT_EVERY`); 3 billboard posts a minute per visitor
    (`BILLBOARD_POSTS_PER_MIN`, 429 / `rate_limited`); after 5 wrong
    passwords (the `/admin` page, `/admin` in the chat, the fserv bot)
    that visitor waits 30 s, doubling each time, up to 15 min.
  - **Access settings survive a restart:** `/admin … mode` and room
    tiers are saved (`access.json`) and restored; `/admin <password>
    reset-access` goes back to `config.py`.
  - **A room made stricter moves out** whoever no longer qualifies, to
    #main, told why (web: a private message; mesh: `→ #main` and the
    refusal).
  - **Saves are whole or not at all:** the credit ledger is written to a
    temporary file and renamed (a power cut mid-write used to leave an
    unreadable ledger, read as empty: everyone's credits gone); the
    unfinished saves a power cut leaves are removed at start-up.
  - **The Heltec link** is primed before every mesh send, not once per
    cycle.
- **The Provisioner, laid out as a route.** It starts by asking what
  you're setting up (CAM, Heltec for a CAM, Heltec relay, Stump on this
  computer, check or fix), shows the route on a card (numbered sections,
  what each does, what you'll need), then runs one section at a time:
  a header with where you are, everything inside it indented under it,
  the setup questions grouped by topic, and a done / skipped / didn't
  work line at the end of each. It ends on a summary of each section and
  what to keep (addresses, chain secret, next command). "Check or fix
  something" offers the one-off tools without flags. Packs list their
  files only with `--list-packs`; the wizard says whether they match the
  pack's hashes. Fixed: a computer with its Heltec on USB was asked the
  CAM's Heltec-over-Wi-Fi questions.
- **The Provisioner times itself.** Each section says how long it took,
  the summary adds them up, and the route card shows the times measured
  on this computer (the median of its last five runs) instead of a guess.
- **Is the chain linked?** When a computer Stump joins another Stump, the
  `--pc` wizard checks each step before and after it starts: on that
  Stump's network, a Stump answers there, its chain is on, the secrets
  match (a real hello), and once running, the Stump above answers it and
  lists it. Each failure says what to fix. Any time:
  `python3 provisioner.py --check-chain` (this computer's Stump) or
  `--check-chain 192.168.5.1` (a CAM's, from a computer on its Wi-Fi).
- **Wi-Fi names picked from a list.** Wherever the Provisioner wizard
  asks for a Wi-Fi name (the network to join, the Stump a chain member
  joins, the Heltec's network), it lists the networks this computer
  hears, strongest first, with a lock on those that need a password, and
  skips the password for open ones. Typing a name still works at the same
  prompt; with no list (no Wi-Fi, or the system hiding names), it asks as
  before.
- **Stump on a computer** (`docs/PC.md`): Windows, macOS or Linux, the
  same firmware on regular Python 3 -- pages, chat, plugins, packs,
  `/admin`, LXMF, propagation node -- with a Heltec on USB (new
  `RNodeSerialInterface`, sharing the Wi-Fi bridge's RNode code) or over
  Wi-Fi, and chaining with CAM Stumps. `python3 provisioner.py --pc` makes
  its folder (firmware, packs, Tools page, its own venv), runs the wizard
  adapted to a computer, and can start it at login (macOS LaunchAgent,
  Windows scheduled task, Linux user service); running it again updates
  and keeps the settings. `pc/` holds the launcher and the stand-ins for
  MicroPython's modules (crypto from `cryptography`, checked against the
  board's own code). Tested in CI on Windows, macOS and Linux, and on Linux
  with a MicroPython CAM joining it over the chain.
- **`GET /node.json`**: name, LXMF address, version and release,
  hotspot address, chain role and features, without joining the chat
  (asked for by the Android team, for discovering nodes).
- **Tools page in sections:** each tool in its own folder on the SD
  card (`tools/provisioner/`, `flasher/`, `firefly/`, one per pack) with
  its own `README.md`, which gives the section its title and summary and
  folds out on the page. Cards set up before are tidied at boot (files
  moved, not copied). `/tools.json` adds `sections` and each file's
  `section`; `/tool?f=` takes `folder/name`. The rnfs pack's
  `rnfs-INSTALL.txt` is now its section's `README.md`.
- **Theme for everyone from `/admin`:** an admin picks the theme every
  visitor gets (built-in or pack themes), applied at once, saved on the
  board; *As set up* goes back to `config.py`'s. The old theme buttons
  there are now labelled for what they always were: this browser only.
  Applying a theme for everyone drops any browser's own older pick
  (which used to beat the site's theme forever), and pages are sent
  with `Cache-Control: no-cache`, so no browser shows an old copy.
- **Delete tools from `/admin`:** a whole section of the Tools page, or
  single files, off the SD card.
- **`/admin` sessions and Log out:** the login gives a session (cookie)
  and redirects, so Back after Log out shows the password prompt instead
  of the admin page, and nothing in the history can resend the password.
  Admin pages are sent `no-store`. Sessions end after 30 min unused.
- **Order of the buttons from `/admin`:** drag the navigation row and the
  home page tiles into order (arrows on a phone), and hide or show each
  one (a hidden page still answers at its address). Home now comes
  first in the navigation row by default.
- `/admin` → Plugins: one tidy row per plugin (name, state, version and
  RAM, commands), the button beside it, or under it on a phone.
- **Tools page in the reader's language:** each section can have
  `README.fr.md` and `README.es.md` beside its `README.md`; the built-in
  sections (Provisioner, flasher, FireFly apps) and the rnfs pack now
  have all three. `/admin`'s home-section status and HTTPS reason are
  translated too (they were English in every language).
- `--skip-tools` still brings the Tools page's READMEs up to date (a few
  KB, every language, for the sections already on the card, packs'
  included): a translation no longer waits for the slow tools copy.
- **rnfs pack 1.1 — credits:** rnfs is by Afi Hogan (afit21), MIT;
  Reticulum and LXMF, shipped with it, by Mark Qvist. Credited on the
  `/p/rnfs/` page, in the `!rnfs` reply, in its Tools page section
  (summary and a Credits section) and the pack's README, in all three
  languages; `pack.json` has a new `credits` field the Provisioner shows
  before installing. Its shelf list no longer squeezes titles on a phone.
- `/help`'s argument names are translated (`/nick <nom>`, `/join <sala>`).
- Fixed: **`--upload-app` replaced the node's `config.py`** with the one
  in the firmware folder, so an update could change a node's name,
  Wi-Fi, passwords or theme (the theme was what showed). It now keeps
  the node's own; `--replace-config` copies the folder's anyway, and a
  freshly flashed board still gets one.
- Fixed: the Provisioner printed "no tools_payload folder found" on
  every run without a `home/` folder.

## 1.0.0-beta.2
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

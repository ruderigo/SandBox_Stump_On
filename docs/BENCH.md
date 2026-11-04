# Bench checks

What the tests can't settle and the real hardware must: every pending
check, in the order to run them. **The quick wins come first**: one
device, a few minutes, already passing in CI, so they should simply
confirm what was built. The harder ones come after, and the last group
are measurements that inform a decision rather than pass or fail.

Tick a box when it passes on the bench (with the date and release). A
check that fails: note what you saw, and bring the log.

Last sorted: 2026-11-03, for 1.0.0-beta.51.

## 1. Quick wins (one device, minutes)

- [ ] **The release signature** (beta.48). On the Mac, from the
      sandbox's `v1.0.0-beta.48` release, download `SHA256SUMS` and
      `SHA256SUMS.rnsig`, then from the repository folder:
      `python3 scripts/sign_release.py verify SHA256SUMS SHA256SUMS.rnsig RELEASE_SIGNING_KEY.txt`.
      Expected: `GOOD signature on SHA256SUMS by d88b72f6e0deb5991f5a5aed5f3f3cdd`.
- [ ] **Keep the computer awake** (beta.45). Laptop Stump: `/admin` →
      Stump settings → *This computer* → tick, Save. Expected: the group
      says *kept awake*; `stump.log` has `keeping the computer awake
      (caffeinate)`; `pmset -g assertions | grep -i caffeinate` lists it.
      Untick: *may sleep*, and the assertion is gone.
- [ ] **An update restarts the Stump by itself** (beta.46). With the
      laptop Stump running: `git pull`, `python3 provisioner.py --pc`.
      Expected: within ~5 s `stump.log` has `this folder was updated
      (the Provisioner): restarting on the new files`; `/admin` opens and
      the About page shows the new release.
- [ ] **Sleep isn't a hang** (beta.45). Keep-awake off; close the lid
      (or Apple menu → Sleep) for 5 minutes; wake. Expected: `stump.log`
      has `the computer was asleep (N s): not a hang`, no `stopped
      responding`, and `localhost` loads at once.
- [ ] **Arborist: Check** on LaBuche3 (USB). Expected: it restarts the
      board, listens, and sums up the start (release, Wi-Fi, SD card).
- [ ] **Arborist: Settings changed and saved** on LaBuche3: change the
      greeting (harmless), Save, let it restart. Expected: the new
      greeting on the chat, and `/admin` → Stump settings shows it.
- [ ] **Arborist: the SD card, what's on it** (beta.49) on LaBuche3.
      Expected: its size and free space, and a line per folder (shared
      files, Tools page, ...) that matches what `/files` and `/tools` show.
- [ ] **Its address, from the home page** (beta.51-53): on a phone on the
      Stump's Wi-Fi, the home page's *Its address* card. Expected: two
      QR codes behind a FireFly / Columba switch. FireFly's scans as
      `lxmf://<address>?stump=...&key=...` and files it under Stumps at
      once. Columba's (Contacts, add, scan) as `lxma://<address>:<key>`
      and adds a contact at once. The address to copy (the same as
      `/node.json`'s `lxmf`) pastes into Sideband's New conversation.
      On a CAM, time the first opening (two codes made, then kept).
- [x] **Announce now, and the timer** (beta.51): `/admin` → Stump
      settings → *Announcing* → *Announce now*. Expected: the log says
      `[announce] on demand (/admin)`; another Stump or FireFly lists it
      within seconds. Set the timer to 5 minutes, Save: the line under
      it counts to the next one, no restart. *Done 2026-11-03: heard
      almost at once.*
- [ ] **The computer wizard from a file** (beta.48), into a scratch
      folder, start-at-login off:
      `python3 provisioner.py --pc --answers-template > a.json`, set
      `"start this stump automatically when you log in": false`, then
      `python3 provisioner.py --pc ~/StumpTest --answers a.json`.
      Expected: exit 0, nothing asked, no password printed. Delete
      `~/StumpTest` after.

## 2. Two Stumps (the laptop and LaBuche3, both on the same release)

- [ ] **A DM to a Stump stays a DM** (beta.47). From the laptop's chat,
      open LaBuche3 under *Stumps*, write `!help`, then `hello`.
      Expected: BarKeep's answers arrive in that DM thread (the help;
      then how to reach people as `name@LaBuche3`); nothing in either
      Stump's `#wifi-mesh`. Then the other way round.
- [ ] **A restarted Stump is named and listed at once** (beta.43-44).
      With the laptop Stump running, press LaBuche3's reset. Expected:
      within ~45 s the laptop lists LaBuche3 by name (no `mesh-xxxx`).
      Then restart the laptop Stump: LaBuche3 lists it as quickly.
      **Keep LaBuche3's console log across that restart** (Arborist →
      Check, or `mpremote`): it's what the chain-lag question needs.
- [ ] **Arborist sets the radio** on a CAM with a Heltec (beta.42):
      Settings → the radio's fields → Save. Expected: `/admin` → Radio
      shows the values; a line in `#lora-mesh` reaches the other Stump.

- [ ] **Arborist: install a pack** (beta.49): tavern's zip from the
      release, on LaBuche3. Expected: *checked* with its size and time;
      after the restart, `/roll 2d6` answers in chat and the Tavern theme is
      offered in `/admin`. Then rnfs (about 17 minutes): the rnfs section
      on the Tools page.
- [ ] **Arborist: fill the Tools page** (beta.49, 25 to 30 minutes):
      Expected: `/tools` lists the Provisioner, the firmware zip and the
      FireFly handheld app, each with its description.
- [ ] **Arborist: wipe the shared files** (beta.49), on a card with a
      test upload or two. Expected: `/files` empty; the Tools page, the
      chat and the settings unchanged.

## 3. More setup

- [ ] **A CAM in the middle of a real chain**: laptop ← LaBuche3 ←
      a third Stump. Expected: `#wifi-mesh` lines and DMs cross both
      hops; restart the CAM in the middle: both ends list each other
      again within a minute or two.
- [ ] **Windows**: `serial-check.html`, then Arborist (Chrome or Edge),
      on a Windows PC with the CAM on USB. Expected: the port is found;
      Check works; then an update.

## 3b. Other LXMF apps (beta.53): does the Stump answer them?

Each app on a phone, the Stump added from `/address` (or by its
address). Send `!help`, then `hello`, over the Stump's Wi-Fi (TCP to
the laptop Stump) and, where the app has it, over LoRa (an RNode).
Expected each time: BarKeep's help, then the hello in `#lora-mesh`
(or `#main`), and the app shows both as delivered. Note what looks
wrong (the replies are chat-room lines: `<nick> text`, `[DM] ...`).

- [ ] **Sideband** (Wi-Fi, then LoRa)
- [ ] **Columba** (Wi-Fi; LoRa if it has the RNode)
- [ ] **MeshChat** (on the laptop: it finds the Stump by its announce)
- [ ] **NomadNet** (on the laptop, the Conversations tab)
- [ ] **Stamps, off** (the default): in Sideband, Settings → *Require
      stamps*, cost 8. Expected: the Stump's replies no longer arrive
      (Sideband drops them); `/admin` shows nothing new.
- [ ] **Stamps, on, a computer Stump**: `/admin` → Stump settings →
      Announcing → *LXMF stamps*. Expected: replies arrive again,
      a second or two late; `stump.log` says `stamp made ... (cost 8`;
      `/admin`: *Stamps made: 1* and more.
- [ ] **Stamps, on, a CAM**: the same. Expected: replies don't arrive,
      `/admin` names Sideband's user under *Require a stamp too costly
      here*. Then in Sideband mark the Stump as trusted and send once:
      `stump.log` says `ticket from ...`, and replies arrive from then on
      (and after the CAM restarts).
- [ ] **NomadNet pack** on the laptop Stump (`--install-pack`, restart):
      NomadNet on another computer, Network → the Stump's name appears
      within a minute; open it. Expected: the home page, Rooms, a room's
      lines, Billboard, Files. *Identify* (the page menu), say something
      in a room: it shows in the Stump's chat as `nomad-xxxx` or your
      name. Then MeshChat (its NomadNet browser). Then over LoRa.
      Switch it off in `/admin` → Plugins: the pages stop answering.
- [ ] **NomadNet's chat in the Stump's rooms** (same pack): in NomadNet,
      a room's *Chat in NomadNet* link (or Channels → New hub, the
      address from the Stump's *NomadNet* card). Expected: the hub
      named after the Stump, #main with its last lines; say something:
      it shows on the web and in FireFly; answer from FireFly: it shows
      in NomadNet. Then over LoRa. If you have MeshChatX: the same.
- [ ] **Simple pack**: from Sideband, write to the Stump. Expected: the
      first answer ends with the tip; write `simple`: answers become
      sentences ("rod: hi", "maria joined."); `simple off` goes back.
      FireFly: unchanged unless it writes `simple`.
- [ ] **Cost 16 on the laptop Stump**: how long a reply takes (minutes
      expected), and that the chat stays usable meanwhile.

## 4. Measurements (they inform a decision, not pass or fail)

- [ ] **4b. Three phones on HTTPS `/admin` at once** (pentest prep):
      the handshake times on a CAM, and whether the Heltec bridge drops
      (`[bridge]` lines). Decides whether 443 needs a lock.
- [ ] **5. The propagation node's longest step** on a CAM (stamp
      checks): the worst stall in ms (`/admin` shows the loop's lag).
- [ ] **12. The HTTPS bench** (`bench/tls_probe.py`, with the Android
      suite): handshake time and free memory on a CAM, a wrong clock,
      mismatched keys, `/rrc/rec` voice over HTTPS.
- [ ] **A night with keep-awake on**: the laptop Stump chained to
      LaBuche3 for 8 h. Expected: still linked in the morning; note any
      restart lines in `stump.log`.

## Done on the bench

- 2026-10-25: Arborist updated a Stump (1.0.0-beta.38); Settings read.
- Late October (beta.39): Arborist made a new Stump, Chrome on macOS;
  `provisioner.py --pc` set up the Mac.

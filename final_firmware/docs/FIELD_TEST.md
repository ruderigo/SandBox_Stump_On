# Field test — Stump 1.0.0-beta.3 (Beta A)

What's new since the last field test, in the order you'd check it on
site, and what to send back. Items marked **(hardware)** are things the
lab tests could not settle — they need the real board, radio and phones.

## Before you go

- [ ] Download `Stump-1.0.0-beta.3.zip` and `SHA256SUMS` from the
      [release](https://github.com/ruderigo/SandBox_Stump_On/releases),
      check them (`shasum -a 256 -c SHA256SUMS` on a Mac; see
      `docs/RELEASE.md` for the signatures), unzip, and work from that
      folder: the Provisioner, the firmware and `packs/` are all in it.
- [ ] `python3 provisioner.py --upload-app PORT --skip-tools` — the app
      and its two built-in plugins are ~1.7 MB: about 12 minutes over USB.
      It then offers the packs (tavern, rnfs): see section 9.
- [ ] Once, with time to spare: `--upload-app PORT` **without**
      `--skip-tools`, to fill in the technician tools (~1 MB, 15–20
      minutes the first time; later runs skip what's unchanged). The
      rnfs pack's tools are another ~1 MB (~17 minutes the first time).
- [ ] With a card reader, onto the SD card:
  - `tools/firefly/FireFly-Android-0.2.11.apk` (rename `app-debug.apk`)
  - `home/` — your branding, if testing it (see `HOME_BRANDING.md`)
- [ ] `/admin` → Radio: set TX power (e.g. 17 dBm). The page says whether
      it reached the Heltec now or will at its next connection.
- [ ] `/admin` → Propagation node: **Activer** (needs the SD card).

## 1. Boot

- [ ] Boot log shows `[web] serving on port 80` and
      `[web] HTTPS off: no certificate installed` (expected for now).
- [ ] With the propagation node on: `[pn] propagation node on: …`.
- [ ] If radio settings were saved: `[radio] saved settings in use: …`.

## 2. Home page and navigation

- [ ] Home: one card per row — Chat, Billboard, Files, Tools, About —
      icon on the left, name and subtitle beside it.
- [ ] Every other page: a row of five icons (all but the page you're on),
      on **one line, on a phone**. On a laptop, hovering an icon shows
      its name (phones don't show these tooltips; screen readers read
      them).
- [ ] Switch the billboard off in the provisioner: it disappears from
      every row.

## 3. Home branding (if a `home/` folder is on the card)

- [ ] `home.html` replaces the Stump logo and title; the language
      switcher stays on top.
- [ ] `/admin` → **Home page section** names the file in use (or why
      none is used).
- [ ] A complete page (e.g. `the_hearth_kinetic_ascii.html`, alone in
      `home/` under its own name) shows in a frame at the top and
      animates; touching it stokes the fire. **(hardware)** Try a
      `"height"` in `home.json` and say what looks right on a phone.
- [ ] Images, a stylesheet and a font from `/home-file?f=…` all load.
- [ ] In `/admin` → Home page section, try each placement — above, under,
      beside left, beside right — on a **phone** (stacks) and a
      **laptop** (side by side from 760 px), plus a frame height and
      "show it" off and on. Each change shows on reload, no restart.
- [ ] `home.fr.html` / `home.en.html`: switch language, the section
      follows.

## 4. About and Tools

- [ ] About: three tabs — Project (v1), How to Connect, Apps & Handhelds.
- [ ] How to Connect names the **real** Wi-Fi name and shows the node's
      address.
- [ ] Apps: "Download from this Stump" shows version and size.
      **(hardware)** On an Android phone: download the APK over the
      node's Wi-Fi (~50 MB — note how long it takes) and install it.
- [ ] `/admin` → **Theme for everyone**: pick another theme. Every page
      changes at once, on a second phone too; restart the node, it stays.
      *As set up* brings back the Provisioner's choice.
- [ ] `/admin` → **Order of the buttons**: drag one nav button and one
      home tile (arrows on a phone), and **Masquer** one of each, save;
      every page and the home page follow, on a second device too.
      **Afficher** brings them back.
- [ ] `/admin` → **Se déconnecter / Log out**, then the browser's Back
      button: the password prompt, never the admin page.
- [ ] `/admin` → **Tools page**: tick one file and one whole section,
      delete; both are gone from `/tools`.
- [ ] `/tools`: apps first, then a section per tool (Provisioner,
      Browser flasher, rnfs…), each with its summary and a **Read me**
      that folds out. A card set up by beta.2 or older: its loose tools
      were moved into their folders at boot (boot log: `[fserv] tools:
      moved N file(s)`).
- [ ] Files page: upload a file with an accented name (`thé.jpg`) and one
      in another script or with an emoji; both appear under their real
      names.
- [ ] From a laptop on the node's Wi-Fi: `/billboard.json`, `/files.json`
      and `/tools.json` open as data. If FireFly posts or uploads, it
      gets a JSON answer (with the new post's `id`).

## 5. Chat over Wi-Fi and LoRa

- [ ] Room movements read `✓ name` / `✗ name`; DMs read
      `[DM] <author>: text`.
- [ ] FireFly's first message lands it in `#lxmf`, and it receives
      `→ #lxmf` first.
- [ ] Make a room `minted` (in chat: `/admin <password> room vip minted`),
      then from an unverified FireFly: `/join vip` and `#vip hello` are
      both refused with `⊘ #vip minted — …`.

## 6. Voice notes

- [ ] Web chat, in a DM: ♪ opens the phone's recorder; the note arrives
      as `[DM] <you>: ♪ N.N s` with ▶.
      **(hardware)** **iPhone:** what does ♪ offer — a recorder, or only
      a file picker? (This decides what iPhone users need.)
- [ ] ▶ plays notes from FireFly (Opus) and any Codec 2 note.
- [ ] FireFly → web user and web user → FireFly, a short note and a full
      15 s note. **(hardware)** Note how long a 15 s Opus note takes over
      LoRa, and whether chat stalls meanwhile (~1 minute of airtime per
      hop, twice when relayed through the Stump).
- [ ] Two notes within 5 s from one sender: the second gets `⧗ — …`.

## 7. Propagation node

- [ ] FireFly lists the Stump as a propagation node; select it.
- [ ] `/admin` test mailbox: send it a message through the node; it shows
      in `/admin` about 30 s later (the stamp check).
- [ ] `/admin` "leave a message" for FireFly's address; close FireFly,
      reopen, sync: it arrives.
- [ ] A 15 s Opus note left for an offline phone is collected intact.
- [ ] **(hardware)** Note the stamp-check time per message on the CAM,
      and whether the web pages stay responsive while it runs.
- [ ] Chat left at the propagation node for the Stump itself, arriving
      more than 30 minutes late, gets "arrived N min late…" instead of
      being acted on.

## 8. Radio

- [ ] **(hardware)** Signal strength of the Stump's announces in FireFly
      before and after the TX power change (7 → 17 dBm should be ~10 dB).

## 9. Plugins and packs

Before you go: the release folder already has `packs/` next to
`provisioner.py`. Install **tavern** and **rnfs** when the wizard or
`--upload-app` offers them (or afterwards:
`--install-pack PORT packs/tavern-pack`). The wizard then offers the
Tavern theme and "Tavernier" as the bot's name.

- [ ] Boot log: `[plugin] active: fservbot, rnfs, stumpid, tavern`, and
      `[fservbot] active` / `[stumpid] active` as before.
- [ ] fservbot's `!` triggers, and stumpid's `/auth`, `/whoami`,
      `/admin`, `/invite`, answer exactly as before (web and FireFly).
- [ ] `/admin` → **Plugins** lists all four, with the RAM each took.
      Switch tavern off: `!roll` stops answering; on again: it's back.
      `stumpid` has no off button.
- [ ] Tavern: `!roll 2d6`, `!8ball`, `!slap`, `!quote add …`,
      `!seen <someone>`, and a poll (`!vote Pizza? | oui | non`, vote
      from two phones, `!vote close`). The home page has a **La taverne**
      card; its page shows the poll and the quotes.
- [ ] From FireFly: `!roll` and `!vote 1` work over LoRa and answer in
      one line; `/help` ends with one `extras:` line.
- [ ] Six quick lines in 10 s from one phone: `⧗ — …`.
- [ ] rnfs: the Tools page's rnfs section has three wheels,
      `rnfs-install.sh` and `rnfs-install.bat`, and its Read me. Paste
      `rnfs:bagaibqabciqkq6rth6jhr2vkh7c2ip7p6bsmdxmslbia47rjbmwpcz6wwu6veya`
      in chat: a hint follows, and the link is on the **rnfs shelf**
      page. `!shelf add <that cid> Manifesto`, then `!shelf`.
      **(hardware)** On a laptop with Python 3.11+ and **no internet**,
      download the wheels and the installer from the node, run it, then
      `rnfs daemon` and `rnfs status`. Note the USB copy time of the
      pack's tools (~1 MB) in the provisioner.
- [ ] fservbot's saved dialogues (from an earlier `/fsadd`) survive a
      reboot — they didn't before this build.
- [ ] `/plugins.json` lists the four, with their commands.
- [ ] **(hardware)** Power-cycle the node twice within its first minute:
      the third boot says `SAFE MODE` and `/admin` explains it; the boot
      after that is normal.

## 10. A chain of Stumps (when the new CAMs arrive)

Two or three CAMs; one with a Heltec as the first Stump. See `CHAIN.md`.

- [ ] Before placing them: `bench/wifi_bench.py` where each will sit;
      pick the quietest channel for the first Stump.
- [ ] Provision the first (chain: yes, first; note the secret) and the
      others (the Wi-Fi name of the one before, numbers 5, 6…, same
      secret, Heltec: no).
- [ ] Boot logs: `[chain] root on 192.168.4.1, channel 11` and
      `[chain] uplink: … via 192.168.4.1 (signal … dBm)`.
- [ ] `/admin` → Stump chain on each: the one above answered recently;
      the ones below are listed. `/chain.json` says the same.
- [ ] Phones on the last Stump's Wi-Fi get `192.168.6.x`, and its pages
      work as usual.
- [ ] FireFly over LoRa reaches a Stump with no Heltec, through the chain
      (chat, DM).
- [ ] **(hardware)** A PC on each end (`CHAIN.md` → A PC on the chain):
      `rnfs add` a 50–100 MB file on one, `rnfs get` it on the other.
      Note the time, and where the Stumps were (walls, floors).
- [ ] **(hardware)** Restart the middle Stump: the last one links up again
      by itself.

## 11. Stump on a computer

See `PC.md`. A Mac or a Windows PC, and a Heltec.

- [ ] `python3 provisioner.py --pc`: the wizard, then start-at-login.
      The log (`Stump/stump.log`) says `visitors reach it at http://…/`.
- [ ] Turn on the computer's hotspot (or join a travel router); a phone
      joins it and opens that address: home, chat, Tools, `/admin`.
- [ ] **(hardware)** The Heltec on USB (Heltec: "On USB" in the wizard):
      the log says `RNode on USB: …` and `radio configured`. FireFly over
      LoRa reaches the computer Stump (chat, a DM both ways).
- [ ] `/admin` → Radio on the computer: change TX power; the Heltec
      takes it (log: `radio configured`).
- [ ] Chained with a CAM: the computer as the first Stump, the CAM
      joining its hotspot with the same secret. `/admin` → Stump chain on
      both; a chat line from a phone on the CAM reaches a phone on the
      computer.
- [ ] Log out, restart the computer: the Stump comes back by itself.
- [ ] `git pull` and `--pc` again: settings kept, the Stump restarts.

## 12. Hardening (October 2026)

- [ ] Six chat lines sent fast from one phone: the fourth comes back
      `⧗ — you're typing too fast`; a few seconds later it works again.
      The same from FireFly over LoRa.
- [ ] Five wrong passwords on `/admin`: the sixth try, even the right
      one, says `too many wrong passwords — try again in 30 s`. Another
      phone can still log in.
- [ ] Four billboard posts in a minute: the fourth is refused.
- [ ] `/admin <pw> room vip minted` while a phone sits in `#vip`: the
      phone lands in `#main` with a `⊘ #vip minted` private message.
- [ ] `/admin <pw> mode hybrid`, then pull the power: after the restart
      `/admin <pw> mode` still says `hybrid`; `/admin <pw> reset-access`
      puts it back.
- [ ] **(with a certificate)** `mpremote connect PORT run bench/tls_probe.py`
      and the curl lines of `HTTPS_SETUP.md` step 0: send back the
      summary. Then, on the Stump's Wi-Fi, the chat page is plain HTTP
      (no padlock); in a private message ♪ opens a small window with a
      padlock; record, ■: the window closes and the note arrives.
      `/admin` has the padlock.

## 13. BarKeep, the librarian

- [ ] Files page: *Ask BarKeep*, "do you have a movie?" (and in French,
      "as-tu un livre ?"): the right files, linked; a download works.
- [ ] Type in the filter: rows narrow as you type; a kind pill; sort by
      size. Enter on a whole question answers in the drawer.
- [ ] Billboard: search a word that's only in a post's body: that post
      opens. Sort by title.
- [ ] In the chat (and from FireFly over LoRa): `!find <word>` answers on
      one line.

## What to send back

- The boot log (from power-on to `Announced as`); its first line names
  the release (`Project Stump -- Beta A (1.0.0-beta.3)`).
- Screenshots of `/admin` (radio, propagation status) and the home page
  with branding, phone and laptop.
- The iPhone ♪ answer, the APK download time, the 15 s Opus note time
  over LoRa, and the stamp-check time.
- The RAM figures from `/admin` → Plugins.
- The `tls_probe.py` summary (section 12), if the CAM has a certificate.
- Anything that looked stuck: the last line on screen, or the last lines
  of the boot log.

# Stump on a computer

A Windows, macOS or Linux computer can be a Stump: the same pages,
chat, plugins, packs, `/admin` and mesh as a CAM, running the same
firmware. With a Heltec plugged in by USB it's on the LoRa mesh, and it
chains with CAM Stumps over Wi-Fi like any other Stump.

```
 [ Laptop Stump + Heltec ] <-- Wi-Fi -- [ CAM Stump ]
   its hotspot: visitors,                its own Wi-Fi
   and the CAM, join it                  for its visitors
```

## Setting it up

You need Python 3.8 or newer (python.org on Windows and macOS) and
internet once, for two packages. From the Stump download or your clone:

```
python3 provisioner.py --pc          # Windows: py provisioner.py --pc
```

It asks for a folder (default: `Stump` in your home folder), then the
same questions as a CAM's wizard, adapted to a computer:

- the Wi-Fi name visitors join, for the About page;
- whether this Stump is in a chain, and its place there;
- the Heltec: **on USB**, **over Wi-Fi**, or **none**;
- packs, the bot's name and greeting, plugins, credits, features, the
  propagation node, the theme.

It ends by offering to start the Stump whenever you log in (a login
item on macOS, a scheduled task on Windows, a user service on Linux).
Or start it yourself:

```
Stump/venv/bin/python Stump/stump_pc.py        # Windows: Stump\venv\Scripts\python Stump\stump_pc.py
```

The first time, the firewall may ask whether to let Python accept
connections: allow it on **private** networks.

**macOS privacy.** macOS may stop the Terminal (and the Stump) reaching
the local network without asking: System Settings > Privacy & Security
> **Local Network**, turn on Terminal (the chain check says when this is
the problem). It also hides the names of Wi-Fi networks around from the
Terminal, so the Provisioner offers the ones this Mac has joined before.

**What's in the folder.** It plays the CAM's flash: the firmware,
plugins and `config.py` sit there as they do on the board, `sd/` is
the SD card, and `venv/` is the folder's own Python with `cryptography`
and `pyserial`. With start-at-login, the log is `stump.log`.

**Updating:** `git pull`, then `python3 provisioner.py --pc` again. It
copies what changed, keeps `config.py`, the identity and everything
saved, brings the folder's packs up to date, and restarts the Stump if
it starts at login. It shows the Stump's settings and asks whether to
change them; a Heltec plugged in by USB since is noticed and offered
(the other settings stay). `--pc --reconfigure` runs the wizard again.

**Restarting** without updating: with start-at-login, on macOS
`launchctl unload ~/Library/LaunchAgents/app.stump.node.plist` then
`launchctl load -w` on the same file (Windows: `schtasks /End /TN Stump`
then `schtasks /Run /TN Stump`; Linux: `systemctl --user restart
stump`); started by hand, Ctrl+C and run the same command again.

**Stopping or removing start-at-login:**

| | Stop | Remove |
|---|---|---|
| macOS | `launchctl unload ~/Library/LaunchAgents/app.stump.node.plist` | then delete that file |
| Windows | `schtasks /End /TN Stump` | `schtasks /Delete /TN Stump /F` |
| Linux | `systemctl --user stop stump` | `systemctl --user disable stump` |

## Visitors' Wi-Fi

The computer's operating system owns its Wi-Fi, so Stump uses whatever
network visitors can reach it on:

| | Visitors join | The Stump's address |
|---|---|---|
| **Windows Mobile Hotspot** (Settings → Network → Mobile hotspot) | the hotspot | `192.168.137.1` |
| **macOS Internet Sharing** (System Settings → General → Sharing) | the shared network | `192.168.2.1` |
| **Linux** (`nmcli device wifi hotspot`) | the hotspot | `10.42.0.1` |
| **A travel router** the computer is on | the router | the computer's address there |

Windows and macOS hotspots share a connection, so they usually want
one (Ethernet, or another Wi-Fi). macOS can't share Wi-Fi over that
same Wi-Fi. **With no internet at all, a small travel router (~€20) is
the dependable choice**: the computer, the Heltec and visitors' phones
all join it. Reserve the computer's address in the router and set it
as `PC_HOTSPOT_IP` (below).

Stump finds the hotspot's address by itself (the ones in the table, or
the computer's own address); the boot log says which: `visitors reach it
at http://…/`. If port 80 is taken, it uses 8080 and says so.

## The Heltec

**On USB:** keep the Heltec's RNode firmware as it is and plug it in;
`'auto'` finds it (Heltec V3's CP2102, and the other common USB chips).
On Windows it's a `COM` port, on macOS `/dev/cu.usbserial-…`. The radio
settings come from `/admin` → Radio, as on a CAM. If the Heltec was set
to Wi-Fi mode for a CAM and doesn't answer on USB, switch that mode off
with `rnodeconf` (its `--help` lists the Wi-Fi options).

**Over Wi-Fi:** as with a CAM: the Heltec joins the computer's network
with a fixed address (`rnodeconf <port> -w STATION --ip <address>`), and
you give the wizard that address.

**None:** a computer Stump in a chain reaches the LoRa mesh through a
Stump that has a Heltec.

## Chaining with CAM Stumps

**The computer as the first Stump** (the simplest): in the wizard, "The
first Stump", and note the chain secret. On each CAM, the wizard's
"Joins another Stump's Wi-Fi", with the computer's hotspot name, the
same secret, and its own number. The computer lists who joined it in
`/admin` → Stump chain and `GET /chain.json`.

**The computer and the CAM on the same Wi-Fi** (home, office): the
computer stays on it, with its internet. In the wizard, "Joins another
Stump's Wi-Fi", then "On the Wi-Fi it's on now", with the CAM's address
there (its setup summary's *On the Wi-Fi*, e.g. `192.168.0.161`). The
CAM must be the first Stump of the chain, have a chain secret, and run
1.0.0-beta.4 or newer (`CHAIN_LAN = True`, the default).

**The computer joining a CAM's own Wi-Fi:** join the CAM's Wi-Fi from the
computer's Wi-Fi settings, and in the wizard choose "Joins another
Stump's Wi-Fi" with the CAM's address (`192.168.<its number>.1`). With
one Wi-Fi radio the computer can't also run a hotspot, so its visitors
use that same network; a second network (Ethernet, a USB Wi-Fi adapter,
a router) gives it its own.

**Talking across the chain:** `/join wifi-mesh` in the chat, on each
Stump. The other Stumps show at the bottom of the column (🪵), lines
from their people as `<nick@thatstump>`, and `/msg rod@LaBuche ...`
reaches someone on another Stump privately.

**Checking the link.** The wizard checks it, step by step, and says what
to fix when a step fails (not on the CAM's Wi-Fi, the CAM's chain off,
different secrets...). Any time after:

```
python3 provisioner.py --check-chain
```

## Settings

In the folder's `config.py` (the wizard writes them):

| Setting | Default | |
|---|---|---|
| `PC_HOTSPOT_IP` | `'auto'` | The address visitors reach the computer on |
| `PC_HTTP_PORT` | `80` | The web port (8080 is tried if it's taken) |
| `PC_STORAGE_MB` | `2048` | Room for shared files and tools in `sd/`: the "card" never fills your disk |
| `PC_HOTSPOT_NAME` | | The Wi-Fi name the About page tells visitors to join |
| `PC_CHAIN_PARENT_IP` | | The Stump this one joins (computer joining a CAM) |

## What's different from a CAM

- **No sign-in pop-up on some set-ups.** The captive portal needs port
  53 on the hotspot's address; a Windows hotspot keeps that port for
  itself. Visitors then open the address themselves.
- **Its own transfers are 16 KB, as on a CAM** (propagation-node
  messages, voice notes). That's how Stump's Reticulum announces a
  transfer, not memory. Transfers it *relays* aren't limited, and big
  files go through rnfs, which runs beside it on the same computer.
- **The clock is the computer's**: the mesh never sets it.
- **Tested** on Windows, macOS and Linux by the project's CI (a Stump
  folder made by the Provisioner, every page; on Linux, a CAM joining
  it over the chain); the USB link against a simulated RNode. Not yet
  with a real Heltec on USB: see `FIELD_TEST.md` section 11.

## How it works (for developers)

`pc/stump_pc.py` starts `example_node.py` exactly as `main.py` does on
the board. `pc/pc_compat/` gives regular Python what the firmware
expects from MicroPython: the `u…` module names, `uasyncio`'s
`awrite`/`aclose`, AES and Ed25519/X25519 from `cryptography` (checked
against the board's own code), and stand-ins for `network` (the
hotspot's real address and name) and `machine` (no pins; the card is
`sd/`). `stump_host.py` maps the paths firmware code opens at `/` into
the folder, writes files as UTF-8 without line-ending translation, and
answers `os.statvfs` with the storage quota. The firmware itself only
gained the USB Heltec interface (`urns/interfaces/rnode_serial.py`) and
a few "on a computer" branches (the hotspot address, port 8080).

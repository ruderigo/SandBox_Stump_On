# The Stump Flasher

One HTML page that makes a **Freenove ESP32-S3-CAM** into a Stump, from
Chrome or Edge on a computer. Nothing to install, no certificate, no
terminal: save the page, open the saved file, plug the board in.

It's `Stump-Flasher-<release>.html` on each release (the version is in
the name). It holds everything: MicroPython 1.28 for the ESP32-S3 with
octal PSRAM (MIT licence), the Stump compiled for it, and esptool-js
(Apache-2.0), which writes the board. Nothing is downloaded or sent
anywhere while it works.

## Using it

1. Save the page on the computer and open the saved file in Chrome or
   Edge. (Opened from a web address it can't reach the board: browsers
   only allow USB from a secure page, and a saved file counts as one.)
2. Choose **A new Stump** and fill in its name, an admin password, and,
   only if you have one, the home Wi-Fi and the LoRa radio (a Heltec
   running RNode: set it up with the Provisioner).
3. **Make my Stump**, pick the board in the browser's list. About 5
   minutes: it erases the board, writes MicroPython, copies the Stump,
   writes its settings and restarts it.
4. Its Wi-Fi appears: join it from a phone.

**Update a Stump** copies the new release onto a Stump and keeps
everything else: its settings (`config.py`), its identity on the mesh,
what's on its card. A Stump on an older MicroPython is told to use
*A new Stump* instead (that erases the board, so it gets a new identity).

If the board isn't found: another USB cable (some only charge), another
port; or hold BOOT, press and release RESET, let go of BOOT, and try again.

## What it does on the board

The same as the Provisioner:

- erase, then MicroPython at 0x0 (esptool-js, 460800 baud)
- at its REPL (115200): a running Stump stopped, its watchdog given two
  hours (`QUIET_WATCHDOG`), a soft reset
- every file of the Stump, folders first: each in chunks to
  `<file>.part`, its SHA-256 checked on the board, then renamed over the
  old one, so a cable pulled out never leaves half a module; a module
  arriving compiled (`.mpy`) has its `.py` removed, and the other way
- `config.py`: `final_firmware/config.py` with every name, password and
  Wi-Fi taken out at build time (the build stops if one is left), the
  answers put in, a fresh Stump's defaults for the rest (no chain, open
  access, chat + billboard + files, the paper theme). The fserv bot's
  operator password is the admin password.
- `machine.reset()`

Not done here (the Provisioner does them): the SD card's Tools and
packs, a chain, the Heltec's own firmware.

## Building it

    pip install mpy-cross==1.28.0.post2
    python3 scripts/build_flasher.py dist/ [--micropython FILE.bin]

Without `--micropython` it downloads the image the Provisioner uses
(`CAM_FIRMWARE_LATEST_URL`) and checks its SHA-256
(`MICROPYTHON_SHA256`). Built twice from the same commit, the page is
the same, byte for byte. Tests: `tests/flasher_test.py` (the uploader
against a pretend board running MicroPython's Unix port, and the page
in Chromium with Web Serial piped to it).

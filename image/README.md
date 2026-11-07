# The Stump image

A MicroPython image with the Stump frozen in, one per board:

| file | board | flashed at |
|---|---|---|
| `stump-<release>-wrover.bin` | Freenove ESP32-WROVER (original ESP32, 4 MB flash, 4 MB PSRAM) | `0x1000` |
| `stump-<release>-s3cam.bin` | Freenove ESP32-S3-WROOM CAM (ESP32-S3, 8 MB flash, Octal PSRAM) | `0x0` |

Both are attached to every GitHub release, built by the **Stump images**
workflow in Espressif's ESP-IDF container from the MicroPython release
the boards run (v1.28.0). The Provisioner picks them up on its own: "A
Stump board" flashes the image for the chip it finds (downloaded from the
release, or found next to the Provisioner, in `~/.provisioner/firmware`,
Downloads or the Desktop).

## Why

A board that takes the Stump as files loads about 1.6 MB of Python into
RAM at boot, and every memory clean-up walks all of it: ~2 s on a WROVER's
PSRAM, and MicroPython's ESP32 port collects as soon as its heap fills.
Frozen into the image, the code runs from flash: far less in RAM, so the
clean-ups are shorter and rarer, the boot is quicker, and the board's
filesystem holds settings, identity and packs instead of the firmware.

## What stays on the filesystem

- `config.py`: the board's settings (the Provisioner's questions);
- `main.py`: MicroPython runs it from the filesystem;
- the built-in plugins (`fservbot/`, `stumpid/`), `web/`, `lib/*.mpy`,
  `themes.json`, `_sd_web/`: data and plugin folders the firmware reads
  from the filesystem;
- the packs (`nomadnet/`, `rnfs/`...): opt-in, installed and updated as
  before;
- the node's own state (`rns/`, `*.json`).

`stump_image.py`, frozen in, says what the image holds: `RELEASE`,
`PARTITIONS` (the partition table's tag) and `FROZEN` (the modules). The
Provisioner reads it to skip those modules when uploading, to remove any
copy of them left on the filesystem (the filesystem is searched before
the frozen modules, so a stale copy would run instead), and to read the
board's release.

## Updating a board that runs the image

"Check or fix something" > "Update a board to this release's Stump image"
writes the new image in place: no erase, so the settings, identity and
packs stay (the filesystem partition is after the application and isn't
written). Then the files that live on the filesystem are brought up to
date. "A Stump board" offers the same in section 3 when the board's image
has this release's partition layout; a board with another layout, or
without the image, is erased for it and asked the setup questions again.

## The partition table

`partitions-stump.csv`: a 3 MiB application partition (MicroPython ~1.7
MiB, the Stump ~0.9 MiB) and no `vfs` entry: the port makes the
filesystem from the end of the application to the end of flash at boot,
so it's 1 MiB on a 4 MiB WROVER and 5 MiB on an 8 MiB S3-CAM. Its tag
(`image/stage.py partitions_tag`) is `STUMP_IMAGE_PARTITIONS` in the
Provisioner; a test keeps them equal.

## Building it yourself

In a checkout with ESP-IDF v5.5.1 set up (`. $IDF_PATH/export.sh`) and a
MicroPython v1.28.0 checkout with `mpy-cross` built and the ESP32 port's
submodules fetched:

```
sh image/build.sh /path/to/micropython build/images [wrover|s3cam]
```

The frozen set is staged by `image/stage.py` (`build/frozen/`) from the
same file list the Provisioner uploads; `image/manifest.py` freezes it
with MicroPython's own ESP32 modules and asyncio.

## Testing it

`scripts/build_micropython_frozen.sh` builds the Unix port with the same
frozen set; `STUMP_FROZEN=1 MICROPYTHON=... python3 tests/run.py` then
runs the whole suite on a tree that holds only what a board running the
image has on its filesystem (CI's "frozen" job).

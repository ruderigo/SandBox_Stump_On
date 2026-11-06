#!/usr/bin/env python3
"""Stages the Stump for freezing into a MicroPython image (image/README.md).

    python3 image/stage.py OUT_DIR

copies into OUT_DIR every Python module the Provisioner would put on a
board (provisioner.STUMP_APP_FILES), except what has to stay on the
board's filesystem:
  - config.py: the board's own settings;
  - main.py: MicroPython runs it from the filesystem;
and writes OUT_DIR/stump_image.py, which the firmware and the Provisioner
read on a board that runs the image: the release, the modules frozen
(the Provisioner doesn't upload those), and the partition table's tag.
The built-in plugins (fservbot, stumpid), the web files, lib/*.mpy and the
packs stay on the filesystem as before.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ON_FILESYSTEM = {"config.py", "main.py"}


def frozen_modules():
    sys.path.insert(0, str(ROOT))
    import provisioner
    return sorted(f for f in provisioner.STUMP_APP_FILES if f.endswith(".py") and f not in ON_FILESYSTEM)


def release():
    for line in (ROOT / "final_firmware" / "example_node.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("STUMP_RELEASE = "):
            return line.split('"')[1]
    raise SystemExit("STUMP_RELEASE not found in example_node.py")


def partitions_tag():
    """A short tag of the partition table: a board whose tag differs from
    the image's has to be erased, not updated in place."""
    text = "\n".join(l for l in (ROOT / "image" / "partitions-stump.csv").read_text().splitlines()
                     if l.strip() and not l.startswith("#"))
    return "stump-" + hashlib.sha256(text.encode()).hexdigest()[:8]


def stage(out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    mods = frozen_modules()
    for rel in mods:
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "final_firmware" / rel, dst)
    info = {"release": release(), "partitions": partitions_tag(), "frozen": mods}
    (out / "stump_image.py").write_text(
        "# Written by image/stage.py: this MicroPython image has the Stump frozen in.\n"
        "RELEASE = %r\n"
        "PARTITIONS = %r\n"
        "FROZEN = %s\n" % (info["release"], info["partitions"], json.dumps(mods, indent=0).replace("\n", "")),
        encoding="utf-8")
    return info


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    info = stage(sys.argv[1])
    print("staged %d modules of Stump %s (partitions %s) in %s" % (len(info["frozen"]), info["release"], info["partitions"], sys.argv[1]))

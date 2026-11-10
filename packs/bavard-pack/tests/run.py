#!/usr/bin/env python3
"""Runs the Bavard pack's own test against a Stump firmware tree.

    MICROPYTHON=~/micropython-f32/micropython python3 tests/run.py [FIRMWARE_DIR]

FIRMWARE_DIR defaults to ../../final_firmware (this pack inside
SandBox_Stump_On's packs/). Like the repository's tests/run.py, it copies
the firmware and the plugin into a fresh folder, so nothing is written
into either, and runs bavard_duet.py there under the MicroPython Unix port
(scripts/build_micropython.sh builds it) with a 4 MB heap.
"""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
FW = Path(sys.argv[1]) if len(sys.argv) > 1 else PACK.parent.parent / "final_firmware"
MP = os.environ.get("MICROPYTHON", "micropython")

if not (FW / "plugins.py").is_file():
    sys.exit("no Stump firmware at %s (give its folder)" % FW)
work = Path(tempfile.mkdtemp(prefix="bavard-test-"))
try:
    ok = True
    for test in ("bavard_duet.py", "bavard_four.py"):
        shutil.rmtree(work / "fw", ignore_errors=True)
        shutil.copytree(FW, work / "fw")
        shutil.copytree(PACK / "bavard", work / "fw" / "bavard")
        r = subprocess.run([MP, "-X", "heapsize=4M", str(HERE / test)],
                           cwd=work / "fw", capture_output=True, text=True, timeout=900)
        out = r.stdout + r.stderr
        print("== " + test)
        print("\n".join(l for l in out.splitlines() if not l.startswith("[")))
        ok = ok and "FAILURES: []" in out
    sys.exit(0 if ok else 1)
finally:
    shutil.rmtree(work, ignore_errors=True)

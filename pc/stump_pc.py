#!/usr/bin/env python3
# Project Stump -- stump_pc.py: a Stump on a computer (docs/PC.md).
#
# The computer plays the CAM's role: same pages, chat, plugins, admin and
# mesh, with the Heltec on USB (or over Wi-Fi), and it can chain with CAM
# Stumps. This folder plays the board's flash: the firmware, the plugins
# and config.py sit next to this file, as they do on the board, and the
# Provisioner keeps them up to date (python3 provisioner.py --pc).
#
# Run:  python3 stump_pc.py        (Windows: py stump_pc.py)
# Stop: Ctrl+C
#
#   --service   what start-at-login runs: the log goes to stump.log in this
#               folder (rotated at 5 MB), and the node is started again if
#               it ever stops on an error (not after Ctrl+C).

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_PYTHON = (3, 8)


def _fail(msg):
    print("\n[stump] " + msg + "\n")
    sys.exit(1)


def main():
    if sys.version_info < MIN_PYTHON:
        _fail("Stump needs Python %d.%d or newer (this is %s)." % (MIN_PYTHON + (sys.version.split()[0],)))
    if not os.path.exists(os.path.join(HERE, "example_node.py")):
        _fail("The Stump firmware isn't in this folder. Set it up with:\n"
              "  python3 provisioner.py --pc")
    if not os.path.exists(os.path.join(HERE, "config.py")):
        _fail("No config.py in this folder. Set it up with:\n  python3 provisioner.py --pc")
    try:
        import cryptography  # noqa: F401
    except ImportError:
        _fail("Stump needs the 'cryptography' package:\n  python3 -m pip install cryptography pyserial")

    # The log has symbols (✓ ✗ ✎ →): never let printing them stop the node
    # (Windows prints to a pipe or file in its legacy code page otherwise).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    os.chdir(HERE)
    sys.path[:0] = [os.path.join(HERE, "pc_compat"), HERE]
    import stump_host
    stump_host.install(HERE)
    print("[stump] on a computer: %s, Python %s" % (sys.platform, sys.version.split()[0]))
    print("[stump] folder: " + HERE)
    print("[stump] visitors reach it at http://%s/" % stump_host.hotspot_ip())
    import example_node  # noqa: F401  -- the node itself, exactly as on the board


LOG = os.path.join(HERE, "stump.log")
LOG_MAX = 5 * 1024 * 1024


def _open_log():
    try:
        if os.path.getsize(LOG) > LOG_MAX:
            os.replace(LOG, LOG + ".1")
    except OSError:
        pass
    return open(LOG, "a", buffering=1, encoding="utf-8", errors="replace")


def service():
    """Runs the node in a child process, logging to stump.log, and starts
    it again if it stops on an error (with a growing pause, up to a
    minute, so a broken setup doesn't spin)."""
    import subprocess
    import time
    log = _open_log()
    wait = 2
    while True:
        log.write("\n[stump] starting %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        t0 = time.time()
        try:
            code = subprocess.call([sys.executable, "-u", os.path.abspath(__file__)],
                                   cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
        except KeyboardInterrupt:
            log.write("[stump] stopped\n")
            return
        if code == 0:
            log.write("[stump] stopped\n")
            return
        if time.time() - t0 > 300:
            wait = 2
        log.write("[stump] stopped with code %s; starting again in %d s\n" % (code, wait))
        log.flush()
        time.sleep(wait)
        wait = min(wait * 2, 60)
        log.close()
        log = _open_log()


if __name__ == "__main__":
    if "--service" in sys.argv:
        service()
    else:
        if sys.stdout is None:          # pythonw.exe: no console to print to
            sys.stdout = sys.stderr = _open_log()
        try:
            main()
        except KeyboardInterrupt:
            pass

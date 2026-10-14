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

    os.chdir(HERE)
    sys.path[:0] = [os.path.join(HERE, "pc_compat"), HERE]
    import stump_host
    stump_host.install(HERE)
    print("[stump] on a computer: %s, Python %s" % (sys.platform, sys.version.split()[0]))
    print("[stump] folder: " + HERE)
    print("[stump] visitors reach it at http://%s/" % stump_host.hotspot_ip())
    import example_node  # noqa: F401  -- the node itself, exactly as on the board


if __name__ == "__main__":
    main()

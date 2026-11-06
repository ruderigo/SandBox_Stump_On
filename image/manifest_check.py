# The same Stump freeze as image/manifest.py, for a build of the Unix port
# that checks everything freezes (CI: "the Stump freezes"), without the
# ESP32 port's own modules.
import os

include("$(MPY_DIR)/extmod/asyncio")
freeze(os.environ["STUMP_FROZEN"])

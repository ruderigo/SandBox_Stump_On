# What's frozen into a Stump image: MicroPython's own ESP32 modules and
# asyncio, then the Stump staged by image/stage.py (the folder in
# STUMP_FROZEN). Not the networking bundle, mqtt and the rest of the
# generic image: the Stump doesn't use them, and the room is for the Stump.
import os

freeze("$(PORT_DIR)/modules")
include("$(MPY_DIR)/extmod/asyncio")
freeze(os.environ["STUMP_FROZEN"])

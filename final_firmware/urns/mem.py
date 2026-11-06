# µReticulum (Project Stump) -- memory clean-ups only when they're needed.
#
# The code used to force a full garbage collection at dozens of places,
# several per packet (a chain secret's signature and its check, a proof, an
# announce), and after every DNS answer: from the days of boards without
# PSRAM, where the heap had to stay tidy. A full collection walks the whole
# heap; on an ESP32-WROVER's 4 MB of PSRAM it takes about 2 s, and the
# event loop stops for it (measured, 1.0.0-beta.56: "a memory clean-up took
# 2040 ms (839 KB in use)"), so every packet froze the Stump for seconds.
#
# collect() is what those places call now: a collection only when free
# memory is getting low. MicroPython still collects by itself when an
# allocation finds the heap full, as it always did; a board short of memory
# collects as before.

import gc

LOW_FRACTION = 0.25        # under this share of the heap free: collect
LOW_BYTES = 96 * 1024      # ... or under this much free, whatever the heap

_n = [0, 0]                # [asked, collected], for /admin and the tests


def low():
    """True when free memory is low enough to be worth a collection now."""
    try:
        free = gc.mem_free()
        used = gc.mem_alloc()
    except AttributeError:
        return False       # CPython (a computer Stump): its own collector
    total = free + used
    return free < LOW_BYTES or free < total * LOW_FRACTION


def collect():
    """A garbage collection, only if memory is low (see above)."""
    _n[0] += 1
    if low():
        _n[1] += 1
        gc.collect()
        return True
    return False


def stats():
    return {"asked": _n[0], "collected": _n[1]}

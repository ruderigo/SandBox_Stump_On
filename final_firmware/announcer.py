# Project Stump -- announcer.py
#
# When the Stump announces its LXMF address (example_node's reannounce
# loop): every REANNOUNCE_INTERVAL seconds (config.py, /admin -> Stump
# settings -> Announcing, applied at once), and once more on demand from
# /admin's "Announce now". An announce goes out on every interface, the
# radio too, so an announce on demand waits NOW_GAP since the last one
# asked for (LoRa airtime), and the interval stays within EVERY_MIN and
# EVERY_MAX.

EVERY_DEFAULT = 120
EVERY_MIN = 60              # 1 minute
EVERY_MAX = 24 * 3600       # 1 day
NOW_GAP = 30

_st = {"every": None, "want": False, "since": None, "count": 0, "asked_at": None, "clock": 0}


def _clamp(s):
    try:
        s = int(s)
    except (TypeError, ValueError):
        return EVERY_DEFAULT
    return max(EVERY_MIN, min(EVERY_MAX, s))


def every():
    """Seconds between announces."""
    if _st["every"] is None:
        try:
            import config
            _st["every"] = _clamp(getattr(config, "REANNOUNCE_INTERVAL", EVERY_DEFAULT))
        except ImportError:
            _st["every"] = EVERY_DEFAULT
    return _st["every"]


def set_every(s):
    _st["every"] = _clamp(s)
    return _st["every"]


def tick(s=1):
    """The reannounce loop's clock: s seconds went by (no wall clock
    needed: a CAM may not know the time)."""
    _st["clock"] += s


def request():
    """/admin's "Announce now": (True, 0) if asked for, or (False, seconds
    to wait) when one was asked for under NOW_GAP ago."""
    a = _st["asked_at"]
    if a is not None and _st["clock"] - a < NOW_GAP:
        return False, NOW_GAP - (_st["clock"] - a)
    _st["asked_at"] = _st["clock"]
    _st["want"] = True
    return True, 0


def take():
    """True once after request(): the loop announces at once."""
    if _st["want"]:
        _st["want"] = False
        return True
    return False


def done():
    """An announce went out."""
    _st["since"] = _st["clock"]
    _st["count"] += 1


def status():
    """{"every", "ago": seconds since the last announce or None, "next_in",
    "pending": one asked for and not out yet, "count"}."""
    ago = None if _st["since"] is None else _st["clock"] - _st["since"]
    nxt = every() - ago if ago is not None else None
    return {"every": every(), "ago": ago, "next_in": max(0, nxt) if nxt is not None else None,
            "pending": _st["want"], "count": _st["count"]}

# Project Stump -- layout.py
#
# The order of the navigation buttons (the icon row on every page) and of
# the home page's tiles, set by an admin from /admin by dragging them, and
# saved on the board's own memory like the theme. Home comes first by
# default. A key the saved order doesn't know (a feature switched back
# on, a new plugin card) goes at the end; one that no longer exists is
# skipped, so an old saved order never hides anything or breaks a page.

LAYOUT_FILE = "/layout.json"

NAV_DEFAULT = ("home", "chat", "board", "files", "tools", "about")
TILES_DEFAULT = ("chat", "board", "files", "tools", "about")

_saved = {}


def _load():
    global _saved
    try:
        import json
        with open(LAYOUT_FILE) as f:
            d = json.load(f)
        _saved = {k: [str(x) for x in d.get(k, [])] for k in ("nav", "tiles") if isinstance(d.get(k), list)}
    except Exception:
        _saved = {}


_load()


def order(kind, available):
    """`available` (keys, in their default order) in the admin's order."""
    want = _saved.get(kind) or []
    avail = list(available)
    out = [k for k in want if k in avail]
    return out + [k for k in avail if k not in out]


def nav(available=NAV_DEFAULT):
    return order("nav", available)


def tiles(available):
    return order("tiles", available)


def is_custom(kind):
    return bool(_saved.get(kind))


def save(kind, keys):
    """Saves an order (None: back to the default). True if saved."""
    import json
    if kind not in ("nav", "tiles"):
        return False
    new = dict(_saved)
    if keys:
        seen = []
        for k in keys:
            k = str(k)[:120]
            if k and k not in seen:
                seen.append(k)
        new[kind] = seen[:40]
    else:
        new.pop(kind, None)
    try:
        with open(LAYOUT_FILE, "w") as f:
            json.dump(new, f)
    except OSError:
        return False
    _saved.clear()
    _saved.update(new)
    return True

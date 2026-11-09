# Where a room goes (1.0.0-beta.62): its scope.
#
#   local  this Stump only (like #main)
#   wifi   the whole chain, over its Wi-Fi (like #wifi-mesh)
#   lora   the chain and, over LoRa, the other Stumps that agree (like
#          #lora-mesh): every line on the air
#
# The three built-in rooms keep theirs. Any other room starts local; a
# Stump's admin sets it, in the chat, with this Stump's /admin password:
#
#   /create <password> #room -local|-wifi|-lora   a new room
#   /setchan <password> #room -local|-wifi|-lora  an existing one
#   /setchan <password>                           the rooms and their scopes
#   /chanreq <password> [-a 1 2 | -r 3]           LoRa rooms other Stumps offer
#
# -lora warns about airtime first, and is done only when the command is
# typed again with "confirm" at the end. These commands go no further than
# this Stump's own code: not to the room, not to plugins, not in a log.
#
# The chain follows: a scope set on one Stump of the chain is set on the
# others (rrc_mesh: "[ROOM] #room scope n" between Stumps that say "rs" in
# their beacon; the newest n wins). A Stump outside the chain, heard over
# LoRa, only offers its LoRa rooms: here they wait as requests -- BarKeep
# says so in #main -- until this Stump's admin accepts or refuses them
# with /chanreq.
import time
import rrc
import i18n

FILE = "/rooms.json"
SCOPES = ("local", "wifi", "lora")
REFUSED_S = 86400            # a refused offer isn't asked again for a day
MAX_REQUESTS = 16

_db = [None]                 # {"r": {room: [scope, n]}}
_requests = []               # [{"room", "h", "name", "at"}] -- LoRa offers from outside the chain
_refused = {}                # (room, h) -> when
_shared = {}                 # room -> {h: True}: Stumps outside the chain sharing this LoRa room
_hooks = {"changed": None}   # rrc_mesh: tell the chain


def builtin():
    return {rrc.DEFAULT_ROOM: "local", rrc.CHAIN_ROOM: "wifi", rrc.MESH_ROOM: "lora"}


def _load():
    if _db[0] is None:
        db = None
        try:
            import json
            with open(FILE) as f:
                db = json.load(f)
        except (OSError, ValueError):
            db = None
        if not isinstance(db, dict) or not isinstance(db.get("r"), dict):
            db = {"r": {}}
        _db[0] = db
    return _db[0]


def _save():
    try:
        import store
        store.save_json(FILE, _load(), "rooms")
    except Exception as e:
        print("[rooms] couldn't save:", e)


def boot():
    """The rooms with a scope, back after a restart."""
    for room, (scope, _) in list(_load()["r"].items()):
        if scope != "local":
            rrc.create_room(room)


def reset(path=None):
    """Tests: start over."""
    global FILE
    if path:
        FILE = path
    _db[0] = None
    del _requests[:]
    _refused.clear()
    _shared.clear()


def scope(room):
    room = rrc.canon(room)
    b = builtin().get(room)
    if b:
        return b
    e = _load()["r"].get(room)
    return e[0] if e else "local"


def version(room):
    e = _load()["r"].get(rrc.canon(room))
    return e[1] if e else 0


def extra():
    """{room: scope} for the rooms other than the built-in ones that go
    beyond this Stump (and the ones set back to local, with their n, for
    the chain)."""
    return {r: e[0] for r, e in _load()["r"].items()}


def set_scope(room, sc, n=None):
    """Sets a room's scope (creating the room). n: the chain's number for
    this change (from another Stump); None: a change made here, one more
    than any seen. True if it changed."""
    room = rrc.canon(room)
    if room in builtin() or sc not in SCOPES:
        return False
    if sc != "local":
        slug, err = rrc.create_room(room)
        if err:
            print("[rooms] #%s: %s" % (room, err))
            return False
    db = _load()
    old = db["r"].get(room)
    if n is None:
        n = (old[1] if old else 0) + 1
    if old and old[0] == sc and old[1] >= n:
        return False
    db["r"][room] = [sc, n]
    if sc != "lora":
        _shared.pop(room, None)
    _save()
    return True


def shares(room, h, on_chain):
    """Lines of `room` go to / come from Stump h: a chain Stump for a Wi-Fi
    or LoRa room, one outside the chain for a LoRa room both agreed on."""
    sc = scope(room)
    if sc == "local" or rrc.canon(room) in builtin():
        return False
    if on_chain:
        return True
    return sc == "lora" and h in _shared.get(rrc.canon(room), {})


def share(room, h):
    _shared.setdefault(rrc.canon(room), {})[h] = True
    for r in [r for r in _requests if r["room"] == rrc.canon(room) and r["h"] == h]:
        _requests.remove(r)


def unshare(room, h):
    _shared.get(rrc.canon(room), {}).pop(h, None)
    for r in [r for r in _requests if r["room"] == rrc.canon(room) and r["h"] == h]:
        _requests.remove(r)


def refused(room, h):
    t = _refused.get((rrc.canon(room), h))
    return t is not None and time.time() - t < REFUSED_S


def offered(room, h, name):
    """A Stump outside the chain offers its LoRa room. Returns "ok" if
    this Stump shares it already (same scope here: both chose), "no" if
    refused lately, "asked" if it's a new request (BarKeep says so in
    #main), None if asked before."""
    room = rrc.canon(room)
    if room in builtin() or not rrc.clean_room(room):
        return None
    if scope(room) == "lora":
        share(room, h)
        return "ok"
    if refused(room, h):
        return "no"
    if any(r["room"] == room and r["h"] == h for r in _requests):
        return None
    if len(_requests) >= MAX_REQUESTS:
        _requests.pop(0)
    _requests.append({"room": room, "h": h, "name": name or h[:8], "at": time.time()})
    _notify(i18n.t("chanreq_new", None, name=name or h[:8], room=room, n=len(_requests)))
    return "asked"


def _notify(text):
    try:
        import barkeep
        who = barkeep.BOT_NAME
    except Exception:
        who = "BarKeep"
    rrc.post(rrc.DEFAULT_ROOM, who, text, bot=True)


# -- the commands ----------------------------------------------------------------

def is_command(text):
    c = text[:9].lower()
    return c.startswith("/create ") or c.startswith("/setchan") or c.startswith("/chanreq")


def _pw_ok(pw, client_id):
    import barkeep
    return barkeep._check_admin_pw(pw, client_id)


def _warn(lang):
    return ["⚠ " + i18n.t("room_lora_warn", lang)]


def command(client_id, text, lang):
    """/create, /setchan, /chanreq. Returns (reply_lines, None)."""
    parts = text.split()
    cmd = parts[0][1:].lower()
    usage = [i18n.t("room_usage_" + cmd, lang)]
    if len(parts) < 2:
        return usage, None
    if not _pw_ok(parts[1], client_id):
        return ["✗ " + i18n.t("room_bad_pw", lang)], None
    args = parts[2:]
    if cmd == "chanreq":
        return _chanreq(args, lang), None
    if not args and cmd == "setchan":
        rows = ["#%s  %s" % (r, s) for r, s in sorted(builtin().items())]
        rows += ["#%s  %s" % (r, s) for r, s in sorted(extra().items()) if rrc.room_exists(r)]
        return rows, None
    room = rrc.clean_room(args[0].lstrip("#")) if args else ""
    flags = [a.lower() for a in args[1:]]
    sc = next((f[1:] for f in flags if f[1:] in SCOPES and f[:1] == "-"), None)
    if not room or not sc:
        return usage, None
    if room in builtin():
        return ["✗ " + i18n.t("room_builtin", lang, room=room)], None
    exists = rrc.room_exists(room)
    if cmd == "create" and exists:
        return ["✗ " + i18n.t("room_exists", lang, room=room)], None
    if cmd == "setchan" and not exists:
        return ["✗ " + i18n.t("room_missing", lang, room=room)], None
    if sc == "lora" and "confirm" not in flags:
        return _warn(lang) + [i18n.t("room_confirm", lang, cmd=cmd, room=room)], None
    if not exists:
        slug, err = rrc.create_room(room)
        if err:
            return ["✗ " + err], None
    if scope(room) == sc and exists:
        return [i18n.t("room_same", lang, room=room, scope=sc)], None
    set_scope(room, sc)
    if _hooks["changed"]:
        try:
            _hooks["changed"](room)
        except Exception as e:
            print("[rooms] telling the chain failed:", e)
    out = [i18n.t("room_set", lang, room=room, scope=sc)]
    if cmd == "create":
        out.append(i18n.t("room_join_hint", lang, room=room))
    return out, None


def _chanreq(args, lang):
    if not args:
        if not _requests:
            return [i18n.t("chanreq_none", lang)]
        out = _warn(lang)
        now = time.time()
        for i, r in enumerate(_requests):
            out.append("%d. #%s  %s  (%d min)" % (i + 1, r["room"], r["name"], (now - r["at"]) // 60))
        out.append(i18n.t("chanreq_how", lang))
        return out
    act = args[0].lower()
    try:
        picks = sorted(set(int(a) for a in args[1:]))
    except ValueError:
        picks = []
    if act not in ("-a", "-r") or not picks or any(p < 1 or p > len(_requests) for p in picks):
        return [i18n.t("room_usage_chanreq", lang)]
    chosen = [_requests[p - 1] for p in picks]
    out = []
    for r in chosen:
        if act == "-a":
            if scope(r["room"]) != "lora":
                set_scope(r["room"], "lora")
                if _hooks["changed"]:
                    try:
                        _hooks["changed"](r["room"])
                    except Exception as e:
                        print("[rooms] telling the chain failed:", e)
            share(r["room"], r["h"])
            _answer(r, "ok")
            out.append(i18n.t("chanreq_ok", lang, room=r["room"], name=r["name"]))
        else:
            _refused[(r["room"], r["h"])] = time.time()
            unshare(r["room"], r["h"])
            _answer(r, "no")
            out.append(i18n.t("chanreq_no", lang, room=r["room"], name=r["name"]))
        if r in _requests:
            _requests.remove(r)
    return out


_answers = []                # [(h, room, "ok"|"no")] for rrc_mesh to send


def _answer(r, what):
    _answers.append((r["h"], r["room"], what))

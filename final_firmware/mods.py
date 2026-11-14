# Room moderation (1.0.0-beta.64): ops and mods, /kick, /mute, /ban, and
# a room's topic kept to them (+t).
#
# Modelled on rrcd, the RRC hub NomadNet's Channels and MeshChatX speak
# (github.com/kc1awv/rrcd, MIT): the same command names and meanings, so
# someone who knows one knows the other --
#   server op (rrcd: trusted identities)  = this Stump's admin password
#   room op   (rrcd: /op <room> <who>)    = /op, named by the admin
#   half-op   (IRC's %, not in rrcd)      = /mod, named by an op
#   /kick, /ban add|del|list, /mode +t    = /kick, /ban /unban /bans, /mode
#   a moderated room (+m and voice)       = /mute and /unmute, per person
# Each role is in one room ("#room") or in every room of this Stump
# ("-stump"); across a chain is not done (pinned, the kit, 1.0.0-beta.64).
#
# Held by an identity, never by a nick (a nick can be taken by anyone
# once its owner leaves, and "nick@stump" can be anyone's): an LXMF
# address (Sideband, MeshChat, NomadNet, MeshChatX, a FireFly after its
# /auth), or a registered profile (the web, logged in). A guest can be
# kicked, muted and banned (until they come back under another name: a
# guest is a browser), never made op or mod. People on other Stumps
# (nick@stump) can be muted or banned here: their lines don't show here.
#
# Who does what (rrcd's rules, plus the mod between):
#   admin (the password, first in the command): everything, on anyone.
#   op:  /mod /demod, /kick, /mute /unmute, /ban /unban /bans, /mode, the
#        topic under +t -- in their room (or all, "-stump"), on mods and
#        people without a role; not on another op (the admin can).
#   mod: /kick, /mute /unmute, the topic under +t -- on people without a role.
# The admin password is checked like /setchan's (guard.py: wrong ones
# count toward the lockout), and never posted or logged: these commands
# are taken before plugins and before the room sees them.

import time

try:
    import ujson as json
except ImportError:
    import json

import i18n
import rrc

FILE_NAME = "mods.json"
STUMP = "*"                 # a role, ban or mute in every room of this Stump
KICK_S = 60                 # kicked: out of the room, and not back in for that long
MUTE_MAX_MIN = 7 * 24 * 60
MAX_ENTRIES = 200           # roles + bans + mutes, all together

_path = None
_db = None
_kicked = {}                # (key, room) -> until


# -- storage --------------------------------------------------------------------

def _file():
    if _path:
        return _path
    try:
        import fserv
        if fserv.sd_ok:
            return fserv.SD_MOUNT + "/" + FILE_NAME
    except Exception:
        pass
    return "/" + FILE_NAME


def _load():
    global _db
    if _db is not None:
        return _db
    db = None
    try:
        with open(_file()) as f:
            db = json.load(f)
    except (OSError, ValueError):
        db = None
    if not isinstance(db, dict):
        db = {}
    for k in ("roles", "bans", "mutes"):
        if not isinstance(db.get(k), dict):
            db[k] = {}
    if not isinstance(db.get("t"), list):
        db["t"] = []
    _db = db
    return db


def _save():
    try:
        import store
        return store.save_json(_file(), _load(), "mods")
    except Exception as e:
        print("[mods] not saved:", e)
        return False


def reset(path=None):
    """Forget everything (tests); `path`: where to keep it."""
    global _db, _path
    _db, _path = None, path
    _kicked.clear()


def _count():
    db = _load()
    return (len(db["roles"]) + sum(len(v) for v in db["bans"].values())
            + sum(len(v) for v in db["mutes"].values()))


# -- who someone is ---------------------------------------------------------------

def holder(cid):
    """The identity a role is held by: "h:<LXMF address>" or "p:<profile>",
    or None (a guest: no role)."""
    s = str(cid or "")
    if rrc._is_lxmf(s):
        return "h:" + s
    lx = rrc.lxmf_of(s)
    if lx:
        return "h:" + lx
    if s.startswith("p:") and len(s) > 2:
        return s
    return None


def _key(cid):
    """For a ban or a mute: an identity, else the guest's own visit ("c:"),
    else someone on another Stump ("r:@<stump>:<nick>")."""
    s = str(cid or "")
    if s.startswith("@"):
        return "r:" + s
    return holder(s) or ("c:" + s)


def _short(key):
    """How a key shows: a hash's first 8, a profile's name."""
    if key.startswith("h:"):
        return key[2:10]
    if key.startswith("p:"):
        return "profile " + key[2:]
    if key.startswith("r:"):
        return key[2:].split(":", 1)[-1]
    return "guest"


def _scopes_cover(scopes, room):
    return STUMP in scopes or room in scopes


def _here(scope):
    """What rank() is asked for a scope: a room, or for "-stump" a name no
    room has (so only a role in every room covers it)."""
    return "\x00" if scope == STUMP else scope


def rank(cid, room):
    """"op", "mod" or None, for this person in this room. Over LoRa, only
    once their messages check out: a message an open Stump can't check
    yet (no announce heard) could be anyone's (1.0.0-beta.71)."""
    if rrc._is_lxmf(str(cid or "")):
        try:
            import rrc_mesh
            if rrc_mesh.unproved(cid):
                return None
        except ImportError:
            pass
    k = holder(cid)
    r = _load()["roles"].get(k) if k else None
    if not r:
        return None
    if _scopes_cover(r.get("op", []), room):
        return "op"
    if _scopes_cover(r.get("mod", []), room):
        return "mod"
    return None


def _rank_key(key, room):
    room = _here(room) if room == STUMP else room
    r = _load()["roles"].get(key)
    if not r:
        return None
    if _scopes_cover(r.get("op", []), room):
        return "op"
    if _scopes_cover(r.get("mod", []), room):
        return "mod"
    return None


def mark(cid, room):
    """"@" for an op, "%" for a mod (their nick in /names), else ""."""
    return {"op": "@", "mod": "%"}.get(rank(cid, room), "")


# -- what they may do ---------------------------------------------------------------

def _listed(table, key, room, now):
    db = _load()[table]
    for scope in (room, STUMP):
        e = (db.get(scope) or {}).get(key)
        if e is None:
            continue
        until = e.get("until")
        if until and now >= until:
            del db[scope][key]
            if not db[scope]:
                del db[scope]
            _save()
            continue
        return e
    return None


def _keys_of(cid):
    """Every key that may name this person (their identity, and their visit)."""
    out = []
    h = holder(cid)
    if h:
        out.append(h)
    out.append("c:" + str(cid))
    return out


def banned(cid, room, now=None):
    now = time.time() if now is None else now
    return any(_listed("bans", k, rrc.canon(room), now) for k in _keys_of(cid))


def muted(cid, room, now=None):
    now = time.time() if now is None else now
    return any(_listed("mutes", k, rrc.canon(room), now) for k in _keys_of(cid))


def kicked(cid, room, now=None):
    now = time.time() if now is None else now
    room = rrc.canon(room)
    for k in _keys_of(cid):
        t = _kicked.get((k, room))
        if t is not None:
            if now < t:
                return True
            del _kicked[(k, room)]
    return False


def total(cid, now=None):
    """Banned from this Stump's chat altogether: banned in #main or with
    "-stump" (#main is the way in). No room, nothing to read, no line, no
    private message -- only /help, and the admin's own commands."""
    now = time.time() if now is None else now
    for k in _keys_of(cid):
        if _listed("bans", k, STUMP, now) or _listed("bans", k, rrc.DEFAULT_ROOM, now):
            return True
    return False


def total_refusal(cid, lang="en"):
    if total(cid):
        return i18n.t("mod_you_banned_all", lang)
    return None


def join_refusal(cid, room, lang="en"):
    """Why this person can't be in this room now, or None."""
    room = rrc.canon(room)
    if total(cid):
        return i18n.t("mod_you_banned_all", lang)
    if room == rrc.DEFAULT_ROOM:
        return None                     # #main: everyone's way back in (but a total ban)
    if banned(cid, room):
        return i18n.t("mod_you_banned", lang, room=room)
    if kicked(cid, room):
        return i18n.t("mod_you_kicked", lang, room=room)
    return None


def write_refusal(cid, room, lang="en"):
    """Why this person can't write in this room now, or None."""
    room = rrc.canon(room)
    if banned(cid, room):
        return i18n.t("mod_you_banned", lang, room=room)
    if muted(cid, room):
        return i18n.t("mod_you_muted", lang, room=room)
    if kicked(cid, room):
        return i18n.t("mod_you_kicked", lang, room=room)
    return None


def topic_locked(room):
    return rrc.canon(room) in _load()["t"]


def topic_refusal(cid, room, lang="en"):
    """+t: the topic only by an op or a mod."""
    if topic_locked(room) and rank(cid, rrc.canon(room)) is None:
        return i18n.t("mod_topic_locked", lang, room=rrc.canon(room))
    return None


def remote_hidden(room, nick, via):
    """A line from someone on another Stump ("nick@stump" from Stump
    `via`) that's muted or banned here: not shown."""
    base = str(nick).split("@", 1)[0].lower()
    key = "r:@%s:%s" % (via, base)
    now = time.time()
    room = rrc.canon(room)
    return bool(_listed("bans", key, room, now) or _listed("mutes", key, room, now))


# -- the commands ---------------------------------------------------------------------

COMMANDS = ("op", "deop", "mod", "demod", "kick", "mute", "unmute", "ban", "unban", "bans", "mode", "roles")


def is_command(text):
    if text[:1] != "/":
        return False
    return text[1:].split(" ", 1)[0].lower() in COMMANDS


def _scope(tok):
    """"#room" (one that exists) or "-stump" -> (scope, None) or (None, why)."""
    if tok == "-stump":
        return STUMP, None
    if tok.startswith("#"):
        name = rrc.canon(rrc.clean_room(tok[1:]) or "")
        if name and rrc.room_exists(name):
            return name, None
        return None, "mod_no_room"
    return None, "mod_scope"


def _where(scope, lang):
    return i18n.t("mod_everywhere", lang) if scope == STUMP else "#" + scope


def _people_here():
    """(cid, nick) for everyone this Stump can name: here, and reachable."""
    out = []
    for table in (rrc._users, rrc._reachable):
        for cid, u in list(table.items()):
            if cid not in rrc._hidden:
                out.append((cid, u["nick"]))
    return out


def _resolve(tok):
    """A person by nick, nick@stump, or the start of their hash (6+ hex):
    (cid, nick) or (None, ambiguous list or None)."""
    t = tok.lstrip("~@").strip()
    low = t.lower()
    if not t:
        return None, None
    hits = []
    for cid, nick in _people_here():
        if nick.lower() == low:
            hits.append((cid, nick))
    if not hits and len(low) >= 6 and all(c in "0123456789abcdef" for c in low):
        for cid, nick in _people_here():
            lx = cid if rrc._is_lxmf(cid) else rrc.lxmf_of(cid)
            if lx and lx.startswith(low):
                hits.append((cid, nick))
    seen, uniq = set(), []
    for cid, nick in hits:
        k = _key(cid)
        if k not in seen:
            seen.add(k)
            uniq.append((cid, nick))
    if len(uniq) == 1:
        return uniq[0]
    return None, (uniq or None)


def _stored(tok, table):
    """Someone in a stored list (to /deop, /unban, /unmute someone who
    isn't here): by the nick it was given under, or the start of the key."""
    low = tok.lstrip("~@").lower()
    hits = set()
    db = _load()
    if table == "roles":
        for k, e in db["roles"].items():
            if e.get("label", "").lower() == low or (len(low) >= 6 and k[2:].startswith(low)):
                hits.add(k)
    else:
        for scope, entries in db[table].items():
            for k, e in entries.items():
                if e.get("label", "").lower() == low or (len(low) >= 6 and k[2:].startswith(low)):
                    hits.add(k)
    return list(hits)


def _target(tok, table, lang):
    """(key, label, cid or None) or (None, error lines, None)."""
    cid, info = _resolve(tok)
    if cid is not None:
        return _key(cid), info, cid
    if info:
        return None, [i18n.t("mod_ambiguous", lang, who=tok,
                             list=", ".join("%s (%s)" % (n, _short(_key(c))) for c, n in info))], None
    ks = _stored(tok, table)
    if len(ks) == 1:
        k = ks[0]
        return k, _label_of(k) or tok, None
    if len(ks) > 1:
        return None, [i18n.t("mod_ambiguous", lang, who=tok, list=", ".join(_short(k) for k in ks))], None
    return None, [rrc.no_such(tok)], None


def _label_of(key):
    db = _load()
    e = db["roles"].get(key)
    if e:
        return e.get("label")
    for table in ("bans", "mutes"):
        for entries in db[table].values():
            if key in entries:
                return entries[key].get("label")
    return None


def _nick(cid):
    u = rrc._users.get(cid) or rrc._reachable.get(cid)
    return u["nick"] if u else "?"


def _note(scope, text):
    """Said in the room it happened in (or #main, for every room)."""
    rrc.system(rrc.DEFAULT_ROOM if scope == STUMP else scope, text)


def _move_out(cid, room):
    """Out of this room, back to #main (a mesh peer's room too)."""
    u = rrc._users.get(cid)
    if not u or rrc.canon(u.get("room")) != room:
        return
    rrc.system(room, rrc.ev_leave(u["nick"]))
    rrc.touch_user(cid, room=rrc.DEFAULT_ROOM)
    try:
        import rrc_mesh
        p = rrc_mesh._peers.get(cid)
        if p is not None and p.get("room") == room:
            p["room"] = rrc.DEFAULT_ROOM
    except Exception:
        pass


def _shut_out(cid):
    """Out of every room and off the lists (a total ban)."""
    u = rrc._users.get(cid)
    if u:
        rrc.system(u["room"], rrc.ev_leave(u["nick"]))
        rrc._users.pop(cid, None)
    try:
        import rrc_mesh
        p = rrc_mesh._peers.get(cid)
        if p is not None and not p.get("stump"):
            p["room"] = rrc.DEFAULT_ROOM
    except Exception:
        pass


def _tell(cid, text):
    """A private word to the person acted on (on the mesh: as a DM)."""
    if rrc._is_lxmf(str(cid)):
        try:
            import rrc_mesh
            rrc_mesh.notify(cid, text)
        except Exception:
            pass


def command(client_id, room, text, lang):
    """/op /deop /mod /demod /kick /mute /unmute /ban /unban /bans /mode
    /roles. Returns (reply_lines, None)."""
    parts = text.split()
    cmd = parts[0][1:].lower()
    args = parts[1:]
    usage = [i18n.t("mod_usage_" + cmd, lang)]
    if cmd == "roles":
        return _roles(args, lang), None
    # The admin: the password first (/op and /deop: only the admin).
    admin = False
    # Only where a room or "-stump" follows (so "/kick Zoe", a room
    # forgotten, isn't taken as a wrong password and counted).
    scopey = lambda a: a.startswith("#") or a.startswith("-")
    if (cmd in ("op", "deop") or (len(args) >= 2 and not scopey(args[0]) and scopey(args[1]))
            or (cmd == "bans" and args and not scopey(args[0]))):
        if not args:
            return usage, None
        import rooms
        if not rooms._pw_ok(args[0], client_id):
            return ["✗ " + i18n.t("room_bad_pw", lang)], None
        admin, args = True, args[1:]
    if cmd == "bans":
        return _bans(client_id, args, admin, lang), None
    if not args:
        return usage, None
    scope, why = _scope(args[0])
    if scope is None:
        return [i18n.t(why, lang, room=args[0].lstrip("#")), usage[0]], None
    # Their role here ("-stump": only a role in every room covers it).
    me = rank(client_id, _here(scope))
    by = "admin" if admin else _nick(client_id)
    if cmd == "mode":
        return _mode(client_id, scope, args[1:], admin or me == "op", by, lang), None
    if len(args) < 2:
        return usage, None
    need = {"mod": "op", "demod": "op", "kick": "mod", "mute": "mod", "unmute": "mod",
            "ban": "op", "unban": "op", "op": "admin", "deop": "admin"}[cmd]
    if not admin and (me is None or (need == "op" and me != "op") or need == "admin"):
        return ["✗ " + i18n.t("mod_not_allowed", lang, where=_where(scope, lang))], None
    table = {"op": "roles", "deop": "roles", "mod": "roles", "demod": "roles",
             "ban": "bans", "unban": "bans", "mute": "mutes", "unmute": "mutes", "kick": None}[cmd]
    key, label, cid = _target(args[1], table or "bans", lang)
    if key is None:
        return label, None
    if cid is not None and cid == client_id and not admin:
        return [i18n.t("mod_not_self", lang)], None
    # Not on someone of the same rank or above (the admin: anyone) -- for
    # what acts against them (kick, mute, ban). Naming a mod, or lifting a
    # mute or a ban, harms no one: an op of every room may make a mod of
    # someone who's op in one room (1.0.0-beta.69).
    if not admin and cmd in ("kick", "mute", "ban"):
        theirs = _rank_key(key, scope)
        if scope == STUMP:
            # Every room: not on anyone who's op or mod in any of them.
            rr = _load()["roles"].get(key, {})
            theirs = "op" if rr.get("op") else "mod" if rr.get("mod") else None
        if theirs == "op" or (theirs == "mod" and me != "op"):
            return ["✗ " + i18n.t("mod_not_on", lang, who=label)], None
    rest = args[2:]
    if cmd == "kick" and key.startswith("r:"):
        return [i18n.t("mod_kick_remote", lang, who=label)], None
    if cmd in ("op", "mod"):
        return _grant(cmd, key, label, cid, scope, by, lang), None
    if cmd in ("deop", "demod"):
        return _ungrant(cmd[2:], key, label, scope, by, lang), None
    if cmd == "kick":
        return _kick(key, label, cid, scope, by, " ".join(rest), lang), None
    if cmd in ("ban", "mute"):
        return _list_add(cmd, key, label, cid, scope, by, rest, lang), None
    return _list_del(cmd[2:], key, label, scope, by, lang), None


def _grant(role, key, label, cid, scope, by, lang):
    if not key.startswith(("h:", "p:")):
        return [i18n.t("mod_needs_identity", lang, who=label)]
    db = _load()
    e = db["roles"].get(key)
    if e is None:
        if _count() >= MAX_ENTRIES:
            return [i18n.t("mod_full", lang)]
        e = db["roles"][key] = {"label": label, "op": [], "mod": []}
    e["label"] = label
    if scope in e[role]:
        return [i18n.t("mod_already", lang, who=label, role=role, where=_where(scope, lang))]
    e[role].append(scope)
    e["by"] = by
    _save()
    _note(scope, ("@ " if role == "op" else "% ") + label + " ⟵ " + by + ("" if scope != STUMP else " (-stump)"))
    if cid is not None:
        _tell(cid, i18n.t("mod_you_" + role, lang, where=_where(scope, lang), by=by))
    return ["✓ " + i18n.t("mod_granted", lang, who=label, role=role, where=_where(scope, lang))]


def _ungrant(role, key, label, scope, by, lang):
    db = _load()
    e = db["roles"].get(key)
    if not e or scope not in e.get(role, []):
        return [i18n.t("mod_not_role", lang, who=label, role=role, where=_where(scope, lang))]
    e[role].remove(scope)
    if not e["op"] and not e["mod"]:
        del db["roles"][key]
    _save()
    _note(scope, ("@✗ " if role == "op" else "%✗ ") + label + " ⟵ " + by)
    return ["✓ " + i18n.t("mod_removed", lang, who=label, role=role, where=_where(scope, lang))]


def _kick(key, label, cid, scope, by, reason, lang):
    if scope == STUMP:
        return [i18n.t("mod_kick_room", lang)]
    if scope == rrc.DEFAULT_ROOM:
        return [i18n.t("mod_kick_main", lang)]
    _kicked[(key, scope)] = time.time() + KICK_S
    if len(_kicked) > 200:
        now = time.time()
        for k in [k for k, t in _kicked.items() if t <= now]:
            del _kicked[k]
    if cid is not None:
        _move_out(cid, scope)
        _tell(cid, i18n.t("mod_you_kicked_by", lang, room=scope, by=by, why=reason or "-"))
    _note(scope, "⊖ " + label + " ⟵ " + by + (": " + reason[:80] if reason else ""))
    return ["✓ " + i18n.t("mod_kicked", lang, who=label, room=scope)]


def _list_add(what, key, label, cid, scope, by, rest, lang):
    until = None
    if what == "mute" and rest:
        try:
            m = int(rest[0])
        except ValueError:
            return [i18n.t("mod_usage_mute", lang)]
        if not 1 <= m <= MUTE_MAX_MIN:
            return [i18n.t("mod_usage_mute", lang)]
        until = time.time() + m * 60
    table = "bans" if what == "ban" else "mutes"
    db = _load()
    entries = db[table].setdefault(scope, {})
    if key not in entries and _count() >= MAX_ENTRIES:
        return [i18n.t("mod_full", lang)]
    entries[key] = {"label": label, "by": by, "at": int(time.time())}
    if until:
        entries[key]["until"] = int(until)
    _save()
    if what == "ban" and cid is not None:
        if scope in (STUMP, rrc.DEFAULT_ROOM):
            _shut_out(cid)               # a total ban: out of the chat altogether
        else:
            _move_out(cid, scope)
    mins = (" (%d min)" % int(rest[0])) if until else ""
    _note(scope, ("⊘ " if what == "ban" else "⧗ ") + label + " ⟵ " + by + mins + (" (-stump)" if scope == STUMP else ""))
    if cid is not None:
        _tell(cid, i18n.t("mod_you_" + what + "ned_by" if what == "ban" else "mod_you_muted_by", lang,
                          where=_where(scope, lang), by=by))
    out = ["✓ " + i18n.t("mod_" + what + "ned" if what == "ban" else "mod_muted", lang,
                         who=label, where=_where(scope, lang)) + mins]
    if key.startswith("c:"):
        out.append(i18n.t("mod_guest_note", lang))
    return out


def _list_del(what, key, label, scope, by, lang):
    table = "bans" if what == "ban" else "mutes"
    db = _load()
    entries = db[table].get(scope) or {}
    if key not in entries:
        return [i18n.t("mod_not_" + what + "ned" if what == "ban" else "mod_not_muted", lang,
                       who=label, where=_where(scope, lang))]
    del entries[key]
    if not entries:
        db[table].pop(scope, None)
    _save()
    _note(scope, ("⊘✓ " if what == "ban" else "⧗✓ ") + label + " ⟵ " + by)
    return ["✓ " + i18n.t("mod_un" + what + "ned" if what == "ban" else "mod_unmuted", lang,
                         who=label, where=_where(scope, lang))]


def _mode(client_id, scope, rest, may, by, lang):
    if scope == STUMP:
        return [i18n.t("mod_usage_mode", lang)]
    t = topic_locked(scope)
    if not rest:
        return [i18n.t("mod_mode_is", lang, room=scope, modes="+t" if t else "-")]
    if rest[0] not in ("+t", "-t"):
        return [i18n.t("mod_usage_mode", lang)]
    if not may:
        return ["✗ " + i18n.t("mod_not_allowed", lang, where="#" + scope)]
    want = rest[0] == "+t"
    db = _load()
    if want and scope not in db["t"]:
        db["t"].append(scope)
    elif not want and scope in db["t"]:
        db["t"].remove(scope)
    else:
        return [i18n.t("mod_mode_is", lang, room=scope, modes="+t" if t else "-")]
    _save()
    rrc.system(scope, "✎ #" + scope + " " + rest[0] + " ⟵ " + by)
    return ["✓ " + i18n.t("mod_mode_is", lang, room=scope, modes="+t" if want else "-")]


def _roles(args, lang):
    """Who's op or mod (anyone may ask): in one room, or all."""
    want = None
    if args:
        scope, why = _scope(args[0])
        if scope is None:
            return [i18n.t(why, lang, room=args[0].lstrip("#"))]
        want = scope
    lines = []
    for k, e in sorted(_load()["roles"].items(), key=lambda kv: kv[1].get("label", "").lower()):
        for role, mk in (("op", "@"), ("mod", "%")):
            sc = [s for s in e.get(role, []) if want is None or s == want or s == STUMP]
            if sc:
                lines.append("%s%s (%s): %s" % (mk, e.get("label", "?"), _short(k),
                                                ", ".join(_where(s, lang) for s in sorted(sc))))
    return lines or [i18n.t("mod_no_roles", lang)]


def _bans(client_id, args, admin, lang):
    """The bans and mutes (an op's or a mod's, in their rooms; the admin's: all)."""
    want = None
    if args:
        scope, why = _scope(args[0])
        if scope is None:
            return [i18n.t(why, lang, room=args[0].lstrip("#"))]
        want = scope
    lines, now = [], time.time()
    db = _load()
    for table, mk in (("bans", "⊘"), ("mutes", "⧗")):
        for scope in sorted(db[table]):
            if want is not None and scope != want:
                continue
            if not admin and rank(client_id, _here(scope)) is None:
                continue
            for k, e in db[table][scope].items():
                left = ""
                if e.get("until"):
                    if now >= e["until"]:
                        continue
                    left = " (%d min)" % max(1, int((e["until"] - now) / 60))
                lines.append("%s %s (%s) %s, %s%s" % (mk, e.get("label", "?"), _short(k), _where(scope, lang), e.get("by", "?"), left))
    return lines or [i18n.t("mod_none_listed", lang)]

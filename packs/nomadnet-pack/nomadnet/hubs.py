# Joining other RRC hubs from the Stump: another community's NomadNet chat
# (an rrcd hub, or another Stump's) bridged into rooms here. The admin adds
# a hub and the rooms to join (/admin, section "NomadNet hubs"); each
# becomes a room on the Stump named "<room>-<hub>", and everything said
# there goes both ways: the hub's people show here as "zoe@aleph", the
# Stump's people there as "rod@<this Stump>".
#
# The Stump is one client of the hub (its own identity, proved on the
# link); each line carries the speaker's nick, which RRC clients show
# (K_NICK). Its own lines coming back from the hub are recognised by
# their sender (the Stump's identity) and not posted twice.

import time
from . import cbor
from .hub import (K_V, K_T, K_ID, K_TS, K_SRC, K_ROOM, K_BODY, K_NICK, T_HELLO, T_WELCOME, T_JOIN,
                  T_JOINED, T_PARTED, T_MSG, T_NOTICE, T_ACTION, T_PING, T_PONG, T_ERROR, _cut, _now_ms)

HUBS_MAX = 4
ROOMS_PER_HUB = 4
RETRY_S = 60
PER_TICK = 4

_api = []
_hubs = []          # [Hub]
_file = [None]


class Hub:
    def __init__(self, hexhash, name, rooms):
        self.hex = hexhash
        self.name = name
        self.rooms = {r: _local_name(r, name) for r in rooms}     # remote room -> local room
        self.remote = None
        self.state = "off"          # off, hello, on
        self.next_try = 0
        self.last = {}              # local room -> last id sent to the hub
        self.posted = set()         # ids of lines the bridge posted here (never sent back)
        self.status = ""
        self.max_body = 350

    def to_dict(self):
        return {"hub": self.hex, "name": self.name, "rooms": list(self.rooms)}


def _local_name(room, hubname):
    import rrc
    return rrc.clean_room(room + "-" + hubname)[:24]


def _own():
    import plugins
    i = plugins._net[0]
    return i.hash if i is not None else b"\x00" * 16


def _stump_name():
    import rrc
    return (rrc.NODE or {}).get("name") or "Stump"


def setup(stump):
    _api.append(stump)
    _file[0] = stump.storage_file("hubs.json")
    _load()
    stump.every(1, tick)
    stump.admin_panel(lambda lang: stump.t("hubs_title", lang), _panel, _panel_post)
    stump.page("hubs", _hubs_page)


def _load():
    try:
        import ujson as json
    except ImportError:
        import json
    try:
        with open(_file[0]) as f:
            for d in json.load(f)[:HUBS_MAX]:
                _hubs.append(Hub(d["hub"], d["name"], d.get("rooms", [])[:ROOMS_PER_HUB]))
    except Exception:
        pass


def _save():
    try:
        import store
        store.save_json(_file[0], [h.to_dict() for h in _hubs], "nomadnet")
    except Exception:
        pass


def _env(t, room=None, body=None, nick=None):
    e = {K_V: 1, K_T: t, K_ID: __import__("os").urandom(8), K_TS: _now_ms(), K_SRC: _own()}
    if room is not None:
        e[K_ROOM] = room
    if body is not None:
        e[K_BODY] = body
    if nick:
        e[K_NICK] = nick
    return cbor.dumps(e)


def _packet(h, data):
    import rrc
    try:
        env = cbor.loads(data)
    except Exception:
        return
    if not isinstance(env, dict):
        return
    t = env.get(K_T)
    room = env.get(K_ROOM) if isinstance(env.get(K_ROOM), str) else None
    local = h.rooms.get(room.strip().lower()) if room else None
    body = env.get(K_BODY)
    nick = env.get(K_NICK) if isinstance(env.get(K_NICK), str) else ""
    if t == T_PING:
        h.remote.send(_env(T_PONG, body=body))
    elif t == T_WELCOME:
        h.state = "on"
        if isinstance(body, dict) and isinstance(body.get(3), dict) and isinstance(body[3].get(2), int):
            h.max_body = max(64, min(400, body[3][2]))
        if isinstance(body, dict) and isinstance(body.get(0), str):
            h.status = body[0][:40]
        for r, loc in h.rooms.items():
            rrc.create_room(loc)
            if not rrc.topic(loc):
                rrc.set_topic(loc, (h.name + " #" + r + " (NomadNet)")[:120])
            h.last[loc] = _latest(loc)
            h.remote.send(_env(T_JOIN, room=r, nick=_stump_name()))
    elif t in (T_MSG, T_ACTION) and local and isinstance(body, str):
        if env.get(K_SRC) == _own():
            return                                     # our own line, back from the hub
        who = (nick or "?")[:16] + "@" + h.name
        m = rrc.post(local, who, body, kind="msg" if t == T_MSG else "action")
        if m:
            h.posted.add(m["id"])
    elif t in (T_JOINED, T_PARTED) and local and nick and env.get(K_SRC) != _own():
        m = rrc.system(local, (rrc.ev_join if t == T_JOINED else rrc.ev_leave)(nick[:16] + "@" + h.name))
        if m:
            h.posted.add(m["id"])
    elif t in (T_NOTICE, T_ERROR) and isinstance(body, str):
        target = local or next(iter(h.rooms.values()), None)
        if target and rrc.room_exists(target):
            m = rrc.system(target, _cut(body, 300))
            if m:
                h.posted.add(m["id"])


def _latest(room):
    import rrc
    m = rrc.since(room, 0)
    return m[-1]["id"] if m else 0


def _connect(h):
    h.remote = _api[0].connect(h.hex, "rrc", ("hub",), identify=True)
    h.remote.on_packet(lambda data: _packet(h, data))
    h.remote.on_close(lambda: _closed(h))
    h.state = "hello"
    h.status = ""
    body = {0: "stump", 1: "0.1", 2: {0: False, 1: True}}
    h.remote.send(_env(T_HELLO, body=body, nick=_stump_name()))


def _closed(h):
    h.state = "off"
    h.next_try = time.time() + RETRY_S


def tick():
    import rrc
    now = time.time()
    for h in _hubs:
        if h.state == "off":
            if now >= h.next_try:
                h.next_try = now + RETRY_S
                _connect(h)
            continue
        if h.state != "on" or not h.remote.is_open():
            continue
        for r, loc in h.rooms.items():
            sent = 0
            for m in rrc.since(loc, h.last.get(loc, 0)):
                h.last[loc] = m["id"]
                if m["id"] in h.posted:
                    h.posted.discard(m["id"])
                    continue
                kind = m.get("kind")
                if kind not in ("msg", "action", "me"):
                    continue
                nick = (m.get("nick") or "?") + "@" + _stump_name()
                h.remote.send(_env(T_MSG if kind == "msg" else T_ACTION, room=r,
                                   body=_cut(m.get("body") or "", h.max_body - 8), nick=nick[:32]))
                sent += 1
                if sent >= PER_TICK:
                    break
        if len(h.posted) > 200:
            h.posted = set(sorted(h.posted)[-100:])


# ── /admin: the hubs this Stump joins ────────────────────────────────

def _t(lang, key, **kw):
    return _api[0].t(key, lang, **kw)


def _panel(lang, hidden):
    e = _api[0].esc
    out = ["<p class='sub'>" + e(_t(lang, "hubs_intro")) + "</p>"]
    if _hubs:
        out.append("<div class='panel'><ul class='plist'>")
        for i, h in enumerate(_hubs):
            st = _t(lang, "hubs_on", name=h.status or h.name) if h.state == "on" else _t(lang, "hubs_off")
            out.append("<li><div><span class='pname'>" + e(h.name) + "</span> <small>&lt;" + h.hex[:8] + "&gt; · "
                       + e(st) + "</small><br><small>" + e(", ".join("#" + r + " → #" + l for r, l in h.rooms.items()))
                       + "</small></div><form method='POST' action='/admin/panel'>" + hidden
                       + "<input type='hidden' name='remove' value='" + str(i) + "'><button type='submit'>"
                       + e(_t(lang, "hubs_remove")) + "</button></form></li>")
        out.append("</ul></div>")
    if len(_hubs) < HUBS_MAX:
        out.append("<form method='POST' action='/admin/panel' class='post-form'>" + hidden
                   + "<label>" + e(_t(lang, "hubs_address")) + "<br><input name='hub' maxlength='32' size='34' required></label>"
                   + "<label>" + e(_t(lang, "hubs_name")) + "<br><input name='name' maxlength='12' required></label>"
                   + "<label>" + e(_t(lang, "hubs_rooms")) + "<br><input name='rooms' value='main'></label>"
                   + "<button type='submit'>" + e(_t(lang, "hubs_add")) + "</button></form>")
    return "".join(out)


def _panel_post(fields, lang):
    import rrc
    if "remove" in fields:
        try:
            h = _hubs.pop(int(fields["remove"]))
        except (ValueError, IndexError):
            return None
        if h.remote:
            h.remote.close()
        _save()
        return _t(lang, "hubs_removed", name=h.name)
    hx = (fields.get("hub") or "").strip().lower()
    if hx.startswith("rrc://"):
        hx = hx[6:]
    hx, _, room_in_link = hx.partition("/")
    name = rrc.clean_room(fields.get("name") or "")[:12]
    rooms = [rrc.clean_room(r.strip().lstrip("#")) for r in (fields.get("rooms") or room_in_link or "main").split(",")]
    rooms = [r for r in rooms if r][:ROOMS_PER_HUB]
    if len(hx) != 32 or any(c not in "0123456789abcdef" for c in hx) or not name or not rooms:
        return _t(lang, "hubs_bad")
    if len(_hubs) >= HUBS_MAX or any(h.hex == hx for h in _hubs):
        return _t(lang, "hubs_bad")
    _hubs.append(Hub(hx, name, rooms))
    _save()
    return _t(lang, "hubs_added", name=name)


def _hubs_page(req):
    """Where an rrc:// link on a browsed NomadNet page leads: what it is,
    and how the admin adds it."""
    e = _api[0].esc
    add = (req.query.get("add") or "")[:80]
    t = lambda k, **kw: _api[0].t(k, req.lang, **kw)
    out = ["<h1>" + e(t("hubs_title")) + "</h1>"]
    if add:
        out.append("<div class='panel'><p>" + e(t("hubs_link", link="rrc://" + add)) + "</p></div>")
    if _hubs:
        out.append("<p class='sub'>" + e(t("hubs_in_chat")) + " <a href='/rrc'>" + e(t("hubs_chat")) + "</a></p><ul class='files'>" + "".join("<li><b>" + e(h.name) + "</b>: "
                   + ", ".join("<code>/join #" + e(l) + "</code>" for l in h.rooms.values())
                   + "</li>" for h in _hubs) + "</ul>")
    return "".join(out)

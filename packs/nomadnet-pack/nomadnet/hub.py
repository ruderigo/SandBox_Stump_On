# The Stump as an RRC hub: NomadNet's own chat (Channels) joins the
# Stump's rooms. RRC is rrcd's protocol (github.com/kc1awv/rrcd), as
# NomadNet's client speaks it (nomadnet/RRC.py): a link to an "rrc.hub"
# destination, the client identifies, then CBOR envelopes,
#   {0: version 1, 1: type, 2: id, 3: ms, 4: sender's identity hash,
#    5: room, 6: body, 7: nick}
# HELLO -> WELCOME (name, version, capabilities, limits); JOIN -> JOINED;
# PART -> PARTED; MSG / ACTION both ways; NOTICE from the hub (/list,
# /who, replies); PING -> PONG. The rooms are the Stump's own: what's
# said on the web, over LXMF or by FireFly reaches NomadNet, and back.

import time, os
from . import cbor

K_V, K_T, K_ID, K_TS, K_SRC, K_ROOM, K_BODY, K_NICK = 0, 1, 2, 3, 4, 5, 6, 7
T_HELLO, T_WELCOME = 1, 2
T_JOIN, T_JOINED, T_PART, T_PARTED = 10, 11, 12, 13
T_MSG, T_NOTICE, T_ACTION = 20, 21, 22
T_PING, T_PONG = 30, 31
T_ERROR = 40

MAX_BODY = 300          # bytes of text per envelope (a link packet holds ~380 with the rest)
MAX_ROOMS = 8           # rooms one session may join
PER_TICK = 4            # lines sent per room per second (airtime over LoRa)
HISTORY = 10            # lines a JOIN gets from before
SESSIONS_MAX = 12

_sessions = []
_api = []


def _now_ms():
    import sys
    t = time.time() + (946684800 if sys.platform == "esp32" else 0)
    return int(t * 1000)


def _cut(text, n=MAX_BODY):
    b = str(text).encode("utf-8")
    if len(b) <= n:
        return str(text)
    return b[:n].decode("utf-8", "ignore") + "…"


def _pseudo(nick):
    """A stable 16-byte stand-in for people with no identity here (the web,
    other Stumps): RRC names a sender by its identity hash."""
    from urns.crypto.hashes import sha256
    return sha256(("stump-nick:" + str(nick).lower()).encode())[:16]


def _env(t, room=None, body=None, nick=None, src=b"\x00" * 16):
    e = {K_V: 1, K_T: t, K_ID: os.urandom(8), K_TS: _now_ms(), K_SRC: src}
    if room is not None:
        e[K_ROOM] = room
    if body is not None:
        e[K_BODY] = body
    if nick:
        e[K_NICK] = nick
    return cbor.dumps(e)


class HubSession:
    def __init__(self, s, hub_src):
        self.s = s
        self.hub_src = hub_src
        self.cid = None
        self.nick = None
        self.rooms = {}         # room -> last message id sent
        self.last_dm = 0
        self.welcomed = False
        self.seen = time.time()

    def send(self, t, **kw):
        return self.s.send(_env(t, **kw))

    def notice(self, text, room=None):
        self.send(T_NOTICE, room=room, body=_cut(text), src=self.hub_src)

    def error(self, text, room=None):
        self.send(T_ERROR, room=room, body=_cut(text), src=self.hub_src)


def _t(key, **kw):
    import i18n
    return _api[0].t(key, i18n.DEFAULT_LANG, **kw)


def on_link(session):
    from . import install as nn
    _api[:] = nn._api[:1]
    while len(_sessions) >= SESSIONS_MAX:
        _drop(_sessions[0])
    hs = HubSession(session, nn._hub_src())
    session.on_packet(lambda data: _packet(hs, data))
    _sessions.append(hs)


def _packet(hs, data):
    from . import install as nn
    try:
        env = cbor.loads(data)
    except Exception:
        return
    if not isinstance(env, dict):
        return
    t = env.get(K_T)
    hs.seen = time.time()
    if t == T_PING:
        hs.send(T_PONG, body=env.get(K_BODY), src=hs.hub_src)
        return
    if t == T_HELLO:
        _hello(hs, env)
        return
    if not hs.welcomed:
        hs.error(_t("hub_hello_first"))
        return
    room = env.get(K_ROOM)
    room = nn._canon(room) if isinstance(room, str) and room.strip() else None
    body = env.get(K_BODY)
    if t == T_JOIN and room:
        _join(hs, room)
    elif t == T_PART and room:
        _part(hs, room)
    elif t == T_MSG and isinstance(body, str):
        if body.startswith("/"):
            _command(hs, room, body)
        elif room in hs.rooms:
            _say(hs, room, body)
        else:
            hs.error(_t("hub_not_in"), room)
    elif t == T_ACTION and isinstance(body, str) and room in hs.rooms:
        _say(hs, room, "/me " + body)


def _hello(hs, env):
    import rrc
    from . import install as nn
    who = hs.s.remote_hex()
    if not who:
        hs.error(_t("hub_identify"))
        return
    hs.cid = nn._lxmf_of(who)
    want = env.get(K_NICK) if isinstance(env.get(K_NICK), str) else ""
    nick = rrc.clean_nick(want)[:16] if want else ""
    if not nick or rrc.nick_taken(nick, hs.cid):
        nick = nn._nick_for(hs.cid)
    hs.nick = nick
    hs.src = bytes.fromhex(who)
    rrc.touch_user(hs.cid, nick=nick, room=rrc.MESH_ROOM)
    try:
        hs.last_dm = max([m["id"] for m in rrc.dms_since(hs.cid, 0)] or [0])
    except Exception:
        hs.last_dm = 0
    hs.welcomed = True
    import config
    rel = ""
    try:
        rel = (rrc.NODE_INFO or {}).get("release") or ""
    except Exception:
        pass
    hs.send(T_WELCOME, body={0: nn._name(), 1: "stump " + rel, 2: {0: False, 1: True},
                             3: {0: 16, 1: 32, 2: MAX_BODY, 3: MAX_ROOMS, 4: 30}}, src=hs.hub_src)
    greet = getattr(config, "MESH_GREETING", "") or ""
    hs.notice((greet + "\n" if greet else "") + _t("hub_motd", nick=nick))


def _join(hs, room):
    import rrc
    from . import install as nn
    if not nn._on("chat") or room not in nn._room_list() or not nn._may_read(hs.cid):
        hs.error(_t("no_room"), room)
        return
    try:
        import mods
        no = mods.join_refusal(hs.cid, room)
    except Exception:
        no = None
    if no:
        hs.error(no, room)                       # banned or kicked (mods.py)
        return
    if room not in hs.rooms and len(hs.rooms) >= MAX_ROOMS:
        hs.error(_t("hub_too_many"), room)
        return
    first = room not in hs.rooms
    if first:
        msgs = rrc.since(room, 0)
        # The last few lines from before, then everything new.
        hs.rooms[room] = msgs[-HISTORY]["id"] - 1 if len(msgs) >= HISTORY else 0
    rrc.touch_user(hs.cid, nick=hs.nick, room=room)
    hs.send(T_JOINED, room=room, body=[hs.src], src=hs.hub_src)
    if first:
        rrc.system(room, rrc.ev_join("~" + hs.nick))


def _part(hs, room):
    import rrc
    if room in hs.rooms:
        del hs.rooms[room]
        rrc.system(room, rrc.ev_leave("~" + hs.nick))
    hs.send(T_PARTED, room=room, body=[hs.src], src=hs.hub_src)


def _say(hs, room, text):
    import rrc
    rrc.touch_user(hs.cid, nick=hs.nick, room=room)
    replies, _ = rrc.handle_input(hs.cid, room, text)
    for r in replies:
        if r and r != "__CLEAR__":
            hs.notice(r, room)


def _command(hs, room, body):
    import rrc
    from . import install as nn
    word = body.split(" ", 1)[0].lower()
    if word == "/list":
        lines = []
        for r in nn._room_list():
            topic = ""
            try:
                topic = rrc.topic(r, None) or ""
            except Exception:
                pass
            lines.append("  " + r + (" - " + topic if topic else ""))
        hs.notice("Registered public rooms:\n" + "\n".join(lines) if lines else "No public rooms registered")
        return
    if word in ("/who", "/names"):
        r = nn._canon(body.split(" ", 1)[1]) if " " in body else room
        if not r or r not in nn._room_list():
            hs.error(_t("no_room"), r)
            return
        names = [n + " (" + _pseudo(n).hex()[:12] + ")" for n in rrc.names_in_room(r)]
        hs.notice("members in " + r + ": " + (", ".join(names) or "(none)"), r)
        return
    _say(hs, room or rrc.MESH_ROOM, body)


def _drop(hs):
    import rrc
    for room in list(hs.rooms):
        try:
            rrc.system(room, rrc.ev_leave("~" + hs.nick))
        except Exception:
            pass
    hs.rooms = {}
    if hs.cid:
        rrc.drop_user(hs.cid)
    if hs in _sessions:
        _sessions.remove(hs)
    hs.s.close()


def tick():
    """Every second: what was said in each joined room since, out to
    each session (a few lines a room, for the radio), and its DMs."""
    import rrc
    now = time.time()
    for hs in list(_sessions):
        if not hs.s.is_open():
            _drop(hs)
            continue
        if not hs.welcomed:
            if now - hs.seen > 60:
                _drop(hs)
            continue
        try:
            import mods
            out = mods.total(hs.cid)
        except Exception:
            out = False
        if out:
            # Banned from the Stump's chat altogether (mods.py): nothing goes to them.
            for room in list(hs.rooms):
                m = rrc.since(room, hs.rooms[room])
                if m:
                    hs.rooms[room] = m[-1]["id"]
            d = rrc.dms_since(hs.cid, hs.last_dm)
            if d:
                hs.last_dm = d[-1]["id"]
            continue
        if now - hs.seen > 30 and hs.rooms:
            rrc.touch_user(hs.cid, nick=hs.nick)       # still here: kept on the roster
            hs.seen = now
        for room, last in list(hs.rooms.items()):
            sent = 0
            for m in rrc.since(room, last):
                hs.rooms[room] = m["id"]
                kind, nick, body = m.get("kind"), m.get("nick") or "", m.get("body") or ""
                if nick == hs.nick and kind in ("msg", "me", "action"):
                    continue                     # its own line: NomadNet shows it already
                if kind == "msg":
                    hs.send(T_MSG, room=room, body=_cut(body), nick=nick, src=_pseudo(nick))
                elif kind in ("me", "action"):
                    hs.send(T_ACTION, room=room, body=_cut(body), nick=nick, src=_pseudo(nick))
                elif kind == "system":
                    hs.send(T_NOTICE, room=room, body=_cut(body), src=hs.hub_src)
                else:
                    continue
                sent += 1
                if sent >= PER_TICK:
                    break
        try:
            dms = rrc.dms_since(hs.cid, hs.last_dm)
        except Exception:
            dms = []
        for m in dms[:PER_TICK]:
            hs.last_dm = m["id"]
            room = next(iter(hs.rooms), None)
            hs.notice(_t("hub_dm", who=m.get("nick") or "?", text=m.get("body") or ""), room)

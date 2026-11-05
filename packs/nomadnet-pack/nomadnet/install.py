# NomadNet -- the Stump as a Nomad Network node: pages that NomadNet and
# MeshChat browse over Reticulum (LoRa included), so people on those apps
# get a real interface instead of chat-room lines. The Stump's home page,
# its rooms (read, and say something), the billboard (read, and post a
# notice) and the shared files' list. Uses plugin API 2: stump.node().
#
# The protocol is NomadNet's own (nomadnet/Node.py): a "nomadnetwork.node"
# destination announced with the node's name, answering link requests for
# /page/<name>.mu with a page in micron, its markup. Form fields arrive as
# "field_<name>", link variables as "var_<name>".

import time

VERSION = "1.0"
STUMP_API = 3

ROOM_LINES = 15        # lines shown per room
BOARD_SHOWN = 12       # notices shown
FILES_SHOWN = 40       # files listed
BODY_MAX = 300         # a notice's text shown, in characters

_api = []
_door = [None]
_hub = [None]          # the rrc.hub destination: NomadNet's chat (hub.py)


def setup(stump):
    _api.append(stump)
    d = stump.node("nomadnetwork", "node")
    _door[0] = d
    for name, fn in (("index", _index), ("rooms", _rooms), ("room", _room), ("say", _say),
                     ("board", _board), ("notice", _notice), ("files", _files)):
        d.handle("/page/" + name + ".mu", fn)
    if stump.setting("HUB", True):
        from . import hub
        h = stump.node("rrc", "hub")
        h.on_link(hub.on_link)
        _hub[0] = h
        stump.every(1, hub.tick)
    from . import browse, hubs
    browse.setup(stump)
    hubs.setup(stump)
    stump.page("", _web, nav=lambda lang: stump.t("card", lang), sub=lambda lang: stump.t("card_sub", lang))
    every = max(5, int(stump.setting("ANNOUNCE_MIN", 30) or 30))
    stump.every(every * 60, _announce)
    stump.every(60, _first_announce)


_announced = [False]


def _first_announce():
    if not _announced[0]:
        _announce()


def _announce():
    if _door[0] is not None and _door[0].announce(_name()):
        _announced[0] = True
    if _hub[0] is not None:
        _hub[0].announce(_name())


def _hub_src():
    """The hub's own sender hash in RRC envelopes: its destination's."""
    try:
        return _hub[0].dest.hash
    except Exception:
        return b"\x00" * 16


def _hub_link(room):
    """A link that opens this room in NomadNet's Channels (rrc://)."""
    h = _hub[0].hexhash if _hub[0] is not None else None
    if not h:
        return ""
    return "`F79d`[" + _t("hub_open") + "`rrc://" + h + "/" + room + "]`f"


def _canon(room):
    import rrc
    return rrc.canon(str(room).strip().lstrip("#").lower())


# ── helpers ──────────────────────────────────────────────────────────

def _lang():
    try:
        import i18n
        return i18n.DEFAULT_LANG
    except Exception:
        return "en"


def _t(key, **kw):
    return _api[0].t(key, _lang(), **kw)


def _name():
    try:
        import rrc
        return (rrc.NODE or {}).get("name") or "Stump"
    except Exception:
        return "Stump"


def esc(text):
    """User text made safe in micron: ` and \\ escaped, and a line that
    would start a heading, divider, comment or field made plain."""
    out = []
    for line in str(text).replace("\\", "\\\\").replace("`", "\\`").split("\n"):
        if line[:1] in (">", "-", "#", "<", "="):
            line = "\\" + line
        out.append(line)
    return "\n".join(out)


def _str(v):
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except Exception:
            return ""
    return v if isinstance(v, str) else ""


def _get(data, key):
    return _str((data or {}).get(key)) if isinstance(data, dict) else ""


def _on(feature):
    try:
        import features
        return features.enabled(feature)
    except Exception:
        return True


def _mode():
    try:
        import stumpid.core as sc
        return sc.AUTH_MODE
    except Exception:
        return "open"


def _lxmf_of(who):
    """The LXMF address (hex) of whoever identified on the link, or None."""
    if not who:
        return None
    try:
        import rrc_mesh
        return rrc_mesh.lxmf_address(who)
    except Exception:
        return None


def _may_read(cid):
    try:
        import stumpid.core as sc
        return sc.can_read(cid) if cid else sc.AUTH_MODE != "mandatory"
    except Exception:
        return True


def _room_open(room):
    try:
        import stumpid.core as sc
        return sc.room_tier(room) == "open"
    except Exception:
        return True


def _inline(text):
    """Text inside a line (after a tag): only ` and \\ escaped."""
    return str(text).replace("\\", "\\\\").replace("`", "\\`").replace("\n", " ")


def _head(title):
    return ("`c`!" + _inline(_name()) + "`!\n`a\n-\n>" + _inline(title) + "\n\n")


def _nav():
    links = ["`[" + _t("nav_home") + "`:/page/index.mu]"]
    if _on("chat"):
        links.append("`[" + _t("nav_rooms") + "`:/page/rooms.mu]")
    if _on("billboard"):
        links.append("`[" + _t("nav_board") + "`:/page/board.mu]")
    if _on("files"):
        links.append("`[" + _t("nav_files") + "`:/page/files.mu]")
    return "\n-\n`F79d" + "  ".join(links) + "`f\n"


def _ago(ts):
    try:
        s = max(0, int(time.time() - float(ts)))
    except Exception:
        return ""
    if s < 90:
        return _t("ago_now")
    if s < 5400:
        return _t("ago_min", n=s // 60)
    if s < 129600:
        return _t("ago_h", n=s // 3600)
    return _t("ago_d", n=s // 86400)


def _off(feature_key):
    return _head(_t(feature_key)) + _t("off") + "\n" + _nav()


# ── pages ────────────────────────────────────────────────────────────

def _index(path, data, who):
    out = _head(_t("home_title"))
    try:
        import config
        greet = getattr(config, "MESH_GREETING", "") or ""
    except Exception:
        greet = ""
    if greet:
        out += esc(greet) + "\n\n"
    out += _t("home_intro") + "\n\n"
    if _on("chat"):
        out += "`F79d`[" + _t("nav_rooms") + "`:/page/rooms.mu]`f  " + _t("home_rooms") + "\n"
    if _on("billboard"):
        out += "`F79d`[" + _t("nav_board") + "`:/page/board.mu]`f  " + _t("home_board") + "\n"
    if _on("files"):
        out += "`F79d`[" + _t("nav_files") + "`:/page/files.mu]`f  " + _t("home_files") + "\n"
    try:
        import rrc
        lx = (rrc.NODE or {}).get("lxmf")
    except Exception:
        lx = None
    if lx:
        out += "\n" + _t("home_lxmf", addr=lx) + "\n"
    out += "\n`*" + _t("home_about") + "`*\n"
    return out


def _room_list():
    import rrc
    return [r for r in rrc.room_names() if _room_open(r)]


def _rooms(path, data, who):
    if not _on("chat"):
        return _off("rooms_title")
    if not _may_read(_lxmf_of(who)):
        return _head(_t("rooms_title")) + _t("mandatory") + "\n" + _nav()
    import rrc
    out = _head(_t("rooms_title"))
    for r in _room_list():
        n = len(rrc.names_in_room(r))
        try:
            topic = rrc.topic(r, _lang()) or ""
        except Exception:
            topic = ""
        out += ("`F79d`[#" + _inline(r) + "`:/page/room.mu`room=" + r + "]`f  "
                + _t("people", n=n) + ("  " + _inline(topic[:80]) if topic else "") + "\n")
        if _hub[0] is not None:
            out += "    " + _hub_link(r) + "\n"
    return out + _nav()


def _room_page(room, who, note=""):
    import rrc
    room = rrc.canon(room or rrc.MESH_ROOM)
    if not _on("chat") or room not in _room_list():
        return _head(_t("rooms_title")) + _t("no_room") + "\n" + _nav()
    if not _may_read(_lxmf_of(who)):
        return _head("#" + room) + _t("mandatory") + "\n" + _nav()
    out = _head("#" + room)
    lines = [m for m in rrc.since(room, 0) if m.get("kind") in ("msg", "me", "action", "system")][-ROOM_LINES:]
    if not lines:
        out += "`*" + _t("room_empty") + "`*\n"
    for m in lines:
        body = _inline(m.get("body") or "")
        if m.get("kind") == "system":
            out += "`Faaa" + body + "`f\n"
        elif m.get("kind") in ("me", "action"):
            out += "* " + _inline(m.get("nick") or "") + " " + body + "\n"
        else:
            out += "`!" + _inline(m.get("nick") or "") + "`! " + body + "\n"
    out += "\n"
    if note:
        out += "`Ff80" + esc(note) + "`f\n"
    if who:
        out += (_t("say_label") + " `B444`<48|msg`>`b  `F79d`[" + _t("say_send")
                + "`:/page/say.mu`msg|room=" + room + "]`f\n")
    else:
        out += "`*" + _t("identify") + "`*\n"
    out += "`F79d`[" + _t("refresh") + "`:/page/room.mu`room=" + room + "]`f\n"
    if _hub[0] is not None:
        out += _hub_link(room) + "  " + _t("hub_why") + "\n"
    return out + _nav()


def _room(path, data, who):
    return _room_page(_get(data, "var_room"), who)


def _nick_for(lx):
    """The name the Stump already knows for this person, else nomad-xxxx."""
    try:
        import rrc_mesh
        p = rrc_mesh._peers.get(lx)
        if p and p.get("nick"):
            return p["nick"]
    except Exception:
        pass
    try:
        from urns import lxmf
        r = lxmf.ROUTER[0]
        e = r.peers.get(bytes.fromhex(lx)) if r else None
        if e and e.get("name"):
            import rrc
            n = rrc.clean_nick(e["name"]) if hasattr(rrc, "clean_nick") else e["name"]
            if n:
                return n
    except Exception:
        pass
    return "nomad-" + lx[:4]


def _speak(who, room, text):
    """A line from a NomadNet user, as if their app had sent it over LXMF:
    the same gates (access mode, flood guard, plugins). The replies only
    they would see, as one line."""
    import rrc
    lx = _lxmf_of(who)
    if not lx:
        return _t("identify")
    nick = _nick_for(lx)
    rrc.touch_user(lx, nick=nick, room=room)
    replies, _ = rrc.handle_input(lx, room, text)
    replies = [r for r in replies if r and r != "__CLEAR__"]
    return " ".join(replies)[:200]


def _say(path, data, who):
    import rrc
    room = rrc.canon(_get(data, "var_room") or rrc.MESH_ROOM)
    msg = _get(data, "field_msg").strip()
    note = ""
    if msg and _on("chat") and room in _room_list() and who:
        note = _speak(who, room, msg)
    return _room_page(room, who, note)


def _board_page(who, note=""):
    if not _on("billboard"):
        return _off("board_title")
    import billboard
    out = _head(_t("board_title"))
    try:
        ents = billboard._read_entries()
    except Exception:
        ents = []
    shown = list(reversed(ents))[:BOARD_SHOWN]
    if not shown:
        out += "`*" + _t("board_empty") + "`*\n"
    for e in shown:
        title, body, ts = e[1], e[2], e[3]
        out += ">>" + _inline((title or "")[:80]) + "\n"
        if body:
            b = body if len(body) <= BODY_MAX else body[:BODY_MAX] + "…"
            out += esc(b) + "\n"
        a = _ago(ts)
        if a:
            out += "`Faaa" + a + "`f\n"
        out += "\n"
    if note:
        out += "`Ff80" + esc(note) + "`f\n"
    if who:
        out += ("-\n" + _t("notice_title") + " `B444`<40|title`>`b\n" + _t("notice_body")
                + " `B444`<40x3|body`>`b\n`F79d`[" + _t("notice_send") + "`:/page/notice.mu`title|body]`f\n")
    else:
        out += "`*" + _t("identify") + "`*\n"
    return out + _nav()


def _board(path, data, who):
    return _board_page(who)


def _notice(path, data, who):
    import rrc
    title = _get(data, "field_title").replace("\n", " ").strip()
    body = _get(data, "field_body").strip()
    note = ""
    if title and who and _on("billboard"):
        note = _speak(who, rrc.MESH_ROOM, "/post " + title + (" | " + body if body else ""))
    return _board_page(who, note)


def _files(path, data, who):
    if not _on("files"):
        return _off("files_title")
    import fserv
    out = _head(_t("files_title"))
    names = fserv._list_files()
    if not names:
        out += "`*" + _t("files_empty") + "`*\n"
    for n in names[:FILES_SHOWN]:
        size = fserv._size(fserv.SHARED_DIR + "/" + n)
        out += esc(n) + "  `Faaa" + _size(size) + "`f\n"
    if len(names) > FILES_SHOWN:
        out += _t("files_more", n=len(names) - FILES_SHOWN) + "\n"
    out += "\n" + _t("files_how") + "\n"
    return out + _nav()


def _size(n):
    if n >= 1048576:
        return "%.1f MB" % (n / 1048576)
    if n >= 1024:
        return "%d KB" % (n // 1024)
    return "%d B" % n


# ── the Stump's own web page: how to reach it from NomadNet ──────────

def _web(req):
    s = _api[0]
    e = s.esc
    t = lambda k, **kw: s.t(k, req.lang, **kw)
    node = _door[0].hexhash if _door[0] is not None else None
    hub = _hub[0].hexhash if _hub[0] is not None else None
    out = ["<h1>" + e(t("web_title")) + "</h1><p class='sub'>" + e(t("web_intro")) + "</p>"]
    if not node:
        return "".join(out) + "<div class='panel'><p>" + e(t("web_starting")) + "</p></div>"
    out.append("<div class='panel'><h2>" + e(t("web_pages")) + "</h2><p>" + e(t("web_pages_how")) + "</p>"
               "<p><code>" + node + "</code></p></div>")
    if hub:
        out.append("<div class='panel'><h2>" + e(t("web_chat")) + "</h2><p>" + e(t("web_chat_how")) + "</p>"
                   "<p><code>" + hub + "</code></p><p class='sub'>" + e(t("web_chat_rooms")) + " "
                   + ", ".join("<code>rrc://" + hub + "/" + e(r) + "</code>" for r in _room_list()) + "</p></div>")
    out.append("<p class='sub'>" + e(t("web_meshchat")) + "</p>")
    return "".join(out)

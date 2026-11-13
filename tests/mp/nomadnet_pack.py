# The NomadNet pack (1.0.0-beta.53): the Stump as a Nomad Network node.
# Through the real request handlers of its nomadnetwork.node destination
# (plugin API 2), as a NomadNet browser's link requests reach them.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import config
config.AUTH_ADMIN_PASSWORD = 'pw'
import plugins, rrc, i18n, billboard, fserv
from urns.identity import Identity
from urns.destination import Destination
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:400]))
    if not c:
        FAIL.append(n)


i18n.DEFAULT_LANG = 'en'
plugins.load_all()
check("the pack starts (plugin API 2)", plugins._plugins.get('nomadnet', {}).get('state') == 'on',
      plugins._plugins.get('nomadnet'))
node = Identity()
rrc.NODE = {"name": "LaBuche", "lxmf": "ab" * 16}
plugins.network_ready(node)
door = plugins._doors[("nomadnetwork", ("node",))]
check("its destination: nomadnetwork.node, the Stump's identity",
      door.dest is not None and door.dest.hash == Destination.hash(node, "nomadnetwork", "node"))


def get(page, data=None, who=None):
    from urns.identity import Identity as I
    h = door.dest.request_handlers.get(I.truncated_hash(("/page/" + page).encode()))
    if h is None:
        return None
    r = h["generator"](path="/page/" + page, data=data, request_id=b'r' * 16, link_id=b'l' * 16,
                       remote_identity=who, requested_at=0)
    return r.decode() if r is not None else None


b = get("index.mu")
check("home: the name, links to rooms, billboard, files, the LXMF address",
      "LaBuche" in b and ":/page/rooms.mu]" in b and ":/page/board.mu]" in b and ":/page/files.mu]" in b
      and "ab" * 16 in b, b)

rrc.post('main', 'rod', 'hello `world`')
rrc.post('main', '-dash', '# looks like a comment')
b = get("rooms.mu")
check("rooms: each open room, linked", "`room=main]" in b and "#main" in b, b)
b = get("room.mu", {"var_room": "main"})
check("a room: its lines, user text escaped for micron", "`!rod`! hello \\`world\\`" in b and "`!-dash`! # looks like" in b
      and ">#main" in b, b)
check("... anonymous: no field, asked to identify", "<48|msg`>" not in b and "Identify" in b)

who = Identity()
b = get("room.mu", {"var_room": "main"}, who)
check("... identified: a field and a Send link", "`<48|msg`>" in b and "`:/page/say.mu`msg|room=main]" in b, b)
b = get("say.mu", {"var_room": "main", "field_msg": "bonjour from nomadnet"}, who)
said = [m for m in rrc.since('main', 0) if m.get('body') == 'bonjour from nomadnet']
check("say: posted in the room, as that person, through the usual path",
      len(said) == 1 and said[0]['nick'].startswith('nomad-') and "bonjour from nomadnet" in b, rrc.since('main', 0)[-2:])
before = len(rrc.since('main', 0))
get("say.mu", {"var_room": "main", "field_msg": "sneaky"})
check("... anonymous: nothing posted", len(rrc.since('main', 0)) == before)

import stumpid.core as sc
sc.set_room_tier('main', 'minted')
b = get("rooms.mu")
check("a restricted room isn't listed", "room=main]" not in b, b)
b = get("room.mu", {"var_room": "main"})
check("... nor shown", "rod" not in b and "restricted" in b, b)
sc.set_room_tier('main', 'open')

b = get("notice.mu", {"field_title": "Soup tonight", "field_body": "Bring a bowl."}, who)
titles = [e[1] for e in billboard._read_entries()]
check("billboard: a notice posted by an identified visitor", "Soup tonight" in titles and "Soup tonight" in b, (titles, b[-300:]))
b = get("board.mu")
check("... and listed", ">>Soup tonight" in b and "Bring a bowl." in b, b)

open(fserv.SHARED_DIR + '/map.pdf', 'wb').write(b'x' * 2048)
b = get("files.mu")
check("files: names and sizes, downloads on Wi-Fi", "map.pdf" in b and "2 KB" in b and "Wi-Fi" in b, b)

import features
features._CONFIGURED = ['chat', 'about']
b = get("files.mu")
check("a feature switched off: said so", "doesn't offer" in b and "map.pdf" not in b, b)
features._CONFIGURED = ['chat', 'billboard', 'files', 'about']

sent = []
door.dest.announce = lambda app_data=None, **k: sent.append(app_data)
import nomadnet.install as nn
nn._announce()
check("announced with the Stump's name", sent == [b"LaBuche"], sent)

plugins.set_enabled('nomadnet', False)
check("switched off in /admin: pages answer nothing, no announce",
      get("index.mu") is None and door.announce(b"x") is False)
plugins.set_enabled('nomadnet', True)
check("... and back on", get("index.mu") is not None)

# ── The RRC hub: NomadNet's own chat in the Stump's rooms ─────────────
from nomadnet import cbor, hub
hubdoor = plugins._doors[("rrc", ("hub",))]
check("the hub's destination: rrc.hub", hubdoor.dest is not None and hubdoor.dest.hash == Destination.hash(node, "rrc", "hub"))
b = get("rooms.mu")
check("rooms list: a Chat in NomadNet link per room (rrc://)", "`rrc://" + hubdoor.hexhash + "/main]" in b, b)


class FakeSession:
    def __init__(self, who):
        self.who, self.out, self.cb, self.open = who, [], None, True
    def remote_hex(self):
        return self.who.hash.hex() if self.who else None
    def is_open(self):
        return self.open
    def send(self, d):
        assert len(d) < 380, len(d)
        self.out.append(cbor.loads(d))
        return True
    def on_packet(self, fn):
        self.cb = fn
    def close(self):
        self.open = False


def env(t, room=None, body=None, nick=None):
    e = {0: 1, 1: t, 2: b"12345678", 3: 0, 4: rrcme.hash}
    if room is not None: e[5] = room
    if body is not None: e[6] = body
    if nick: e[7] = nick
    return cbor.dumps(e)


rrcme = Identity()
fs = FakeSession(rrcme)
hub.on_link(fs)
fs.cb(env(1, body={0: "nomadnet", 1: "0.1", 2: {0: True, 1: True}}, nick="Zoe"))
types = [e[1] for e in fs.out]
check("HELLO -> WELCOME, with the Stump's name and limits, then a greeting notice",
      types[:2] == [2, 21] and fs.out[0][6][0] == "LaBuche" and fs.out[0][6][3][2] == 300, fs.out[:2])
fs.out.clear()
fs.cb(env(10, room="main"))
check("JOIN -> JOINED", fs.out and fs.out[0][1] == 11 and fs.out[0][5] == "main", fs.out)
check("... and the room is told Zoe arrived", any(m.get('body') == '✓ ~Zoe' for m in rrc.since('main', 0)), rrc.since('main', 0)[-2:])
hub.tick()
check("... with the last lines from before", any(e[1] == 20 and e.get(6) == "bonjour from nomadnet" for e in fs.out), fs.out)
fs.out.clear()
fs.cb(env(20, room="main", body="hi from Channels", nick="Zoe"))
said = [m for m in rrc.since('main', 0) if m.get('body') == 'hi from Channels']
check("MSG from NomadNet: in the Stump's room, as Zoe", len(said) == 1 and said[0]['nick'] == 'Zoe', rrc.since('main', 0)[-2:])
hub.tick()
check("... not sent back to Zoe", not any(e.get(6) == "hi from Channels" for e in fs.out), fs.out)
rrc.post('main', 'rod', 'hello Zoe')
hub.tick()
m = [e for e in fs.out if e[1] == 20 and e.get(6) == 'hello Zoe']
check("someone on the Stump speaks: Zoe gets it, with the nick", len(m) == 1 and m[0][7] == 'rod' and m[0][5] == 'main', fs.out)
fs.out.clear()
fs.cb(env(20, room="main", body="/list"))
check("/list: the hub's room list notice", fs.out and fs.out[0][1] == 21 and fs.out[0][6].startswith("Registered public rooms:\n  main"), fs.out)
fs.out.clear()
fs.cb(env(20, room="main", body="/who main"))
check("/who: members in main", fs.out and fs.out[0][6].startswith("members in main: ") and "Zoe (" in fs.out[0][6], fs.out)
fs.out.clear()
fs.cb(env(30, body=b"pp"))
check("PING -> PONG", fs.out and fs.out[0][1] == 31 and fs.out[0][6] == b"pp", fs.out)
fs.out.clear()
rrc.touch_user('v' + 'r' * 20, nick='rod')
rrc.send_dm('rod', 'Zoe', 'psst')
hub.tick()
check("a DM to Zoe: a notice", any(e[1] == 21 and 'rod' in e[6] and 'psst' in e[6] for e in fs.out), fs.out)
fs.out.clear()
fs.cb(env(10, room="nope"))
check("JOIN a room that isn't here: ERROR", fs.out and fs.out[0][1] == 40, fs.out)
fs.cb(b"\xff\x00garbage")
check("garbage: ignored", True)
anon = FakeSession(None)
hub.on_link(anon)
anon.cb(env(1, body={}))
check("not identified: refused", anon.out and anon.out[0][1] == 40, anon.out)
# Banned on the Stump (mods.py, 1.0.0-beta.64): a room ban refuses joining
# it; a total ban (#main or -stump) and the hub sends nothing at all.
import mods
mods.reset("nn_mods.json")
zcid = [h.cid for h in hub._sessions if getattr(h, "nick", "") == "Zoe" and h.cid]
zcid = zcid[0]
rrc.create_room("bavard")
mods._load()["bans"]["bavard"] = {mods._key(zcid): {"label": "Zoe", "by": "test", "at": 0}}
fs.out.clear()
fs.cb(env(10, room="bavard"))
check("NomadNet, banned from a room: JOIN refused (ERROR)", fs.out and fs.out[0][1] == 40, fs.out)
mods._load()["bans"]["*"] = {mods._key(zcid): {"label": "Zoe", "by": "test", "at": 0}}
fs.out.clear()
rrc.post('main', 'rod', 'Zoe must not get this')
rrc.send_dm('rod', 'Zoe', 'nor this')
hub.tick()
check("NomadNet, a total ban: the hub sends nothing (no room line, no DM)",
      not any('must not' in str(e.get(6)) or 'nor this' in str(e.get(6)) for e in fs.out), fs.out)
fs.cb(env(20, room="main", body="let me in"))
check("... and what they send isn't posted", not any(m.get('body') == 'let me in' for m in rrc.since('main', 0)))
mods._load()["bans"].clear()
rrc.post('main', 'rod', 'back for Zoe')
hub.tick()
check("... unbanned: lines again from then on (not what was missed)", any(e.get(6) == 'back for Zoe' for e in fs.out)
      and not any('must not' in str(e.get(6)) for e in fs.out), fs.out)
fs.out.clear()
fs.cb(env(12, room="main"))
check("PART -> PARTED, the room told", fs.out and fs.out[0][1] == 13 and any(m.get('body') == '✗ ~Zoe' for m in rrc.since('main', 0)), fs.out)
fs.open = False
hub.tick()
check("link closed: session dropped", fs not in hub._sessions)
check("CBOR: a round trip", cbor.loads(cbor.dumps({1: [b"x", "é", -5, None, True, 70000]})) == {1: [b"x", "é", -5, None, True, 70000]})

# The card on the Stump's own home page, and its page.
s_, ct, b = req('/')
check("a NomadNet card on the home page", "href='/p/nomadnet/'" in b, b[-1500:])
s_, ct, b = req('/p/nomadnet/')
check("its page: the node's and the hub's addresses, the rooms' rrc:// links",
      s_.startswith("200") and door.hexhash in b and hubdoor.hexhash in b and "rrc://" + hubdoor.hexhash + "/main" in b, b[-800:])

# ── Browsing NomadNet from the Stump (API 3) ─────────────────────────
from nomadnet import browse
OTHER = "c0ffee" + "00" * 13
browse._heard(OTHER, b"Aleph")
s_, ct, b = req('/p/nomadnet/nodes')
rrc.set_reachable('9d' * 16, 'sidney')
s_, ct, b = req('/p/nomadnet/nodes')
check("people heard by their LXMF announce, with how to write to them", "sidney" in b and "/msg sidney" in b, b[-800:])
check("browse: the nodes heard, by name, linked", "Aleph" in b and "/p/nomadnet/view?n=" + OTHER in b, b[-600:])
PAGE = """#!c=0
>Aleph
Hello `!there`!, `Ff00red`f and \\`literal\\`.
-
>>Links
`[Next page`:/page/next.mu]  `[Elsewhere`abababababababababababababababab:/page/index.mu]
`[Join chat`rrc://abababababababababababababababab/main]
Name: `<16|name`Zoe>  `<?|ok|yes`Agree>
`[Send`:/page/form.mu`name|ok|mode=fast]
"""
asked = []


class FakeRemote:
    failed = False
    def request(self, path, data, fn):
        asked.append((path, data))
        fn(PAGE.encode() if path != "/page/form.mu" else ("got " + repr(sorted((data or {}).items()))).encode())


browse._api[0].connect = lambda *a, **k: FakeRemote()
s_, ct, b = req('/p/nomadnet/view?n=' + OTHER + '&p=/page/index.mu')
check("a node's page: fetched over its link, shown as HTML", asked and asked[0] == ("/page/index.mu", None)
      and "class='mu h1'>Aleph</div>" in b, (asked, b[-1500:]))
check("... formatting: bold, colour, escapes", "font-weight:bold'>there</span>" in b and "color:#f00'>red</span>" in b
      and "`literal`" in b, b[-1500:])
check("... links: same node, another node, an RRC room", "href='/p/nomadnet/view?n=" + OTHER + "&amp;p=/page/next.mu'" in b
      and "n=abababababababababababababababab&amp;p=/page/index.mu" in b and "/p/nomadnet/hubs?add=abababababababababababababababab/main" in b, b[-1500:])
check("... fields and a submit link carrying its fields and variables",
      "name='mu_name'" in b and "value='Zoe'" in b and "type='checkbox' name='mu_ok' value='yes'" in b
      and "formaction='/p/nomadnet/view?n=" + OTHER + "&amp;p=/page/form.mu&amp;v=mode=fast&amp;f=name|ok'" in b, b[-1500:])
check("... no script, user text escaped", "<script" not in b.split("mu-page")[1])
s_, ct, b = req('/p/nomadnet/view?n=' + OTHER + '&p=/page/form.mu&v=mode=fast&f=name|ok', b'mu_name=Zoe+B&mu_ok=yes&mu_other=x')
check("a form sent as NomadNet sends it: field_ and var_ entries, only the listed fields",
      asked[-1] == ("/page/form.mu", {"field_name": "Zoe B", "field_ok": "yes", "var_mode": "fast"}), asked[-1])
check("... and the node's answer shown", "got " in b, b[-600:])
s_, ct, b = req('/p/nomadnet/view?n=nothex&p=/page/index.mu')
check("a bad address: refused, nothing asked", "Not a valid" in b)
html = browse.render("<script>alert(1)</script>\n>`<x`<b>bad>\n`[x`javascript:alert(1)]", OTHER)
check("render: markup in a page can't inject HTML or script links", "<script>" not in html and "javascript:" not in html.replace("&", ""), html)

try:
    plugins.Api('evil').node('lxmf', 'delivery')
    check("a plugin can't take the core's names", False)
except ValueError:
    check("a plugin can't take the core's names", True)
print('FAILURES:', FAIL)

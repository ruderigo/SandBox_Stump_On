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

try:
    plugins.Api('evil').node('lxmf', 'delivery')
    check("a plugin can't take the core's names", False)
except ValueError:
    check("a plugin can't take the core's names", True)
print('FAILURES:', FAIL)

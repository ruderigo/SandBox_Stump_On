# Stumps' names on the other Stumps (1.0.0-beta.60), with the real firmware
# on regular Python:
#  - a Stump set up again (a new identity, the same name, the same home
#    address) retires the old identity once its announces have stopped: the
#    new one gets the plain name, not "LaBuche1";
#  - one just heard (no route yet) is never taken for the old one; a copy of
#    the old one's announce passed on late doesn't keep it alive; another
#    Stump with the same name elsewhere keeps its tag ("LaBuche-k7q2", not
#    a number);
#  - a Stump whose announces stopped isn't kept a peer by its route;
#  - a renamed Stump goes by its new name.
# Run: python3 tests/pc/stump_names_test.py
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, "pc", "pc_compat"), os.path.join(ROOT, "final_firmware")]
import stump_host
stump_host.install(os.path.join(ROOT, "final_firmware"))
from urns.log import set_loglevel, LOG_NONE
set_loglevel(LOG_NONE)
from urns.identity import Identity
from urns.transport import Transport
from urns.lxmf import LXMRouter
import rrc, rrc_mesh, discovery

FAIL = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + repr(info)[:500]))
    if not cond:
        FAIL.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print("::error::" + (name + ": " + repr(info)[:1500]).replace("\n", "%0A"))


me = LXMRouter(identity=Identity())
me.register_delivery_identity(me.identity, display_name="LaBuche10")
T = [1_000_000.0]                       # this test's clock
rrc_mesh.time.time = lambda: T[0]


def stump(h, name, http, emitted, heard=None):
    """Another Stump: its beacon heard, a route to it (its announce's time)."""
    rrc.mark_stump(h)
    discovery._known[h] = {"name": name, "http": http, "at": heard if heard is not None else T[0], "caps": {}}
    if emitted is not None:
        Transport.path_table[bytes.fromhex(h)] = [T[0], bytes.fromhex(h), 2, T[0] + 86400, None, None, emitted]
    me.peers[bytes.fromhex(h)] = {"name": name}


def announce(h, emitted):
    """An announce of h arrives: its route's time (emitted) as it carries."""
    if h in rrc_mesh._peers:
        rrc_mesh._peers[h]["last_seen"] = T[0]     # (a pass marks a live Stump peer present)
    e = Transport.path_table.get(bytes.fromhex(h))
    if e is None:
        return                          # (retired: its route gone)
    e[6] = emitted
    e[0] = T[0]


OLD, NEW = "11" * 16, "22" * 16
HOME = ["http://192.168.0.173/", "http://192.168.4.1/"]
stump(OLD, "LaBuche", HOME, emitted=100)
rrc_mesh._peers[OLD] = {"nick": "LaBuche", "room": rrc.CHAIN_ROOM, "home_room": rrc.CHAIN_ROOM, "stump": True,
                        "last_seen": T[0], "last_sent_id": 0, "lora_sent_id": 0, "last_dm_id": 0}
rrc.touch_user(OLD, nick="LaBuche", room=rrc.CHAIN_ROOM)
rrc_mesh._reach[OLD] = {"nick": "LaBuche", "last_dm_id": 0}
rrc.set_reachable(OLD, "LaBuche")
rrc_mesh._quiet_for(OLD)                # its announces seen rising, now

# The board set up again: a new identity, the same name and address. Its
# beacon heard first, no route yet.
stump(NEW, "LaBuche", ["http://192.168.0.173/", "http://192.168.4.1/"], emitted=None)
T[0] += 30
rrc_mesh._tidy_replaced(T[0])
check("a new identity just heard, no route yet: not taken for the old one", NEW in discovery._known and OLD in discovery._known)
p = rrc_mesh._get_peer(NEW, "LaBuche")
check("... while the old one holds the name, the new one has a tag (from its identity: the same on every Stump)",
      p["nick"] == rrc.tagged_nick("LaBuche", NEW) and p["nick"].startswith("LaBuche-"), p["nick"])
stump(NEW, "LaBuche", ["http://192.168.0.173/", "http://192.168.4.1/"], emitted=5000)
rrc_mesh._quiet_for(NEW)

# The old one's announces have stopped; a copy of its last one passed on
# late (the same time inside) doesn't count.
for step in range(4):
    T[0] += 200
    announce(OLD, 100)                  # replayed: the same moment
    announce(NEW, 5000 + T[0])          # the new one's, rising
    rrc_mesh._quiet_for(NEW)
    rrc_mesh._tidy_replaced(T[0])
check("the old identity's announces stopped (a late copy doesn't count): retired", OLD not in discovery._known
      and OLD not in rrc_mesh._peers and OLD not in rrc_mesh._reach and not rrc.is_stump(OLD)
      and bytes.fromhex(OLD) not in Transport.path_table, list(discovery._known))
check("... its name free: nick_taken says no", not rrc.nick_taken("LaBuche", NEW))
rrc_mesh._fix_nick(me, NEW, rrc_mesh._peers[NEW])
check("... the new one goes by the plain name", rrc_mesh._peers[NEW]["nick"] == "LaBuche", rrc_mesh._peers[NEW]["nick"])

# Another Stump called LaBuche, elsewhere (another address): keeps its number.
OTHER = "33" * 16
stump(OTHER, "LaBuche", ["http://10.0.0.5/", "http://192.168.4.1/"], emitted=7000)
po = rrc_mesh._get_peer(OTHER, "LaBuche")
for step in range(4):
    T[0] += 200
    announce(NEW, 9000 + T[0])
    announce(OTHER, 9000 + T[0])
    for h in (NEW, OTHER):              # (each pass marks a live Stump peer present)
        if h in rrc_mesh._peers:
            rrc_mesh._peers[h]["last_seen"] = T[0]
    rrc_mesh._quiet_for(NEW); rrc_mesh._quiet_for(OTHER)
    rrc_mesh._tidy_replaced(T[0])
check("another Stump of the same name elsewhere: not retired, keeps its tag", OTHER in discovery._known
      and po["nick"] == rrc.tagged_nick("LaBuche", OTHER), po["nick"])
rrc_mesh._fix_nick(me, OTHER, po)
check("... and _fix_nick leaves it tagged while the name is taken", po["nick"] == rrc.tagged_nick("LaBuche", OTHER), po["nick"])
# A Stump known with a number from before 1.0.0-beta.60: the plain name once free, as with a tag.
OLDNUM = "66" * 16
stump(OLDNUM, "Grange", ["http://192.168.0.191/"], emitted=1)
pn = rrc_mesh._get_peer(OLDNUM, "Grange")
pn["nick"] = "Grange1"
rrc_mesh._fix_nick(me, OLDNUM, pn)
check("a nick with a number from an older release: the plain name once free", pn["nick"] == "Grange", pn["nick"])
# /nick with a taken nick: a tag, said.
rrc.touch_user("10.0.0.9", nick="ann", room="main")
r, _ = rrc.handle_input("10.0.0.10", "main", "/nick ann")
got = rrc._users.get("10.0.0.10", {}).get("nick")
check("/nick with a nick taken here: theirs with a tag, and said", got == rrc.tagged_nick("ann", "10.0.0.10") and r and got in r[0], (got, r))

# A Stump whose announces stopped: not kept alive by its route.
GONE = "44" * 16
stump(GONE, "LaBuche7", ["http://192.168.0.177/"], emitted=300)
rrc_mesh._quiet_for(GONE)
check("a Stump announcing: alive", rrc_mesh._alive(GONE, T[0]))
T[0] += rrc_mesh.STUMP_QUIET_S + 10
announce(GONE, 300)
check("... its announces stopped for STUMP_QUIET_S (its route still there): gone", not rrc_mesh._alive(GONE, T[0]))

# A Stump renamed (same identity): goes by its new name.
REN = "55" * 16
stump(REN, "Atelier", ["http://192.168.0.190/"], emitted=1)
pr = rrc_mesh._get_peer(REN, "Atelier")
me.peers[bytes.fromhex(REN)] = {"name": "Grange"}
discovery._known[REN]["name"] = "Grange"
rrc_mesh._fix_nick(me, REN, pr)
check("a Stump renamed: goes by its new name", pr["nick"] == "Grange", pr["nick"])

print("FAILURES", FAIL)
sys.exit(1 if FAIL else 0)

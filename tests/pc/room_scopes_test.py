# Rooms with a scope (1.0.0-beta.62), with the real firmware (urns, LXMF,
# rrc, rrc_mesh, rooms) on regular Python:
#  - /create, /setchan, /chanreq: the admin password, -lora only with
#    "confirm" after a warning, the built-in rooms untouched, never posted;
#  - to a chain Stump: the scope ("[ROOM] #bavard wifi n"), then the room's
#    lines, a plugin bot's included (not BarKeep's), over the chain only;
#  - from a chain Stump: its scope taken (the newest n), its lines filed in
#    the room; from a Stump outside the chain, a room's lines not taken;
#  - a LoRa room offered by a Stump outside the chain: a request, BarKeep
#    says so in #main; /chanreq lists it, -a shares it (and answers OK),
#    -r refuses it (answers NO, not asked again);
#  - a Stump that doesn't say "rs" gets nothing of this; the scopes come
#    back after a restart.
# Run: python3 tests/pc/room_scopes_test.py
import os, sys, time, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, "pc", "pc_compat"), os.path.join(ROOT, "final_firmware")]
import stump_host
stump_host.install(os.path.join(ROOT, "final_firmware"))
from urns.log import set_loglevel, LOG_NONE
set_loglevel(LOG_NONE)
from urns.identity import Identity
from urns.destination import Destination
from urns.transport import Transport
from urns.interfaces import Interface
from urns.lxmf import LXMRouter
import rrc, rrc_mesh, discovery, rooms, i18n

FAIL = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + repr(info)[:600]))
    if not cond:
        FAIL.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print("::error::" + (name + ": " + repr(info)[:1500]).replace("\n", "%0A"))


class Fake(Interface):
    HW_MTU = 564

    def __init__(self, name):
        super().__init__(name)
        self.online = True

    def process_outgoing(self, data):
        return True


class RNodeSerialInterface(Fake):
    pass


class ChainUplinkInterface(Fake):
    pass


radio_if, chain_if = RNodeSerialInterface("Heltec (USB)"), ChainUplinkInterface("chain")
Transport.interfaces[:] = [chain_if, radio_if]
now = time.time()
ROOMS_FILE = os.path.join(stump_host.ROOT, ".test_rooms_%d.json" % os.getpid())
rooms.reset(ROOMS_FILE)
rooms._pw_ok = lambda pw, cid: pw == "s3cret"
rrc.create_room(rrc.CHAIN_ROOM)                 # in a chain
me = LXMRouter(identity=Identity())
me.register_delivery_identity(me.identity, display_name="CAM")
rrc.NODE.update({"name": "CAM", "lxmf": "ab" * 16})


def stump(name, over, caps):
    ident = Identity()
    d = Destination(ident, Destination.OUT, Destination.SINGLE, "lxmf", "delivery")
    Identity.remember(os.urandom(32), d.hash, ident.get_public_key())
    Transport.path_table[d.hash] = [now, d.hash, 1, now + 3600, over, None, now]
    h = d.hash.hex()
    rrc.mark_stump(h)
    discovery._known[h] = {"name": name, "at": now, "http": "", "caps": caps}
    me.peers[d.hash] = {"name": name}
    rrc_mesh._peers[h] = {"nick": name, "room": rrc.CHAIN_ROOM, "home_room": rrc.CHAIN_ROOM, "stump": True,
                          "last_seen": now, "last_sent_id": 0, "lora_sent_id": 0, "last_dm_id": 0}
    return h


def say(text, who="10.0.0.2"):
    return rrc.handle_input(who, rrc.get_user(who)["room"], text)[0]


def flushed(h):
    """What _flush_rooms queues for h: [(title, text, interface)]."""
    del rrc_mesh._send_queue[:]
    rrc_mesh._flush_rooms(me, h, rrc_mesh._peers[h])
    out = [(it[3], it[2], it[5] if len(it) > 5 else None) for it in rrc_mesh._send_queue]
    del rrc_mesh._send_queue[:]
    return out


rrc.touch_user("10.0.0.2", nick="rod", room="main")
LB = stump("LaBuche", chain_if, {"rs": 1, "rad": False})
OLD = stump("Vieille", chain_if, {"rad": False})              # an older Stump: no "rs"
FAR = stump("Loin", radio_if, {"rs": 1, "rad": True})          # outside the chain, over LoRa
radio_bridges = [radio_if]
import radio
radio.bridges = lambda: radio_bridges

# ---- 1. The commands ----
before = len(rrc.since("main", 0))
check("/create without the password: how to use it", "/create" in say("/create")[0])
r = say("/create wrong #bavard -wifi")
check("a wrong password: refused, no room", r[0].startswith("✗") and not rrc.room_exists("bavard"), r)
r = say("/create s3cret #lora-mesh -local")
check("a built-in room: its scope doesn't change", r[0].startswith("✗") and rooms.scope(rrc.MESH_ROOM) == "lora", r)
r = say("/create s3cret #bavard -lora")
check("-lora: the airtime warning (red), not done without confirm",
      r[0].startswith("⚠") and "confirm" in r[1] and not rrc.room_exists("bavard"), r)
r = say("/create s3cret #bavard -wifi")
check("/create #bavard -wifi: made, Wi-Fi, how to join", rrc.room_exists("bavard") and rooms.scope("bavard") == "wifi"
      and any("/join #bavard" in x for x in r), r)
check("... nothing of it posted anywhere (the password stays private)",
      len(rrc.since("main", 0)) == before and not any("s3cret" in m["body"] for m in rrc.since("bavard", 0)))
r = say("/create s3cret #bavard -local")
check("/create on an existing room: use /setchan", r[0].startswith("✗") and "/setchan" in r[0], r)
r = say("/setchan s3cret")
check("/setchan <password>: the rooms and where they go", "#bavard  wifi" in r and "#lora-mesh  lora" in r, r)
r = rrc.handle_input("10.0.0.2", "main", "/rooms")[0]
check("/rooms marks a Wi-Fi room", any(x.startswith("#bavard") and "[Wi-Fi]" in x for x in r), r)

# ---- 2. To a chain Stump ----
out = flushed(LB)
check("to a chain Stump: the scope, over the chain", out and out[0][1] == "[ROOM] #bavard wifi 1" and out[0][2] is chain_if, out)
check("... an older Stump (no \"rs\"): nothing", flushed(OLD) == [])
check("... a Stump outside the chain: a Wi-Fi room isn't offered", flushed(FAR) == [])
check("... told once, not again each pass", flushed(LB) == [])
rrc.touch_user("10.0.0.2", room="bavard")
rrc.handle_input("10.0.0.2", "bavard", "bonjour la chaîne")
import barkeep
barkeep.plugin_posts_reset()
barkeep.plugin_post("bavard", "Bavard", "bavard", "Qu'est-ce donc? Qu'avez-vous?")
rrc.post("bavard", barkeep.BOT_NAME, "a BarKeep answer", bot=True)
out = flushed(LB)
body = out[0][1] if out else ""
check("its lines, titled #bavard, over the chain only", out and out[0][0] == "#bavard" and out[0][2] is chain_if, out)
check("... a person's and a plugin bot's (tagged), not BarKeep's", "<rod> bonjour la chaîne" in body
      and ("<%s> Qu'est-ce donc? Qu'avez-vous?" % rrc.bot_nick("Bavard")) in body and "BarKeep answer" not in body, body)
check("... from now on: nothing again", flushed(LB) == [])

# ---- 3. From a chain Stump ----
rrc_mesh._from_stump(LB, rrc_mesh._peers[LB], "<ann> salut\n<Bavard-x7q2> Laissez-moi, je vous prie.", me, "#bavard")
got = [(m["nick"], m["body"]) for m in rrc.since("bavard", 0)][-2:]
check("a chain Stump's #bavard lines: filed in #bavard", got == [("ann@LaBuche", "salut"), ("Bavard-x7q2@LaBuche", "Laissez-moi, je vous prie.")], got)
rrc_mesh._from_stump(FAR, rrc_mesh._peers[FAR], "<eve> intrusion", me, "#bavard")
check("... a Stump outside the chain: not taken (not shared with it)", rrc.since("bavard", 0)[-1]["body"] != "intrusion")
rrc_mesh._from_stump(LB, rrc_mesh._peers[LB], "[ROOM] #atelier wifi 3", me, "")
check("a chain Stump's new Wi-Fi room: made here too", rrc.room_exists("atelier") and rooms.scope("atelier") == "wifi"
      and rooms.version("atelier") == 3)
rrc_mesh._from_stump(LB, rrc_mesh._peers[LB], "[ROOM] #atelier local 2", me, "")
check("... an older change (n 2 < 3) doesn't undo it", rooms.scope("atelier") == "wifi")
rrc_mesh._from_stump(LB, rrc_mesh._peers[LB], "[ROOM] #atelier local 4", me, "")
check("... a newer one does: local again", rooms.scope("atelier") == "local")
rrc_mesh._from_stump(FAR, rrc_mesh._peers[FAR], "[ROOM] #club wifi 9", me, "")
check("a Stump outside the chain can't set a scope here", rooms.scope("club") == "local" and not rrc.room_exists("club"))

# ---- 4. A LoRa room offered from outside the chain ----
main_before = len(rrc.since("main", 0))
rrc_mesh._from_stump(FAR, rrc_mesh._peers[FAR], "[ROOM] #radio-club lora 1", me, "#lora-mesh")
note = rrc.since("main", 0)[main_before:]
check("an offer from outside the chain: a request, BarKeep says so in #main",
      len(note) == 1 and "Loin" in note[0]["body"] and "#radio-club" in note[0]["body"] and "/chanreq" in note[0]["body"]
      and not rrc.room_exists("radio-club"), note)
rrc_mesh._from_stump(FAR, rrc_mesh._peers[FAR], "[ROOM] #radio-club lora 1", me, "#lora-mesh")
check("... offered again: asked once", len(rrc.since("main", 0)) == main_before + 1)
rrc_mesh._from_stump(FAR, rrc_mesh._peers[FAR], "[ROOM] #rando lora 1", me, "#lora-mesh")
r = say("/chanreq s3cret")
check("/chanreq: the warning, then the requests numbered", r[0].startswith("⚠") and r[1].startswith("1. #radio-club  Loin")
      and r[2].startswith("2. #rando  Loin"), r)
r = say("/chanreq s3cret -a 1")
check("-a 1: #radio-club shared over LoRa here", rooms.scope("radio-club") == "lora" and rooms.shares("radio-club", FAR, False), r)
out = flushed(FAR)
ctl = [o for o in out if o[0] == "#lora-mesh"]
check("... answered OK, over the radio", ctl and "[ROOMOK] #radio-club" in ctl[0][1] and ctl[0][2] is radio_if, out)
r = say("/chanreq s3cret -r 1")
NONE = i18n.t("chanreq_none", i18n.get_lang("10.0.0.2"))
check("-r 1: #rando refused, the list empty", "#rando" in r[0] and say("/chanreq s3cret")[0] == NONE, r)
out = flushed(FAR)
check("... answered NO", any("[ROOMNO] #rando" in o[1] for o in out), out)
rrc_mesh._from_stump(FAR, rrc_mesh._peers[FAR], "[ROOM] #rando lora 1", me, "#lora-mesh")
check("... offered again: no new request (refused for a day)", say("/chanreq s3cret")[0] == NONE)
rrc_mesh._from_stump(FAR, rrc_mesh._peers[FAR], "<eve> 73 de F4XYZ", me, "#radio-club")
check("the shared LoRa room's lines from it: filed", rrc.since("radio-club", 0)[-1]["body"] == "73 de F4XYZ")
rrc.post("radio-club", "rod", "73!")
out = flushed(FAR)
check("... and ours to it, over the radio", any(o[0] == "#radio-club" and "<rod> 73!" in o[1] and o[2] is radio_if for o in out), out)
out = flushed(LB)
check("a LoRa room goes to the chain too (its scope, then its lines)", any("[ROOM] #radio-club lora" in o[1] for o in out), out)

# ---- 5. Our own LoRa room, offered outside the chain ----
r = say("/create s3cret #veille -lora confirm")
check("-lora confirm: done", rooms.scope("veille") == "lora", r)
out = flushed(FAR)
check("... offered to the Stump outside the chain, over the radio", any("[ROOM] #veille lora" in o[1] and o[2] is radio_if for o in out), out)
check("... not again each pass", not any("#veille" in o[1] for o in flushed(FAR)))
rrc_mesh._from_stump(FAR, rrc_mesh._peers[FAR], "[ROOMOK] #veille", me, "#lora-mesh")
check("... it said OK: shared", rooms.shares("veille", FAR, False))
barkeep.plugin_post("bavard", "Bavard", "veille", "un bot sur la LoRa")
check("a bot posting in a LoRa room: BarKeep warns there, once", sum(1 for m in rrc.since("veille", 0) if m["body"].startswith("⚠")) == 1)
r = say("/setchan s3cret #veille -local")
out = flushed(FAR)
check("set back to local: the Stump outside the chain is told, and unshared",
      any("[ROOM] #veille local" in o[1] for o in out) and not rooms.shares("veille", FAR, False), out)

# ---- 6. After a restart ----
saved = rooms.FILE
rooms._db[0] = None
check("the scopes come back from the file", rooms.scope("bavard") == "wifi" and rooms.scope("radio-club") == "lora"
      and rooms.scope("veille") == "local", rooms._load())

for f in (ROOMS_FILE, ROOMS_FILE + ".tmp"):
    if os.path.exists(f):
        os.remove(f)
print("FAILURES", FAIL)
sys.exit(1 if FAIL else 0)

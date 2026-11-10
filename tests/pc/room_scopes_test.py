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
rrc_mesh._peers[FAR].update({"room": rrc.MESH_ROOM, "home_room": rrc.MESH_ROOM})   # (met over the radio)
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
QUIET = stump("Muette", chain_if, {})                        # its beacon not heard (yet)
check("a Stump whose beacon isn't heard yet: nothing until it shows it takes rooms", flushed(QUIET) == [])
rrc_mesh._from_stump(QUIET, rrc_mesh._peers[QUIET], "[ROOM] #bavard wifi 1", me, "")
check("... it sent a room's scope: it takes them, ours go to it", any("[ROOM] #bavard wifi" in o[1] for o in flushed(QUIET)))
del rrc_mesh._peers[QUIET]
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

# ---- 3b. A chain Stump whose route goes over a Heltec for a while (1.0.0-beta.63) ----
e = Transport.path_table[bytes.fromhex(LB)]
e[4] = radio_if                                   # its route: LoRa now
rrc_mesh._from_stump(LB, rrc_mesh._peers[LB], "<ann> par la radio", me, "#bavard")
check("route over LoRa for now: a chain Stump's #bavard lines still filed", rrc.since("bavard", 0)[-1]["body"] == "par la radio")
rrc.handle_input("10.0.0.2", "bavard", "pendant ce temps")
out = flushed(LB)
check("... and ours still go to it (its route, not dropped)", any(o[0] == "#bavard" and "<rod> pendant ce temps" in o[1] for o in out), out)
check("... the scopes still go to it", rrc_mesh._room_chain(LB) and rooms.shares("bavard", LB, rrc_mesh._room_chain(LB)))
e[4] = chain_if
rrc.handle_input("10.0.0.2", "bavard", "de retour")
out = flushed(LB)
check("route back over the chain: over the chain again, nothing skipped", out and out[0][2] is chain_if and "<rod> de retour" in out[0][1], out)
rrc.post("bavard", "rod", "ok")
rrc.post("bavard", "rod", "ok")
out = flushed(LB)
check("the same words twice in a Wi-Fi room: two lines sent", sum(o[1].count("<rod> ok") for o in out) == 2, out)
rrc_mesh._from_stump(LB, rrc_mesh._peers[LB], "<ann> oui", me, "#bavard")
rrc_mesh._from_stump(LB, rrc_mesh._peers[LB], "<ann> oui", me, "#bavard")
check("... and two received", [m["body"] for m in rrc.since("bavard", 0)][-2:] == ["oui", "oui"])
# Behind: a chain Stump that tells an older scope gets ours on the next pass.
flushed(LB)
rrc_mesh._from_stump(LB, rrc_mesh._peers[LB], "[ROOM] #bavard local 0", me, "")
out = flushed(LB)
check("a chain Stump behind on a room's scope: ours to it at once, not in ROOM_EVERY",
      any("[ROOM] #bavard wifi 1" in o[1] for o in out) and rooms.scope("bavard") == "wifi", out)

# ---- 3c. A chain Stump first heard over the radio: its beacon names the chain (1.0.0-beta.63) ----
rrc_mesh._my_chain[:] = ["c0ffee123456", time.time() + 10 ** 6]      # (this Stump's chain id)
for i in range(8):
    rrc.post("bavard", "rod", "ligne %d" % i)
NEWC = stump("Grange", radio_if, {"rs": 1, "rad": True, "ch": "c0ffee123456"})
rrc_mesh._peers[NEWC].update({"room": rrc.MESH_ROOM, "home_room": rrc.MESH_ROOM})    # met over the radio
check("a Stump met over the radio, its beacon naming this chain: on the chain for the rooms", rrc_mesh._room_chain(NEWC))
out = flushed(NEWC)
txt = "\n".join(o[1] for o in out)
check("... the scopes at once, then the last few lines (not the whole backlog, not nothing)",
      "[ROOM] #bavard wifi" in txt and "<rod> ligne 7" in txt and "<rod> ligne 3" in txt and "<rod> ligne 2" not in txt, out)
rrc_mesh._from_stump(NEWC, rrc_mesh._peers[NEWC], "<lea> depuis la Grange", me, "#bavard")
check("... and its #bavard lines taken", rrc.since("bavard", 0)[-1]["body"] == "depuis la Grange")
OTHERC = stump("Ailleurs", radio_if, {"rs": 1, "rad": True, "ch": "0123456789ab"})
rrc_mesh._peers[OTHERC].update({"room": rrc.MESH_ROOM, "home_room": rrc.MESH_ROOM})
check("... a Stump of another chain isn't", not rrc_mesh._room_chain(OTHERC) and not any("#bavard" in o[1] for o in flushed(OTHERC)))
del rrc_mesh._peers[NEWC], rrc_mesh._peers[OTHERC]
rrc_mesh._my_chain[:] = [None, time.time() + 10 ** 6]

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

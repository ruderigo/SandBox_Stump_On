# #lora-mesh across a chain with radios (1.0.0-beta.58), with the real
# firmware (urns, LXMF, rrc_mesh) on regular Python:
#  - a Stump the chain reaches gets #lora-mesh over Wi-Fi, never the radio;
#    one with no radio of its own too (it got nothing before);
#  - a live path over the chain's Wi-Fi isn't replaced by a shorter one
#    over LoRa (two chain members: 2 hops over Wi-Fi, 1 over the Heltecs);
#  - to several Stumps reached over LoRa only, a line goes once, signed,
#    and a copy played again, forged or heard twice shows nothing new;
#  - "No LoRa on mesh": no radio here nor along the chain, #lora-mesh lets
#    no one in from the chat;
#  - a burst of sends is paced (SENDS_PER_PASS).
# Run: python3 tests/pc/lora_mesh_test.py
import os, sys, time, asyncio
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
from urns import const
import urns.packet
import rrc, rrc_mesh, discovery, i18n

FAIL = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + repr(info)[:500]))
    if not cond:
        FAIL.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print("::error::" + (name + ": " + repr(info)[:1500]).replace("\n", "%0A"))


class Fake(Interface):
    HW_MTU = 564

    def __init__(self, name):
        super().__init__(name)
        self.online = True
        self.sent = []

    def process_outgoing(self, data):
        self.sent.append(bytes(data))
        return True


class RNodeSerialInterface(Fake):      # radio.bridges() knows radios by class name
    pass


class ChainUplinkInterface(Fake):
    pass


radio_if, chain_if = RNodeSerialInterface("Heltec (USB)"), ChainUplinkInterface("chain")
chain_if.gravity = 10                  # as chain.py sets it
Transport.interfaces[:] = [chain_if, radio_if]
now = time.time()

me = LXMRouter(identity=Identity())
me.register_delivery_identity(me.identity, display_name="CAM")


def stump(name, over, caps):
    """Another Stump: its keys known, its path over `over`, its beacon's caps."""
    ident = Identity()
    d = Destination(ident, Destination.OUT, Destination.SINGLE, "lxmf", "delivery")
    Identity.remember(os.urandom(32), d.hash, ident.get_public_key())
    Transport.path_table[d.hash] = [now, d.hash, 1, now + 3600, over, None, now]
    h = d.hash.hex()
    rrc.mark_stump(h)
    discovery._known[h] = {"name": name, "at": now, "http": "", "caps": caps}
    me.peers[d.hash] = {"name": name}
    rrc_mesh._peers[h] = {"nick": name, "room": rrc.MESH_ROOM, "home_room": rrc.MESH_ROOM, "stump": True,
                          "last_seen": now, "last_sent_id": 0, "lora_sent_id": 0, "last_dm_id": 0}
    return h, ident


rrc.touch_user("127.0.0.1", nick="rod", room=rrc.MESH_ROOM)

# ---- 1. Over Wi-Fi to a Stump the chain reaches ----
W3, _ = stump("WROVER3", chain_if, {"rad": False, "rh": False, "lb": 1})
FAR1, far1_id = stump("Far1", radio_if, {"rad": True, "rh": True, "lb": 1})
lines = ["<rod> hello"]
del rrc_mesh._send_queue[:]
rrc_mesh._queue_lora(me, W3, lines)
q = list(rrc_mesh._send_queue)
check("a chain Stump with no radio: over the chain, never the radio", len(q) == 1 and q[0][5] is chain_if, q)
del rrc_mesh._send_queue[:]
rrc_mesh._queue_lora(me, FAR1, lines)
q = list(rrc_mesh._send_queue)
check("a Stump reached over LoRa only: the radio", len(q) == 1 and q[0][5] is radio_if, q)
del rrc_mesh._send_queue[:]
NORAD, _ = stump("NoRadio", radio_if, {"rad": False, "rh": True, "lb": 1})
rrc_mesh._queue_lora(me, NORAD, lines)
q = list(rrc_mesh._send_queue)
check("a Stump whose radio is off: not the radio (it can't hear it)", len(q) == 1 and len(q[0]) == 4, q)
del rrc_mesh._send_queue[:]
rrc_mesh._peers.pop(NORAD)

# ---- 2. A live chain path stays against a shorter LoRa one ----
entry = [now, b"\x11" * 16, 2, now + 3600, chain_if, None, 5]
check("a live chain path stays against a shorter one over LoRa", Transport._keeps(entry, radio_if, now))
check("... not once it's unconfirmed past GRAVITY_KEEP_S",
      not Transport._keeps([now - 700] + entry[1:], radio_if, now))
chain_if.online = False
check("... nor with the chain link down", not Transport._keeps(entry, radio_if, now))
chain_if.online = True
check("a LoRa path doesn't hold against the chain", not Transport._keeps([now, b"\x22" * 16, 1, now + 3600, radio_if, None, 5],
                                                                       chain_if, now))

# ---- 3. Once on the radio for several Stumps ----
FAR2, _ = stump("Far2", radio_if, {"rad": True, "rh": True, "lb": 1})
OLD, _ = stump("Old", radio_if, {"rad": True, "rh": True})            # before beta.58: no "lb"
rrc_mesh._lb_install(me)
check("one broadcast group: the LoRa-only Stumps that take it", sorted(rrc_mesh._lb_peers()) == sorted([FAR1, FAR2]),
      rrc_mesh._lb_peers())
for h in (FAR1, FAR2, OLD):
    rrc_mesh._peers[h]["lora_sent_id"] = rrc.since(rrc.MESH_ROOM, 0)[-1]["id"] if rrc.since(rrc.MESH_ROOM, 0) else 0
rrc.post(rrc.MESH_ROOM, "rod", "one for all")
del rrc_mesh._send_queue[:]
rrc_mesh._flush_lora_broadcast(me)
q = list(rrc_mesh._send_queue)
check("the new line: one item for the radio, not one per Stump",
      sum(1 for i in q if i[0] == "lb" and "one for all" in i[1]) == 1 and all(i[0] == "lb" for i in q), q)
del rrc_mesh._send_queue[:]
rrc_mesh._flush_to_peer(me, FAR1, rrc_mesh._peers[FAR1])
check("... and Far1's own send has nothing left of it", not any("one for all" in str(i[2]) for i in rrc_mesh._send_queue),
      rrc_mesh._send_queue)
del rrc_mesh._send_queue[:]
rrc_mesh._flush_to_peer(me, OLD, rrc_mesh._peers[OLD])
check("an older Stump still gets its own copy", any("one for all" in str(i[2]) for i in rrc_mesh._send_queue),
      rrc_mesh._send_queue)
del rrc_mesh._send_queue[:]

# The packet itself, then heard by another Stump.
captured = []
real_packet = urns.packet.Packet


class Capture(real_packet):
    def send(self):
        captured.append((self.data, self.attached_interface))
        return True


urns.packet.Packet = Capture
rrc_mesh._send_item(("lb", "<rod> one for all", radio_if))
urns.packet.Packet = real_packet
check("sent on the radio only", len(captured) == 1 and captured[0][1] is radio_if, captured)

# The receiving side: another Stump (Far1) hearing this one.
src = bytes(me.delivery_destination.hash)
sender_h = src.hex()
receiver = LXMRouter(identity=far1_id)
receiver.register_delivery_identity(far1_id, display_name="Far1")
receiver.peers[src] = {"name": "CAM"}
Identity.remember(os.urandom(32), src, me.identity.get_public_key())
rrc.mark_stump(sender_h)
saved_router = rrc_mesh._lb["router"]
rrc_mesh._lb["router"] = receiver
rrc_mesh._peers.pop(sender_h, None)
data = captured[0][0]
before = rrc.since(rrc.MESH_ROOM, 0)[-1]["id"]
rrc_mesh._lb_in(data, None)
got = rrc.since(rrc.MESH_ROOM, before)
check("heard: shown as rod@CAM in #lora-mesh", any(m["nick"] == "rod@CAM" and m["body"] == "one for all" for m in got), got)
before = rrc.since(rrc.MESH_ROOM, 0)[-1]["id"]
rrc_mesh._lb_in(data, None)
check("the same packet played again: nothing", rrc.since(rrc.MESH_ROOM, before) == [])
from urns import umsgpack
f = umsgpack.unpackb(data)
f[3] += 1
f[4] = "<rod> forged"
rrc_mesh._lb_in(umsgpack.packb(f), None)
check("changed after signing: nothing", rrc.since(rrc.MESH_ROOM, before) == [])
rrc_mesh._from_stump(sender_h, rrc_mesh._peers[sender_h], "<rod> one for all", receiver, "#lora-mesh")
check("the same line again over Wi-Fi: shown once", rrc.since(rrc.MESH_ROOM, before) == [])
# The whole way: a real packet off the radio, into the receiving Stump's
# transport, to the broadcast destination.
rrc_mesh._lb["router"] = saved_router
radio_if.sent.clear()
rrc_mesh._send_item(("lb", "<rod> through the radio", radio_if))
raw = radio_if.sent[-1] if radio_if.sent else b""
check("a plain packet on the air, small enough", raw and len(raw) <= const.MTU, len(raw))
rrc_mesh._lb["router"] = receiver
# (Sent from this same process: its hash is in the dedup lists. Another
# Stump never sent it.)
Transport.packet_hashlist.clear()
Transport.packet_hashlist_prev.clear()
if Transport.identity is None:
    Transport.identity = Identity()    # (a running Stump's transport has one)
before = rrc.since(rrc.MESH_ROOM, 0)[-1]["id"]
Transport.inbound(raw, radio_if)
got = rrc.since(rrc.MESH_ROOM, before)
check("... heard through the radio layer: rod@CAM", any(m["nick"] == "rod@CAM" and m["body"] == "through the radio"
                                                       for m in got), got)
rrc_mesh._lb["router"] = saved_router

# ---- 4. No LoRa on mesh ----
WEB = "192.168.0.50"
i18n.set_lang(WEB, "en")
rrc.touch_user(WEB, nick="ann", room="main")
# No radio here nor on any Stump heard (the state lora_tick keeps, and the
# radios checked again).
real_paths = rrc_mesh._lora_paths
rrc_mesh._lora_paths = lambda: (False, False)
rrc_mesh._lora["state"] = "none"
r, room = rrc.handle_input(WEB, "main", "/join lora-mesh")
check("no LoRa: /join refused, said so", room is None and r and r[0].startswith("⊘ #lora-mesh no-lora")
      and "No LoRa on mesh" in r[0], r)
r, _ = rrc.handle_input(WEB, "lora-mesh", "anyone?")
check("... a line there refused too (nothing posted)", r and "No LoRa on mesh" in r[0]
      and not any(m["body"] == "anyone?" for m in rrc.since(rrc.MESH_ROOM, 0)), r)
check("... the room's topic says so", "No LoRa on mesh" in rrc.topic(rrc.MESH_ROOM, "en"))
check("... nor an app over the local network", not rrc.room_allows("ab" * 16, rrc.MESH_ROOM))
APP = "ab" * 16
rrc_mesh._peers.pop(APP, None)
p = rrc_mesh._get_peer(APP, "Sideband")
check("... which lands in #main instead, where the web chat reads it", p["room"] == rrc.DEFAULT_ROOM, p)
rrc_mesh._peers.pop(APP, None)
rrc_mesh._lora_paths = lambda: (True, False)
r, room = rrc.handle_input(WEB, "main", "/join lora-mesh")
check("a radio along the chain just heard (before the next tick): in", room == "lora-mesh", (r, room))
rrc_mesh._lora_paths = real_paths
rrc_mesh._lora["state"] = "up"

# ---- 5. Sends paced ----
sent = []
real_send = rrc_mesh._send_item
rrc_mesh._send_item = lambda item: sent.append(item)
del rrc_mesh._send_queue[:]
rrc_mesh._send_queue.extend([("x", i) for i in range(20)])
rrc_mesh._budget[0] = rrc_mesh.SENDS_PER_PASS
asyncio.run(rrc_mesh._drain("test"))
check("a burst: SENDS_PER_PASS this pass, the rest kept for the next",
      len(sent) == rrc_mesh.SENDS_PER_PASS and len(rrc_mesh._send_queue) == 20 - rrc_mesh.SENDS_PER_PASS,
      (len(sent), len(rrc_mesh._send_queue)))
rrc_mesh._send_item = real_send
del rrc_mesh._send_queue[:]

print("FAILURES", FAIL)
sys.exit(1 if FAIL else 0)

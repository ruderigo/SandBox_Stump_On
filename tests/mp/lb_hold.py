# A LoRa Stump's first lines after it starts (kit finding 19, 1.0.0-beta.72):
# its radio broadcast reaches the other Stumps before its beacon does. They
# kept dropping it ("not a Stump yet"); now they keep it a while and take it
# once the beacon says it's a Stump -- still checked (signature, played once).
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import time
import rrc, rrc_mesh
from urns import umsgpack
from urns.identity import Identity
rrc.LORA_NONE[0] = False
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:400]))
    if not c:
        FAIL.append(n)


class Dest:
    hash = bytes.fromhex("aa" * 16)


class Router:
    peers = {}
    delivery_destination = Dest()

    def send_message(self, *a, **k):
        pass


rrc.reset()
rrc_mesh._lb["router"] = Router()
gear = Identity()
G = "6e" * 16                      # Gearn's LXMF address (as its announce gave it)
Identity.remember(b"\x00" * 32, bytes.fromhex(G), gear.get_public_key())
boot = b"\x01\x02\x03\x04"


def lb(seq, text, ident=gear):
    sig = ident.sign(rrc_mesh._lb_signed(bytes.fromhex(G), boot, seq, text))
    return umsgpack.packb([b"lb1", bytes.fromhex(G), boot, seq, text, sig])


def lines():
    return [m["body"] for m in rrc.since(rrc.MESH_ROOM, 0) if m.get("kind") != "system"]


rrc_mesh._lb_in(lb(1, "<ann> hello from Gearn"), None)
check("a broadcast before its sender's beacon: not shown yet", lines() == [], lines())
check("... but kept", G in rrc_mesh._lb_held)
rrc_mesh._lb_in(lb(2, "<ann> second"), None)
rrc_mesh._lb_in(lb(3, "<ann> forged", Identity()), None)        # not signed by Gearn
rrc.mark_stump(G)
rrc_mesh._lb_release(G)
check("its beacon in: the lines kept meanwhile show, in order", lines() == ["hello from Gearn", "second"], lines())
check("... the forged one never", "forged" not in lines())
check("... nothing left kept", G not in rrc_mesh._lb_held)
rrc_mesh._lb_in(lb(2, "<ann> second"), None)
check("played again later: shown once", lines().count("second") == 1, lines())
rrc_mesh._lb_in(lb(4, "<ann> live"), None)
check("then as before: straight in", lines()[-1] == "live", lines())

# kept a while only, a few, from a few
rrc.reset()
H = "7f" * 16
rrc_mesh._lb_held.clear()
for i in range(10):
    rrc_mesh._lb_hold(H, b"x%d" % i)
check("a few kept per sender", len(rrc_mesh._lb_held[H]) == rrc_mesh.LB_HOLD_EACH)
for i in range(20):
    rrc_mesh._lb_hold("%032x" % i, b"y")
check("from a few senders", len(rrc_mesh._lb_held) <= rrc_mesh.LB_HOLD_FROM, len(rrc_mesh._lb_held))
rrc_mesh._lb_held.clear()
rrc_mesh._lb_hold(H, b"old")
rrc_mesh._lb_held[H][0] = (time.time() - rrc_mesh.LB_HOLD_S - 1, b"old")
rrc_mesh._lb_hold("8a" * 16, b"new")
check("too old: let go", H not in rrc_mesh._lb_held)

# the beacon path releases them (not only a test's call)
rrc.reset()
rrc_mesh._lb_held.clear()
src = open(sys.argv[1] + "/../../final_firmware/rrc_mesh.py").read()
check("every place a Stump is marked releases what was kept",
      src.count("rrc.mark_stump(h)\n            _lb_release(h)") == 1 and src.count("_lb_release(dest_hash_hex)") == 2)

print("FAILURES", FAIL)

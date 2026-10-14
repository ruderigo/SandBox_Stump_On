# #lora (once #lxmf) and #chained: the other Stumps of a chain land in
# #chained, are taken in from their beacon alone, and only chat lines go
# between Stumps -- each Stump's own people's, as "<nick@stump>" on the
# other side, never relayed twice, never joins and parts.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import rrc, rrc_mesh, i18n
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:500]))
    if not c:
        FAIL.append(n)


# the rename
rrc.reset()
check("#lora is the mesh room", rrc.MESH_ROOM == "lora" and rrc.room_exists("lora"))
check("#lxmf still reaches it", rrc.room_exists("lxmf") and rrc.create_room("#lxmf") == ("lora", None)
      and rrc.clean_room("LXMF") == "lora")
W = '192.168.4.50'
i18n.set_lang(W, 'en')
rrc.touch_user(W, nick='bob', room='main')
r, room = rrc.handle_input(W, 'main', '/join lxmf')
check("/join lxmf lands in #lora", room == "lora", (r, room))
check("no #chained outside a chain", not rrc.room_exists("chained"))
rrc.post("lxmf", "bob", "hi")
check("a line to #lxmf is in #lora", rrc.since("lora", 0)[-1]["body"] == "hi")

# a chain
rrc.open_chain_room()
check("#chained once in a chain", rrc.room_exists("chained") and "Stumps" in rrc.topic("chained", "en"))


class ChainHubInterface:
    pass


class LoRaInterface:
    pass


from urns.transport import Transport
from urns import const
LAPTOP = 'ab' * 16
FAR = 'ef' * 16          # a Stump heard over LoRa only
PHONE = 'cd' * 16


def path(h, iface):
    e = [0, b'', 1, 0, iface, None, 0]
    Transport.path_table[bytes.fromhex(h)] = e


path(LAPTOP, ChainHubInterface())
path(FAR, LoRaInterface())
path(PHONE, ChainHubInterface())
rrc.mark_stump(LAPTOP)
rrc.mark_stump(FAR)
sent = []


class Router:
    peers = {bytes.fromhex(LAPTOP): {"name": "Laptop"}}
    delivery_destination = None

    def send_message(self, dest, text, title="", fields=None):
        sent.append((bytes(dest).hex(), text, title))


R = Router()
rrc_mesh._take_in_chain_stumps(R)
p = rrc_mesh._peers.get(LAPTOP)
check("a Stump on the chain is taken in from its beacon, into #chained", p and p["room"] == "chained"
      and p["stump"] and p["nick"] == "Laptop", p)
check("its arrival shows in #chained", any("~Laptop" in m["body"] for m in rrc.since("chained", 0)))
check("a Stump heard over LoRa only isn't", FAR not in rrc_mesh._peers)
check("a phone isn't a Stump: not taken in", PHONE not in rrc_mesh._peers)

# out: only local chat lines
rrc.touch_user(W, nick='bob', room='chained')
rrc.post("chained", "bob", "hello chain")
rrc.post("chained", "bob", "waves", kind="action")
rrc.system("chained", rrc.ev_join("carol"))
rrc_mesh._flush_to_peer(R, LAPTOP, p)
batch = rrc_mesh._send_queue[-1]
text = batch[2]
check("to the other Stump: the chat lines", "<bob> hello chain" in text and "* bob waves" in text, text)
check("... not the notices", "✓" not in text and "carol" not in text, text)
check("... titled #chained", batch[3] == "#chained", batch)
del rrc_mesh._send_queue[:]


# in: a batch from the laptop
class Msg:
    source_hash = bytes.fromhex(LAPTOP)
    signature_validated = True
    fields = {}

    def __init__(self, t):
        self.t = t

    def content_as_string(self):
        return self.t


before = len(rrc.since("chained", 0))
rrc_mesh.on_message(R, Msg("<macOS> hello\n✓ ~LaBuche\n* macOS smiles\n✎ guest-b57d → macOS"))
new = rrc.since("chained", 0)[before:]
check("each line on its own, as nick@stump", [(m["nick"], m["body"], m["kind"]) for m in new]
      == [("macOS@Laptop", "hello", "msg"), ("macOS@Laptop", "smiles", "action")], new)
check("no greeting or 'moved' sent back to a Stump", rrc_mesh._send_queue == [], rrc_mesh._send_queue)
check("#lora stays quiet", not any("macOS" in m["nick"] for m in rrc.since("lora", 0)))
rrc_mesh._flush_to_peer(R, LAPTOP, p)
check("relayed lines never go back", rrc_mesh._send_queue == [], rrc_mesh._send_queue)

# a second Stump: it gets bob's lines, not the laptop's (it hears those itself)
OTHER = '12' * 16
path(OTHER, ChainHubInterface())
rrc.mark_stump(OTHER)
rrc_mesh._take_in_chain_stumps(R)
q = rrc_mesh._peers[OTHER]
rrc.post("chained", "bob", "to everyone")
rrc_mesh._flush_to_peer(R, OTHER, q)
text = rrc_mesh._send_queue[-1][2] if rrc_mesh._send_queue else ""
check("another Stump: local lines only", "<bob> to everyone" in text and "macOS" not in text, text)
del rrc_mesh._send_queue[:]

# a phone on LoRa still lands in #lora, and gets the room's notices
del Transport.path_table[bytes.fromhex(PHONE)]
peer = rrc_mesh._get_peer(PHONE, "Rod")
check("a LoRa user lands in #lora", peer["room"] == "lora" and not peer["stump"], peer)

# a Stump that talked before its path was known moves to #chained
LATE = '34' * 16
peer = rrc_mesh._get_peer(LATE, "Late")
check("unknown yet: #lora", peer["room"] == "lora")
rrc.mark_stump(LATE)
path(LATE, ChainHubInterface())
rrc_mesh._take_in_chain_stumps(R)
check("then moved to #chained", rrc_mesh._peers[LATE]["room"] == "chained" and rrc_mesh._peers[LATE]["stump"])
print('FAILURES:', FAIL)

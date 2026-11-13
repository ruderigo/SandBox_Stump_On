# A long names list between Stumps over the radio (1.0.0-beta.70): split
# between whole names, "[NAMES 1/2] ...", read back whole on the other
# side; never cut mid-name, never a piece shown as a line in #lora-mesh.
# (The kit: the S3's /names lost eKoms' and BGARE's people once each had
# about 10 -- the radio broadcast's 170-byte pieces.)
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import time
import rrc, rrc_mesh, discovery
rrc.LORA_NONE[0] = False
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:500]))
    if not c:
        FAIL.append(n)


rrc.reset()
NICKS = ["Ra", "guest-b57d", "Bavard", "Gaston", "Maxime", "eKoms-bot", "Lea", "Theo", "Zoe",
         "guest-91fe", "Nadia", "Olivier", "Ines", "Sam", "Hugo", "Camille", "Louis", "Emma",
         "Gabrielle", "Maximilien", "guest-0c3a", "Antoine", "Juliette", "Raphael"]
ENTRIES = sorted("%s~%08x" % (n, (i * 2654435761 + 7) % 2 ** 32) for i, n in enumerate(NICKS))
LINE = "[NAMES] " + " ".join(ENTRIES)
check("(the list is longer than a radio piece)", len(LINE.encode()) > rrc_mesh.RADIO_CHUNK, len(LINE))


def names_of(texts):
    """The entries of every names line in these texts, and the lines that aren't."""
    got, other = [], []
    for t in texts:
        for l in t.split("\n"):
            if l.startswith("[NAMES"):
                got += l[l.index("]") + 1:].split()
            else:
                other.append(l)
    return got, other


for limit in (rrc_mesh.RADIO_CHUNK, rrc_mesh.RADIO_CHUNK - 30):
    texts = rrc_mesh._radio_pieces(["<bob> hi", LINE, "<ann> yo"], limit, True)
    got, other = names_of(texts)
    check("in parts (%d bytes): every piece fits" % limit, all(len(t.encode()) <= limit for t in texts), [len(t.encode()) for t in texts])
    check("... every name whole, none lost", got == ENTRIES, got)
    check("... nothing else but the chat lines", other == ["<bob> hi", "<ann> yo"], other)
    heads = [l.split("]")[0] + "]" for t in texts for l in t.split("\n") if l.startswith("[NAMES")]
    n = len(heads)
    check("... numbered 1/%d to %d/%d" % (n, n, n), n >= 2 and heads == ["[NAMES %d/%d]" % (i + 1, n) for i in range(n)], heads)
    texts = rrc_mesh._radio_pieces([LINE], limit, False)
    got, other = names_of(texts)
    check("to an older Stump (%d bytes): one [NAMES] line of whole names" % limit,
          len(texts) == 1 and texts[0].startswith("[NAMES] ") and len(texts[0].encode()) <= limit
          and set(got) <= set(ENTRIES) and len(got) >= 5 and other == [], texts)
check("a short list: as before", rrc_mesh._radio_pieces(["[NAMES] a~1 b~2"], 170, True) == ["[NAMES] a~1 b~2"])
check("a long chat line: cut as before, each piece with its nick",
      all(t.startswith("<bob> ") for t in rrc_mesh._radio_pieces(["<bob> " + "x" * 400], 170, True)))

# -- read back on the other side ----------------------------------------------
EK = "e1" * 16
rrc.mark_stump(EK)
peer = rrc_mesh._get_peer(EK, "eKoms")
peer["stump"] = True
peer["room"] = peer["home_room"] = rrc.MESH_ROOM


def hear(text):
    rrc_mesh._from_stump(EK, peer, text, None, "#" + rrc.MESH_ROOM)


def listed():
    return sorted(n.split("@")[0] for n in rrc.remote_names(rrc.MESH_ROOM))


def lines_in_room():
    return [m["body"] for m in rrc.since(rrc.MESH_ROOM, 0) if m.get("kind") != "system"]


parts = [l for t in rrc_mesh._radio_pieces([LINE], 170, True) for l in t.split("\n")]
for l in parts:
    hear(l)
check("every part in: /names lists them all", listed() == sorted(NICKS), listed())
check("... and nothing of it as a line in #lora-mesh", lines_in_room() == [], lines_in_room())
contacts = set(r["nick"] for r in rrc_mesh._remote.values() if r["h"] == EK)
check("... its people DM contacts (as before: the first 20)", contacts == set(e.split("~")[0] for e in ENTRIES[:20]) and len(ENTRIES) > 20, contacts)

# the next list: its first part only so far -- nobody dropped meanwhile
hear(parts[0])
check("a new list's first part: nobody dropped yet (as contacts)",
      set(r["nick"] for r in rrc_mesh._remote.values() if r["h"] == EK) == contacts)
for l in parts[1:]:
    hear(l)
check("... all parts in again: all listed", listed() == sorted(NICKS), listed())

# a part lost on the air
check("(three parts or more)", len(parts) >= 3, len(parts))
hear(parts[0])
hear(parts[2])
first = sorted(e.split("~")[0] for e in parts[0][parts[0].index("]") + 1:].split())
check("a part missed: the parts after it wait for the next list", listed() == first, listed())
for l in parts:
    hear(l)
check("... the next list whole: all listed", listed() == sorted(NICKS), listed())

# someone left: dropped once the list is whole
small = [e for e in ENTRIES if not e.startswith("Emma~")]
for l in [l for t in rrc_mesh._radio_pieces(["[NAMES] " + " ".join(small)], 170, True) for l in t.split("\n")]:
    hear(l)
check("someone gone from the list: gone from /names and the contacts",
      "Emma" not in listed() and not any(r["nick"] == "Emma" for r in rrc_mesh._remote.values()), listed())

# never shown as a line
for bad in ("[NAMES 3/2] x~1", "[NAMESX] y~2", "[NAMES a/b] z~3", "[NAMES 0/2] w~4", "[NAMES"):
    hear(bad)
check("a broken names line: never a line in #lora-mesh", lines_in_room() == [], lines_in_room())
hear("[NAMES] Solo~12345678")
check("an older Stump's one-line list still read", listed() == ["Solo"], listed())

# -- who gets parts: by the beacon --------------------------------------------
NEW, OLD = "a2" * 16, "b3" * 16
discovery._known[NEW] = {"caps": {"lb": 1, "np": 1, "rad": True, "rh": True}}
discovery._known[OLD] = {"caps": {"lb": 1, "rad": True, "rh": True}}
check("a Stump whose beacon says np takes parts; one without doesn't",
      rrc_mesh._parts_capable(NEW) and not rrc_mesh._parts_capable(OLD) and not rrc_mesh._parts_capable("c4" * 16))
check("this Stump's beacon says np", discovery.caps().get("np") == 1)

# the radio broadcast to several Stumps: parts only if all of them take them
rrc.reset()
rrc.mark_stump(NEW)
rrc.mark_stump(OLD)
for h, n in ((NEW, "Newn"), (OLD, "Oldn")):
    q = rrc_mesh._get_peer(h, n)
    q["stump"] = True
for i, e in enumerate(ENTRIES):
    rrc.touch_user("%032x" % (i + 1), nick=e.split("~")[0], room=rrc.MESH_ROOM)
saved = (rrc_mesh._radio, rrc_mesh._chain_iface, rrc_mesh._lb["out"])
rrc_mesh._radio = lambda: "LORA"
rrc_mesh._chain_iface = lambda d: None
rrc_mesh._lb["out"] = object()
try:
    def broadcast():
        del rrc_mesh._send_queue[:]
        rrc_mesh._lb["roster"], rrc_mesh._lb["sent"] = None, None
        rrc_mesh._flush_lora_broadcast(None)
        return [it[1] for it in rrc_mesh._send_queue if it[0] == "lb"]
    texts = broadcast()
    got, _ = names_of(texts)
    check("broadcast with an older Stump among them: one [NAMES] line, whole names",
          sum(t.count("[NAMES") for t in texts) == 1 and "[NAMES] " in texts[0] and len(got) >= 5, texts)
    discovery._known[OLD]["caps"]["np"] = 1
    texts = broadcast()
    got, _ = names_of(texts)
    check("broadcast when all take parts: everyone, in parts", sorted(got) == sorted(e.split("~")[0] + "~" + rrc.identity_of("%032x" % (i + 1)) for i, e in enumerate(ENTRIES))
          and all(len(t.encode()) <= rrc_mesh.RADIO_CHUNK - 30 for t in texts) and "[NAMES 1/" in texts[0], texts)
finally:
    rrc_mesh._radio, rrc_mesh._chain_iface, rrc_mesh._lb["out"] = saved
    del rrc_mesh._send_queue[:]

# -- a Stump not known yet, over the radio: its room's scope isn't chat ---------
FD = "fd92" * 8


class Msg:
    source_hash = bytes.fromhex(FD)
    signature_validated = True
    fields = {}

    def __init__(self, t, title=""):
        self.t, self.title = t, title

    def content_as_string(self):
        return self.t

    def title_as_string(self):
        return self.title


class LoRaInterface:
    pass


from urns.transport import Transport
Transport.path_table[bytes.fromhex(FD)] = [0, b'', 1, 0, LoRaInterface(), None, 0]


class Router:
    peers = {}
    delivery_destination = None

    def send_message(self, *a, **k):
        pass


rrc.reset()
rrc_mesh.on_message(Router(), Msg("[ROOM] #bavard wifi 1", "#bavard"))
shown = [m for r in rrc.room_names() for m in rrc.since(r, 0) if "[ROOM]" in m.get("body", "")]
check("a Stump not known yet sends a room's scope over the radio: not a line anywhere", shown == [], shown)
check("... it's known as a Stump from it", rrc.is_stump(FD))

print("FAILURES", FAIL)

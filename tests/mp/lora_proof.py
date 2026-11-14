# A LoRa sender answers for its address with its messages' signatures
# (1.0.0-beta.71). An open Stump also takes a message it can't check yet
# (no announce heard: no key) -- as chat only: no role, not verified for a
# room's tier, /invite or /whoami; and it asks for that sender's announce.
# Once a message checks out: verified, as /auth over LoRa made it -- so
# FireFly needs no /auth over LoRa.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import time
import config
config.AUTH_ADMIN_PASSWORD = 'pw'
import plugins
plugins.load_all()
import rrc, rrc_mesh, mods, guard, i18n
from stumpid import core as sid
from stumpid import install as sinst
from urns.identity import Identity
from urns.transport import Transport
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:400]))
    if not c:
        FAIL.append(n)


asked = []
Transport.request_path = staticmethod(lambda h, on_interface=None: asked.append(bytes(h).hex()))
sent = []


class Router:
    peers = {}
    delivery_destination = None

    def send_message(self, *a, **k):
        pass


class Msg:
    def __init__(self, h, text, ok, title=""):
        self.source_hash = bytes.fromhex(h)
        self.signature_validated = ok
        self.timestamp = None
        self.fields = {}
        self._t, self._title = text, title

    def content_as_string(self):
        return self._t

    def title_as_string(self):
        return self._title


R = Router()


def say(h, text, ok):
    guard._buckets.clear()
    del rrc_mesh._send_queue[:]
    rrc_mesh.on_message(R, Msg(h, text, ok))
    return " ".join(str(it[2]) for it in rrc_mesh._send_queue if len(it) > 2)


OPAL = "0a" * 16           # an op of #bavard, on Sideband or FireFly over LoRa
CAT = "c3" * 16
FF = "f1" * 16             # a FireFly over LoRa
opal_id, ff_id = Identity(), Identity()
Identity.remember(b"\x00" * 32, bytes.fromhex(OPAL), opal_id.get_public_key())
Identity.remember(b"\x01" * 32, bytes.fromhex(FF), ff_id.get_public_key())
for h in (OPAL, CAT, FF):
    i18n.set_lang(h, "en")
sid.set_mode("open")
mods.reset("lora_proof.json")
rrc.create_room("bavard")
mods._load()["roles"]["h:" + OPAL] = {"label": "Opal", "op": ["bavard"], "mod": []}
say(OPAL, "/nick Opal", True)
say(OPAL, "/join bavard", True)
say(CAT, "/nick Cat", True)
say(CAT, "/join bavard", True)
check("(Opal, an op of #bavard over LoRa, their messages checking out)", mods.rank(OPAL, "bavard") == "op")

# -- someone sending as Opal's address, to a Stump that can't check it --------
del asked[:]
r = say(OPAL, "/kick #bavard Cat", False)
check("a message that can't be checked (open Stump): an op's command refused", rrc._users[CAT]["room"] == "bavard"
      and not any(k[1] == "bavard" for k in mods._kicked), r)
check("... no role meanwhile, not listed with @", mods.rank(OPAL, "bavard") is None and mods.mark(OPAL, "bavard") == "", mods.rank(OPAL, "bavard"))
check("... its announce asked for (a path request)", asked == [OPAL], asked)
r = say(OPAL, "still chat?", False)
check("... still taken as chat, as LXMF clients do", any(m["body"] == "still chat?" for m in rrc.since("bavard", 0)), r)
check("... asked once a minute, not every message", asked == [OPAL], asked)
r = say(OPAL, "/mute #bavard Cat", False)
check("... /mute refused too", not mods.muted(CAT, "bavard"), r)
r = say(OPAL, "/ban #bavard Cat", False)
check("... /ban refused too", not mods.banned(CAT, "bavard"), r)

# -- Opal's own next message checks out -----------------------------------------
r = say(OPAL, "/mute #bavard Cat 1", True)
check("a message that checks out: the op's command works again", mods.muted(CAT, "bavard"), r)
check("... the role back", mods.rank(OPAL, "bavard") == "op")
mods._load()["mutes"].clear()

# -- the admin password is its own proof --------------------------------------------
r = say(OPAL, "/mod pw #bavard Cat", False)
check("the admin's password works whatever the signature (the password proves it)",
      mods.rank(CAT, "bavard") == "mod", r)
mods._load()["roles"].pop("h:" + CAT, None)

# -- verified without /auth over LoRa: a room's tier, /invite, /whoami ---------
sid.set_room_tier("vault", "minted")
rrc.create_room("vault")
say(FF, "/nick Fly", True)
check("FireFly over LoRa, its messages checking out: verified as its identity, no /auth",
      sid.verified_identity_for(FF) == ff_id.hexhash, sid.verified_identity_for(FF))
ok, why = sid.can_join_room(FF, "vault")
check("... into a minted-only room", ok, why)
check("... /whoami says so", ff_id.hexhash in " ".join(sinst._cmd_whoami(FF)), sinst._cmd_whoami(FF))
sid.set_room_tier("club", "hybrid")
rrc.create_room("club")
say(FF, "/join club", True)
say(CAT, "/join club", True)
r = sinst._cmd_invite(FF, "/invite Cat", "club")
check("... /invite works", r and "verified" not in " ".join(r).lower(), r)
say(FF, "can't check this one", False)
check("a message from it that can't be checked: not verified meanwhile",
      sid.verified_identity_for(FF) is None and not sid.can_join_room(FF, "vault")[0], sid.verified_identity_for(FF))
check("... nor counted as identified (the access modes)", not sid._identified(FF))
say(FF, "checks out", True)
check("... the next that checks out: verified again", sid.verified_identity_for(FF) == ff_id.hexhash)
NEVER = "9e" * 16
check("a LoRa address never heard: not verified for a room's tier", sid.verified_identity_for(NEVER) is None
      and not sid.can_join_room(NEVER, "vault")[0])
check("... still counted as a LoRa client by the access modes (as before)", sid._identified(NEVER))

# -- /auth over LoRa: still works, as before ----------------------------------------
GH = "6a" * 16
g_id = Identity()
r = sinst._cmd_auth(GH, "/auth")
nonce = r[0].split()[-1]
r = sinst._cmd_auth(GH, "/auth %s %s" % (g_id.get_public_key().hex(), g_id.sign(nonce.encode()).hex()))
check("/auth over LoRa still works (typed by hand, older Stumps)", r[0].startswith("AUTH-OK") and sid.verified_identity_for(GH) == g_id.hexhash, r)

# -- hybrid: a message that can't be checked never gets here (as before) ---------------
sid.set_mode("hybrid")
U = "ab" * 16
say(U, "hello", False)
check("hybrid: a message that can't be checked is still ignored", U not in rrc_mesh._peers)
sid.set_mode("open")

# -- bounded ---------------------------------------------------------------------------
for i in range(200):
    rrc_mesh._note_proof("%032x" % i, Msg("%032x" % i, "", i % 2 == 0))
check("the tables stay small", len(rrc_mesh._proved) <= rrc_mesh.PROOF_MAX and len(rrc_mesh._unproved) <= rrc_mesh.PROOF_MAX
      and len(rrc_mesh._asked) <= rrc_mesh.PROOF_MAX + 1, (len(rrc_mesh._proved), len(rrc_mesh._unproved), len(rrc_mesh._asked)))

print("FAILURES", FAIL)

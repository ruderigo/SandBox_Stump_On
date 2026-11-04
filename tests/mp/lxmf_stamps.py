# LXMF stamps on the board's MicroPython (1.0.0-beta.53, opt-in): a stamp
# made in slices, a ticket's stamp, tickets kept and reloaded, and the
# switch in /admin -> Stump settings -> Announcing (off by default).
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import config
config.AUTH_ADMIN_PASSWORD = 'pw'
import i18n, settings
settings.CONFIG_FILE = "config.py"        # (the test's own folder, never the machine's root)
from urns import lxmf
from urns.identity import Identity
from urns.destination import Destination
import uhashlib
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:300]))
    if not c:
        FAIL.append(n)


check("off by default", lxmf.STAMPS[0] is False and settings.current()["LXMF_STAMPS"] is False)

# A stamp, made a slice at a time (cost 6 keeps the test quick).
mid = bytes(range(32))
job = lxmf.StampJob(mid, 6)
steps = 0
while not job.step(30):
    steps += 1
wb = bytearray(3000 * 256)
from urns.crypto.hkdf import hkdf
from urns import umsgpack
from urns.crypto.hashes import sha256
for n in range(3000):
    wb[n * 256:(n + 1) * 256] = hkdf(length=256, derive_from=mid, salt=sha256(mid + umsgpack.packb(n)), context=None)
h = uhashlib.sha256()
h.update(wb)
h.update(job.stamp)
d = h.digest()              # (once: on MicroPython a hash is final after digest())
check("a stamp, in slices: its hash has 6 leading zero bits", len(job.stamp) == 32 and d[0] < 4 and steps > 1,
      (steps, d[0]))
check("... the 768 KB block let go once found", job.wb is None)

# A ticket's stamp: one hash of the ticket and the message id.
t = b'T' * 16
check("a ticket's stamp", lxmf.ticket_stamp(t, mid) == sha256(t + mid)[:16])

# The router: costs from announces; tickets kept only when switched on.
me, them = Identity(), Identity()
r = lxmf.LXMRouter(identity=me)
r.register_delivery_identity(me, display_name="Stump")
dst = Destination(them, Destination.OUT, Destination.SINGLE, "lxmf", "delivery")
r.handle_announce(dst.hash, umsgpack.packb([b"Rod", 12, []]))
check("an announce's stamp cost kept", r.stamp_costs.get(dst.hash) == 12)
r.handle_announce(dst.hash, umsgpack.packb([b"Rod", None, []]))
check("... and dropped when it stops asking", dst.hash not in r.stamp_costs)


class M:
    signature_validated = True
    source_hash = dst.hash
    fields = {lxmf.FIELD_TICKET: [lxmf._wall() + 3600, t]}


r.TICKETS_FILE = ROOT + '/lxmf_tickets.bin'
r._take_ticket(M())
check("off: a ticket isn't kept", r.tickets == {})

# The switch, from /admin.
i18n.set_lang('192.168.4.50', 'en')
s, ct, b = admin_page()
check("the switch in /admin, off", "name='lxmf_stamps' value='1'>" in b and "LXMF stamps" in b, b[b.find('Announcing'):][:400])
ok, later = settings.apply({"LXMF_STAMPS": True})
check("switched on: applied at once, no restart", lxmf.STAMPS[0] is True and "LXMF_STAMPS" not in later, later)
r._take_ticket(M())
check("on: the ticket kept", r._ticket_for(dst.hash) == t)
r2 = lxmf.LXMRouter(identity=me)
r2.load_tickets(ROOT + '/lxmf_tickets.bin')
check("... and there after a restart", r2._ticket_for(dst.hash) == t)
lxmf.ROUTER[0] = r                         # (the node has one router; r2 stood for its restart)
s, ct, b = admin_page()
check("/admin: ticked, and what it did", "name='lxmf_stamps' value='1' checked>" in b and "tickets kept: 1" in b,
      b[b.find('LXMF stamps'):][:500])
r.stamp_costs[dst.hash] = 30
r.stamp_max_cost = 0
src = Destination(me, Destination.OUT, Destination.SINGLE, "lxmf", "delivery")
r.tickets.clear()
m = lxmf.LXMessage(destination=dst, source=src, content="x")
r._stamp_first(m, dst.hash, dst, None)
s, ct, b = admin_page()
check("/admin names who asks for more than it can make", "too costly here" in b and "Rod" in b, b[b.find('LXMF stamps'):][:600])
ok, later = settings.apply({"LXMF_STAMPS": False})
check("switched off again", lxmf.STAMPS[0] is False)
print('FAILURES:', FAIL)

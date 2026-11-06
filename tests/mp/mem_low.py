# Memory clean-ups only when they're needed (urns/mem.py, 1.0.0-beta.56):
# a full collection takes ~2 s on a WROVER's PSRAM, and the code forced one
# several times per packet. Now: plenty free, none; low, one.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
from urns import mem
import gc
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:300]))
    if not c:
        FAIL.append(n)


gc.collect()
free, used = gc.mem_free(), gc.mem_alloc()
check("a heap mostly free: not low", not mem.low(), (free, used))
before = mem.stats()["collected"]
check("... so asking for a clean-up doesn't do one", mem.collect() is False and mem.stats()["collected"] == before)
mem.LOW_FRACTION = 1.01                # everything counts as low
check("low: a clean-up is done", mem.collect() is True and mem.stats()["collected"] == before + 1)
mem.LOW_FRACTION = 0.0
mem.LOW_BYTES = free + used + 1        # less free than this: low whatever the share
check("... and under LOW_BYTES free, whatever the share", mem.low())
mem.LOW_FRACTION, mem.LOW_BYTES = 0.25, 96 * 1024
# The per-packet places call it, not gc.collect (a chain secret's sign and check)
import urns.interfaces as ifs, urns.transport as tr
src = open("urns/interfaces/__init__.py").read() + open("urns/transport.py").read()
check("the chain secret's sign and check no longer force one", "gc.collect()" not in src.replace("# ", ""), "")
print('FAILURES:', FAIL)

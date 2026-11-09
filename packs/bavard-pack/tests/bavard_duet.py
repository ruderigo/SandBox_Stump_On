# The Bavard pack (run it with tests/run.py beside this file): two bots in one process, on a fake
# clock and a fake Reticulum (announces and links are in-memory), through
# the real plugins.py and its posting budget. Alone they post numbers;
# once they hear each other they play the corpus turn by turn, losing and
# repeating nothing; a silent link sends them back to numbers, and they
# pick the play up where it was when they find each other again.
import sys, os, time, re
class _M: pass
_m = _M(); _m.aes = lambda *a, **k: None
sys.modules['ucryptolib'] = _m; sys.modules['cryptolib'] = _m
sys.path.insert(0, '.')
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

FAIL = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ' + repr(info)))
    if not cond: FAIL.append(name)

# A second copy of the plugin, so there are two bots (two names, two budgets).
os.system('rm -rf bavardb && cp -r bavard bavardb')

import config
config.BAVARD_NICK = 'Bavard'; config.BAVARDB_NICK = 'Bavard2'
config.BAVARD_ROOM = config.BAVARDB_ROOM = 'bavard'
config.BAVARD_PACE = config.BAVARDB_PACE = 'quick'

SD = os.getcwd() + '/sdx'
os.system('rm -rf %s && mkdir -p %s/shared %s/tools/bavard %s/home' % (SD, SD, SD, SD))
for f in ('plugins_state.json', 'plugins_loading'):
    try: os.remove(f)
    except OSError: pass
import fserv
fserv.SD_MOUNT = SD; fserv.SHARED_DIR = SD + '/shared'; fserv.TOOLS_DIR = SD + '/tools'
fserv.HOME_DIR = SD + '/home'; fserv.LEDGER_FILE = SD + '/l.json'; fserv.sd_ok = True

# A tiny corpus: two plays, so the bots also go from one to the next.
PLAYS = {
    'un': ('Pièce Une', [('S', 'I, 1'), ('ALCESTE', 'a1'), ('PHILINTE', 'p1'), ('ALCESTE', 'a2'),
                         ('ORONTE', 'o1'), ('ALCESTE', 'a3'), ('S', 'I, 2'), ('PHILINTE', 'p2'),
                         ('ORONTE', 'o2'), ('ORONTE', 'o3'), ('ALCESTE', 'a4')]),
    'deux': ('Pièce Deux', [('S', 'I, 1'), ('VALÈRE', 'v1'), ('ÉLISE', 'e1'), ('VALÈRE', 'v2'),
                            ('HARPAGON', 'h1'), ('ÉLISE', 'e2')]),
}
with open(SD + '/tools/bavard/plays.txt', 'w') as idx:
    for slug in ('un', 'deux'):
        title, recs = PLAYS[slug]
        n = len([r for r in recs if r[0] != 'S'])
        idx.write('%s\t%s\t%d\n' % (slug, title, n))
        with open(SD + '/tools/bavard/%s.txt' % slug, 'w') as f:
            f.write('T\t%s\n' % title)
            for who, text in recs:
                f.write(('S\t%s\n' % text) if who == 'S' else ('L\t%s\t%s\n' % (who, text)))
SCRIPT = []
for slug in ('un', 'deux'):
    SCRIPT += [(PLAYS[slug][0], w, t) for w, t in PLAYS[slug][1] if w != 'S']

import plugins

# ── a fake clock for the bots and the budget ──
class Clock:
    t = 0
    base = int(time.time())
    def ticks_ms(self): return self.t
    def ticks_add(self, a, b): return a + b
    def ticks_diff(self, a, b): return a - b
    def time(self): return self.base + self.t // 1000
    def time_ns(self): return (self.base * 1000 + self.t) * 1000000
    def gmtime(self, s=None): return time.gmtime(self.time() if s is None else s)
CLOCK = Clock()
plugins._now_ms = CLOCK.ticks_ms

class FakeAsync:
    async def sleep_ms(self, ms):
        CLOCK.t += int(ms)
        await asyncio.sleep(0)
    async def sleep(self, s):
        CLOCK.t += int(s * 1000)
        await asyncio.sleep(0)

# ── a fake Reticulum: announces and links in memory ──
HEX = {'bavard': 'aa' * 16, 'bavardb': 'bb' * 16}
NET, ANN, QUEUE = {}, [], []
WIRE = [True]                     # False: packets are lost, silently

class FakeDoor:
    def __init__(self, plugin):
        self.plugin = plugin; self.hexhash = HEX[plugin]; self._on_link = None
        NET[self.hexhash] = self
    def on_link(self, fn): self._on_link = fn
    def handle(self, path, fn): pass
    def announce(self, app_data=None):
        for pl, fn in ANN:
            if pl != self.plugin:
                QUEUE.append(lambda fn=fn: fn(self.hexhash, app_data))
        return True

class End:
    def __init__(self): self.peer = None; self.cb = None; self.open = True; self.close_cb = None
    def send(self, data):
        if not self.open: return False
        if WIRE[0]:
            p = self.peer
            QUEUE.append(lambda: p.cb and p.cb(bytes(data)))
        return True
    def on_packet(self, fn): self.cb = fn
    def on_close(self, fn): self.close_cb = fn
    def is_open(self): return self.open
    def remote_hex(self): return None
    def close(self):
        if self.open:
            self.open = self.peer.open = False
            if self.peer.close_cb: QUEUE.append(self.peer.close_cb)

LINKS = [0]
def fake_node(self, app, *aspects): return FakeDoor(self.name)
def fake_on_announce(self, app, aspects, fn): ANN.append((self.name, fn))
def fake_connect(self, dest_hex, app, aspects, identify=False):
    a, b = End(), End(); a.peer, b.peer = b, a
    door = NET[dest_hex]; LINKS[0] += 1
    QUEUE.append(lambda: door._on_link(b))
    return a
plugins.Api.node = fake_node
plugins.Api.on_announce = fake_on_announce
plugins.Api.connect = fake_connect

# Every post the budget sees, accepted or not.
POSTS, REFUSED = [], [0]          # what was posted; how many were refused (the heap)
_real_post = plugins._post
def spy(plugin, nick, room, text):
    ok = _real_post(plugin, nick, room, text)
    if ok:
        POSTS.append((CLOCK.t, plugin, text, ok))
    else:
        REFUSED[0] += 1
    return ok
plugins._post = spy

running = plugins.load_all()
check('both bots loaded', 'bavard' in running and 'bavardb' in running, (running, plugins.status()))
import bavard.install as A
import bavardb.install as B
for mod in (A, B):
    mod.time = CLOCK
    mod.asyncio = FakeAsync()
    mod._st['started'] = 0
    mod._st['next_ms'] = 0

def pump():
    while QUEUE:
        QUEUE.pop(0)()

DUE = {'ann': 0, 'flush': 0}
async def run(seconds, announce=True):
    end = CLOCK.t + seconds * 1000
    while CLOCK.t < end:
        for mod in (A, B):
            await mod._tick()
            pump()
        # The node's other timers, by time gone by (a bot's turn can jump
        # the clock by minutes).
        if announce and CLOCK.t - DUE['ann'] >= 60000:
            DUE['ann'] = CLOCK.t
            for mod in (A, B): mod._announce()
            pump()
        if CLOCK.t - DUE['flush'] >= 10000:
            DUE['flush'] = CLOCK.t
            for mod in (A, B): mod._flush(); mod._save_state()
        CLOCK.t += 1000

def window_max(plugin, span_ms=60000):
    """Most lines a bot got posted in any sliding window of span_ms."""
    ts = [t for t, pl, _, ok in POSTS if pl == plugin and ok]
    best, j = 0, 0
    for i in range(len(ts)):
        while ts[i] - ts[j] >= span_ms:
            j += 1
        best = max(best, i - j + 1)
    return best

def budget_held(since=0):
    """The budget is 6 a minute in a fixed window that starts with a
    plugin's first post: any sliding minute can see up to twice that
    (the end of one window, the start of the next), never more; and over
    the whole run, no more than 6 a minute on average."""
    ok = True
    for name in ('bavard', 'bavardb'):
        n = len([1 for t, pl, _, k in POSTS if pl == name and t >= since])
        mins = (CLOCK.t - since) // 60000 + 1
        ok = ok and window_max(name) <= 2 * plugins.POSTS_PER_MIN and n <= mins * plugins.POSTS_PER_MIN
    return ok

def molière(plugin, since=0):
    # (order posted, bot, speaker, line): POSTS is in the order the budget saw them.
    out = []
    for k, (t, pl, text, ok) in enumerate(POSTS):
        if pl == plugin and ok and t >= since and ' · ' in text:
            title_scene, _, rest = text.partition('] ')[2].partition(' · ')
            who, _, line = rest.partition(' — ')
            out.append((k, pl, who, line))
    return out

# ── 1. alone: numbers ──
asyncio.run(run(600, announce=False))
D4 = r'\d\d\d\d'   # MicroPython's re has no {n}
pat = re.compile(r'^\[~?' + D4 + r'-\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\dZ\] #(\d\d\d\d\d\d) ('
                 + '-'.join([D4] * 4) + ')$')
bad, seqs, seen = [], {}, {}
for t, pl, x, ok in POSTS:
    if not ok:
        continue
    m = pat.match(x)
    if m is None:
        bad.append(x)
        continue
    seqs.setdefault(pl, []).append(int(m.group(1)))
    seen.setdefault(pl, set()).add(m.group(2))
check('numbers: every line well formed', seqs and not bad, bad[:3])
for name in ('bavard', 'bavardb'):
    sq = seqs.get(name, [])
    check('numbers %s: seq 1..n, no gap' % name, sq and sq == list(range(1, len(sq) + 1)), sq[:10])
    check('numbers %s: all distinct' % name, len(seen.get(name, ())) == len(sq))
del bad, seqs, seen
check('the budget refused some (quick pace)', REFUSED[0] > 0 and A._st['dropped'] + B._st['dropped'] == REFUSED[0])
check('the budget held (alone)', budget_held(), (window_max('bavard'), window_max('bavardb')))
check('still alone', A._st['mode'] == 'solo' and B._st['mode'] == 'solo')

# ── 2. they hear each other: Molière ──
t_duet = CLOCK.t
asyncio.run(run(1800))
check('duet', A._st['mode'] == 'duet' and B._st['mode'] == 'duet', (A._st['mode'], B._st['mode']))
check('one link, made by the smaller hash', LINKS[0] == 1 and A._peer.get('up') and B._peer.get('up'))
lines = sorted(molière('bavard', t_duet) + molière('bavardb', t_duet))
said = [(w, l) for _, _, w, l in lines]
want = [(w, l) for _, w, l in SCRIPT]
cycle = (want * (len(said) // len(want) + 2))[:len(said)]
check('the plays in order, nothing lost or repeated', said == cycle and len(said) > len(want), (said[:12], len(said)))
sides = {}
for _, pl, w, _ in lines:
    sides.setdefault(w, set()).add(pl)
check('each character always the same bot', all(len(v) == 1 for v in sides.values()), sides)
check('characters alternate in order of appearance', sides.get('ALCESTE') == {'bavard'}
      and sides.get('PHILINTE') == {'bavardb'} and sides.get('ORONTE') == {'bavard'}
      and sides.get('VALÈRE') == {'bavard'} and sides.get('ÉLISE') == {'bavardb'}, sides)
check('went on to the next play and round again', A._st['plays_done'] + B._st['plays_done'] >= 3,
      (A._st['plays_done'], B._st['plays_done']))
check('scene and play in the line', any('Pièce Une I, 2 · PHILINTE — p2' in p[2] for p in POSTS), '')
check('numbers stopped during the duet', not [p for p in POSTS if p[0] > t_duet + 120000 and '#' in p[2] and p[3]])
check('the budget held (duet)', budget_held(t_duet), (window_max('bavard'), window_max('bavardb')))
check('round trip measured', A._st['rtt_ms'] is not None)

# ── 3. the link goes silent: back to numbers, then resume ──
where = dict(A._cur)
WIRE[0] = False
t_cut = CLOCK.t
asyncio.run(run(400, announce=False))
check('silent link: both back to numbers', A._st['mode'] == 'solo' and B._st['mode'] == 'solo',
      (A._st['mode'], B._st['mode']))
check('link drop counted', A._st['link_drops'] >= 1 and B._st['link_drops'] >= 1)
check('numbers again', [p for p in POSTS if p[0] > t_cut and '#' in p[2] and p[3]])
WIRE[0] = True
t_back = CLOCK.t
asyncio.run(run(900))
check('together again', A._st['mode'] == 'duet' and B._st['mode'] == 'duet' and LINKS[0] == 2)
after = sorted(molière('bavard', t_back) + molière('bavardb', t_back))
allsaid = [(w, l) for _, _, w, l in sorted(molière('bavard', t_duet) + molière('bavardb', t_duet))]
check('the play picks up where it was: still nothing lost or repeated',
      allsaid == (want * (len(allsaid) // len(want) + 2))[:len(allsaid)] and after, (len(allsaid), allsaid[-8:]))

# ── 4. what's left on the card and on the page ──
A._flush(); B._flush(); A._save_state()
logs = [n for n in os.listdir(SD + '/plugins/bavard') if n.startswith('log-')]
kinds = set()
if logs:
    with open(SD + '/plugins/bavard/' + logs[0]) as f:
        for line in f:
            kinds.add(line[:6])
check('transcript on the card, OK and DROP lines', {'OK   [', 'DROP [', '--   ['} <= kinds, (logs, kinds))
check('state saved', '"cur"' in open(SD + '/plugins/bavard/state.json').read())
st = A._stats()
check('stats', st['log_lines_lost'] == 0 and st['mode'] == 'duet' and st['partner']['nick'] == 'Bavard2' and st['posted'] > 0
      and st['dropped_by_budget'] >= 0 and st['errors'] == 0, st)
check('no tick errors on B', B._st['errors'] == 0, B._st['errors'])
class Req: lang = 'en'
html = A._page(Req())
check('page', 'Bavard' in html and 'Pièce' in html, html[:200])
code, js, ct = A._stats_json(Req())
check('stats.json', code == 200 and '"lines_played"' in js and ct == 'application/json')
print('most lines in a sliding minute: %d (budget %d a fixed minute)' % (
    max(window_max('bavard'), window_max('bavardb')), plugins.POSTS_PER_MIN))
print('lines played: %d, posted %d, refused by the budget %d' % (
    st['lines_played'] + B._st['lines_played'], A._st['posted'] + B._st['posted'],
    A._st['dropped'] + B._st['dropped']))
print('FAILURES:', FAIL)

import sys, os, time
class _M: pass
_m = _M(); _m.aes = lambda *a, **k: None
sys.modules['ucryptolib'] = _m; sys.modules['cryptolib'] = _m
sys.path.insert(0, '.')
import config
config.AUTH_ADMIN_PASSWORD = 'pw'; config.FSERVBOT_OP_PASSWORD = 'op'; config.DICE_SIDES = 20
SD = os.getcwd() + '/sdx'
os.system('rm -rf %s && mkdir -p %s/shared %s/tools %s/home' % (SD, SD, SD, SD))
for f in ('plugins_state.json', 'plugins_loading'):
    try: os.remove(f)
    except OSError: pass
import fserv
fserv.SD_MOUNT = SD; fserv.SHARED_DIR = SD + '/shared'; fserv.TOOLS_DIR = SD + '/tools'; fserv.HOME_DIR = SD + '/home'
fserv.LEDGER_FILE = SD + '/l.json'; fserv.sd_ok = True
import plugins, rrc, i18n
FAIL = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ' + repr(info)))
    if not cond: FAIL.append(name)
running = plugins.load_all()
check('loaded', running == ['dice', 'fservbot', 'stumpid'], running)
st = {p['name']: p for p in plugins.status()}
check('crashy failed', st['crashy']['state'] == 'failed' and 'setup broke' in st['crashy']['error'], st['crashy'])
check('crashy gate removed', all(g[2] != 'crashy' for g in plugins._gates))
check('future refused', st['future']['state'] == 'failed' and 'API 99' in st['future']['error'], st['future'])
check('marker after load is running-phase', plugins._read_marker() == {'plugin': None})
import dice.install as D
check('refusals', [t for t in D.TICKS if t.startswith('refused')] and 'NOT REFUSED' not in D.TICKS, D.TICKS)
check('setting', 'setting=20' in D.TICKS, D.TICKS)
check('storage', ('storage=' + SD + '/plugins/dice') in D.TICKS, D.TICKS)
check('mem measured', st['dice']['mem'] is not None, st['dice'])
A, B, M = '192.168.4.50', '192.168.4.51', 'ab' * 16
i18n.set_lang(B, 'en'); i18n.set_lang(A, 'en')
rrc.touch_user(A, nick='alice'); rrc.touch_user(B, nick='bob')
def say(cid, text):
    plugins._cmd_use.clear()
    return rrc.handle_input(cid, rrc.get_user(cid)['room'], text)
def lastlines(n=3):
    room = rrc.get_user(A)['room']
    return [(m['nick'], m['body']) for m in rrc.since(room, 0)][-n:]
r, _ = say(A, '/roll 2d6')
check('/roll reply', r == ['(only you see this)'], r)
check('/roll posted as plugin nick', lastlines(1) == [('Dé', 'alice rolls 2d6: 4')], lastlines())
r, _ = say(A, '!roll 3d6')
check('!roll line posted, then bot', lastlines(2) == [('alice', '!roll 3d6'), ('Dé', 'alice rolls 3d6: 4')], lastlines())
check('!roll reply', r == ['(only you see this)'], r)
r, _ = say(A, '!nosuch')
check('unknown !word is just text', r == [] and lastlines(1) == [('alice', '!nosuch')], (r, lastlines()))
r, _ = say(A, '/boom')
check('crash -> generic error', len(r) == 1 and 'dice' in r[0] and 'problem' in r[0], r)
r, _ = say(A, 'any dice?')
check('listener reply', r == ['try !roll'] and D.SEEN.get('alice'), (r, D.SEEN))
r, _ = say(A, 'BLOCKME')
check('gate blocks', r == ['⧗ — blocked by flood'] and lastlines(1)[0][1] != 'BLOCKME', (r, lastlines()))
r, _ = say(A, 'DROPME')
check('gate drops silently', r == [] and lastlines(1)[0][1] != 'DROPME', (r, lastlines()))
r, _ = say(A, '/hi')
check('plugin strings', r == ['hello alice'], r)
r, _ = say(A, '/many')
check('web gets all lines', len(r) == 5 and len(r[0]) > 250, len(r))
r, _ = say(A, '/join')
check('core /join untouched', 'join' in r[0].lower() or 'usage' in r[0].lower() or r, r)
# rate limit
plugins._cmd_use.clear()
rrc.handle_input(A, 'lobby', '/hi'); r, _ = rrc.handle_input(A, 'lobby', '/hi')
check('command rate limit', r and r[0].startswith('⧗ — '), r)
# post budget
import barkeep, time
barkeep.plugin_posts_reset()
room_ = rrc.get_user(A)['room']
before = len(rrc.since(room_, 0))
oks = [plugins._post('dice', 'Dé', room_, 'p%d' % i) for i in range(10)]
check('post budget: 6 a minute posted, 3 wait their turn, the next refused', oks == [True] * 9 + [False], oks)
check('... only the 6 are in the room yet', [m['body'] for m in rrc.since(room_, 0)[before:]] == ['p%d' % i for i in range(6)])
barkeep.plugin_posts_tick()
check('... the minute not over: still waiting', len(barkeep._plugin_queue['dice']) == 3)
# The minute moves on for the first two lines: two of the waiting ones go out.
s_ = barkeep._plugin_sent['dice']
s_[0] = s_[1] = time.ticks_add(time.ticks_ms(), -61000)
barkeep.plugin_posts_tick()
check('... a rolling minute: as lines age out, waiting ones go, in order',
      [m['body'] for m in rrc.since(room_, 0)[before:]][6:] == ['p6', 'p7'] and len(barkeep._plugin_queue['dice']) == 1,
      [m['body'] for m in rrc.since(room_, 0)[before:]])
barkeep._plugin_sent['dice'] = []
barkeep.plugin_posts_tick()
check('... and the last one; the queue gone', rrc.since(room_, 0)[-1]['body'] == 'p8' and 'dice' not in barkeep._plugin_queue)
# stump.post(): from a timer, through the same budget (plugin API 4).
api_ = plugins.Api('crier'); api_.nick = 'Crieur'
barkeep.plugin_posts_reset()
r_ = [api_.post('hear %d' % i, room_) for i in range(6)]
last_ = rrc.since(room_, 0)[-1]
check('stump.post(): posts as the plugin nick, a bot line', all(r_) and last_['nick'] == 'Crieur' and last_.get('bot') is True
      and last_['body'] == 'hear 5', last_)
check('... and shares the budget: the 7th waits', api_.post('hear 6', room_) is True and len(barkeep._plugin_queue['crier']) == 1)
check('... no room given: main', plugins.Api('x').post('hi') and rrc.since('main', 0)[-1]['body'] == 'hi')
barkeep.plugin_posts_reset()
r_ = [api_.post('now %d' % i, room_, wait=False) for i in range(7)]
check('wait=False: over the budget refused at once, nothing queued', r_ == [True] * 6 + [False]
      and 'crier' not in barkeep._plugin_queue, r_)
check('plugin API 4', plugins.API_VERSION == 4)
# help
h = rrc.help_lines('en')
check('help web', '!roll 2d6 -- throw some dice' in h and '/many -- five lines' in h and '/boom' not in h and '/secret <pw>' in h and h[-1].startswith('✓'), h[-6:])
hm = rrc.help_lines('en', mesh=True)
check('help mesh compact', 'extras: /fshelp !many !roll /secret' in hm, hm[-3:])
# mesh capping
import rrc_mesh
rrc.LORA_NONE[0] = False  # #lora-mesh open: as on a Stump with a radio (the gate: lora_mesh_test)
rrc_mesh._peers[M] = {'nick': 'meshy', 'room': 'lxmf', 'home_room': 'lxmf', 'via_propagation': True}
rrc.touch_user(M, nick='~meshy', room='lxmf'); i18n.set_lang(M, 'en')
plugins._cmd_use.clear()
r, _ = rrc.handle_input(M, 'lxmf', '/many')
check('mesh capped to 2 lines, 200 chars', len(r) == 2 and len(r[0]) == 200 and r[0].endswith('…'), [len(x) for x in r])
seen = []
plugins.Api('probe').on_message(lambda ctx: seen.append((ctx.is_mesh, ctx.via_propagation)), 99)
plugins._plugins['probe'] = plugins._record('probe', 'setup'); plugins._plugins['probe']['state'] = 'on'
rrc.handle_input(M, 'lxmf', 'hello from mesh')
check('ctx.is_mesh / via_propagation', seen == [(True, True)], seen)
# DMs don't reach listeners
seen.clear(); say(B, '/msg alice secret')
check('listeners never see DMs', seen == [], seen)
# off switch via chat
r, _ = say(A, '/admin pw plugin')
check('plugin list', any(x.startswith('dice: on') for x in r), r)
r, _ = say(A, '/admin pw plugin off dice')
check('off now', r == ['dice is off'], r)
r, _ = say(A, '/roll')
check('off -> unknown', r[0].startswith('? /roll'), r)
check('off persisted', 'dice' in plugins._load_state()['off'])
check('help drops off plugin', not any('roll' in l for l in rrc.help_lines('en')))
r, _ = say(A, '/admin pw plugin on dice')
check('on again', r == ['dice is on'], r)
r, _ = say(A, '/admin pw plugin off stumpid')
check('stumpid protected', 'access control' in r[0], r)
r, _ = say(A, '/admin pw plugin off fservbot')
check('fservbot off now', r == ['fservbot is off'], r)
say(A, '/admin pw plugin on fservbot')
r, _ = say(A, '/admin wrong plugin off dice')
check('wrong pw refused', 'not authorised' in r[0], r)
r, _ = say(A, '/admin pw plugin off ghost')
check('no such', r == ['no plugin called ghost'], r)
check('service', plugins.service_lookup('dice') == {'sides': 6})
# timers
import uasyncio as asyncio
async def run_sched():
    t = asyncio.create_task(plugins.scheduler_loop())
    await asyncio.sleep(5.2)
    t.cancel()
asyncio.run(run_sched())
check('sync timer ran', D.TICKS.count('tick') >= 2, D.TICKS.count('tick'))
at = [t for t in plugins._timers if t['plugin'] == 'dice' and t['every'] == 1][0]
check('async timer off after 3 fails', at['fails'] == 3, at)
pi = plugins.public_info()
check('public_info', pi['trigger'] == '!' and [p['name'] for p in pi['plugins']] == ['dice', 'fservbot', 'stumpid']
      and 'roll' in pi['plugins'][0]['commands'] and '/p/dice/' in pi['plugins'][0]['pages'], pi)
r, _ = say(A, '!secret hunter2')
check('trigger=False not run from !', r == [], r)
r, _ = say(A, '/secret hunter2')
check('slash runs', r == ['pw=hunter2'], r)
r, _ = say(A, '/names')
check('on_result rewrites', r and r[0] == r[0].upper(), r)
r, _ = say(A, 'BLOCKME'); 
check('on_result not after gate', r == ['⧗ — blocked by flood'], r)
print('FAILURES:', FAIL)

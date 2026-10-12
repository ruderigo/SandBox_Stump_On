import sys, json, re, hashlib, shutil, zipfile, builtins
from pathlib import Path
import tempfile
W = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(W)); import provisioner as P
fw = W / 'final_firmware'
FAIL = []
def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:500]))
    if not c: FAIL.append(n)
# manifest excludes plugin files but keeps plugin.json
files = P.manifest_candidates(fw)
check('manifest keeps plugin.json', 'fservbot/plugin.json' in files and 'stumpid/plugin.json' in files)
check('manifest drops plugin files', not any(f.startswith(('fservbot/', 'stumpid/')) and not f.endswith('plugin.json') for f in files))
check('api', P.firmware_plugin_api(fw) == 1)
check('core manifest current', P._check_local_files_current(fw.resolve()) == [], P._check_local_files_current(fw.resolve()))
for n in ('fservbot', 'stumpid'):
    check(n + ' verifies', P.verify_plugin(fw / n) == ([], []), P.verify_plugin(fw / n))
# packs: folder + zip of same -> listed once; zip extraction
P.PACKS_DIR = Path(tempfile.mkdtemp()) / 'packs'
P.PACK_CACHE_DIR = Path(tempfile.mkdtemp()) / 'cache'
shutil.rmtree(P.PACKS_DIR, ignore_errors=True); P.PACKS_DIR.mkdir()
shutil.copytree(W / 'packs/tavern-pack', P.PACKS_DIR / 'tavern-pack')
with zipfile.ZipFile(P.PACKS_DIR / 'rnfs-pack-1.0.zip', 'w') as z:
    for f in (W / 'packs/rnfs-pack').rglob('*'):
        if f.is_file(): z.write(f, 'rnfs-pack/' + str(f.relative_to(W / 'packs/rnfs-pack')))
with zipfile.ZipFile(P.PACKS_DIR / 'evil.zip', 'w') as z:
    z.writestr('../../escape.txt', 'x')
(P.PACKS_DIR / 'notapack').mkdir()
packs = P.discover_packs()
check('discover', sorted(p['spec']['name'] for p in packs) == ['rnfs', 'tavern'], [p['spec']['name'] for p in packs])
for p in packs:
    r, w = P.check_pack(p, 1); check('check ' + p['spec']['name'], r is None and w == [], (r, w))
    r, w = P.check_pack(p, 0); check('refuse old firmware ' + p['spec']['name'], r and 'needs plugin API' in r, r)
# tamper -> warning
t = [p for p in packs if p['spec']['name'] == 'tavern'][0]
f = t['dir'] / 'tavern/install.py'; f.write_text(f.read_text() + '\nimport time\ntime.sleep(5)\n')
r, w = P.check_pack(t, 1)
check('tamper + lint noticed', any('changed since' in x for x in w) and any('time.sleep' in x for x in w), w)
P.describe_pack(t, 1)
# fake mpremote for install + upload
calls = []
def fake_run(cmd, timeout=None, **kw):
    calls.append(cmd)
    if 'exec' in cmd and any('SHA:' in str(c) for c in cmd): return True, 'SHA:none'
    if cmd[-2:] == ['cat', ':themes.json']: return True, '{"old": {"label": "Old", "colors": {"--bg": "#000"}}}'
    if 'exec' in cmd and any('def walk' in str(c) for c in cmd):
        sizes = {}
        for c in calls:
            if 'cp' in c and not str(c[-1]).startswith(':/sd'):
                sizes[c[-1][1:]] = Path(c[-2]).stat().st_size
        return True, repr(sizes)
    return True, ''
P.run = fake_run
pushed_theme = {}
orig = P._merge_board_themes
def spy(port, themes):
    r = orig(port, themes)
    for c in calls[::-1]:
        if c[-1] == ':themes.json' and 'cp' in c:
            pushed_theme.update(json.loads(Path(c[-2]).read_text())); break
    return r
P._merge_board_themes = spy
ok = P.install_packs('/dev/fake', packs)
cps = [c for c in calls if 'cp' in c]
dests = [c[-1] for c in cps]
check('plugin files to flash', ':tavern/install.py' in dests and ':rnfs/strings.py' in dests and ':tavern/plugin.json' not in dests, dests)
check('tools to SD', ':/sd/tools/rnfs-0.1.1-py3-none-any.whl' in dests and ':/sd/tools/rnfs-INSTALL.txt' in dests, dests)
check('themes merged', set(pushed_theme) == {'old', 'tavern'} and pushed_theme['tavern']['colors']['--bg'] == '#1a120b', pushed_theme)
check('install ok', ok)
# upload_stump_app includes built-in plugins
calls.clear()
P.resolve_path = lambda *a, **k: fw
P.ask_yes_no = lambda *a, **k: True
P.install_tools_on_node = lambda port: None
ok = P.upload_stump_app('/dev/fake')
dests = [c[-1] for c in calls if 'cp' in c]
check('upload has core', ':plugins.py' in dests and ':rrc.py' in dests)
check('upload has builtin plugins', ':stumpid/strings.py' in dests and ':fservbot/templates.py' in dests and ':fservbot/plugin.json' not in dests and ':fservbot/README.md' not in dests, [d for d in dests if 'fserv' in d or 'stumpid' in d])
check('upload ok', ok)
# remove_plugin refuses core
check('remove refuses urns', P.remove_plugin('/dev/fake', 'urns') is False)
print('FAILURES', FAIL)

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
BOARD_CONFIG = ['CONFIG:yes']
def fake_run(cmd, timeout=None, **kw):
    calls.append(cmd)
    if 'exec' in cmd and any('SHA:' in str(c) for c in cmd): return True, 'SHA:none'
    if 'exec' in cmd and any('CONFIG:yes' in str(c) for c in cmd): return True, BOARD_CONFIG[0]
    if 'exec' in cmd and any("'DIRS:'" in str(c) for c in cmd): return True, 'DIRS:flasher,rnfs,notes.txt'
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
check('tools to SD', ':/sd/tools/rnfs/rnfs-0.1.1-py3-none-any.whl' in dests and ':/sd/tools/rnfs/README.md' in dests, dests)
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
check('update keeps the node config', ':config.py' not in dests, [d for d in dests if 'config' in d])
calls.clear(); BOARD_CONFIG[0] = 'CONFIG:no'
P.upload_stump_app('/dev/fake')
check('fresh board gets a config', ':config.py' in [c[-1] for c in calls if 'cp' in c])
calls.clear(); BOARD_CONFIG[0] = 'CONFIG:yes'; sys.argv.append('--replace-config')
P.upload_stump_app('/dev/fake')
check('--replace-config replaces it', ':config.py' in [c[-1] for c in calls if 'cp' in c])
sys.argv.remove('--replace-config')
# --skip-tools still brings the sections' READMEs up to date (sections on the card only)
calls.clear()
P.refresh_tool_readmes('/dev/fake')
rd = [c[-1] for c in calls if 'cp' in c]
check('READMEs refreshed, every language', ':/sd/tools/flasher/README.fr.md' in rd and ':/sd/tools/flasher/README.es.md' in rd
      and ':/sd/tools/rnfs/README.fr.md' in rd and ':/sd/tools/flasher/README.md' in rd, rd)
check('no README for a section not on the card', not any('/provisioner/' in d or '/firefly/' in d for d in rd), rd)
# Stump on a computer: the config.py block (docs/PC.md)
b = P._pc_config_block({"pc_hotspot_name": "Apt 3B", "pc_heltec": "usb", "pc_heltec_port": "COM5",
                        "chain": {"enabled": True, "parent_ip": "192.168.4.1"}})
ns = {"CONFIG": {"interfaces": [{"type": "WiFiSerialInterface"}, {"type": "UDPInterface"}]}}
exec(b, ns)
check('pc block: USB Heltec replaces the Wi-Fi bridge', [i["type"] for i in ns["CONFIG"]["interfaces"]] ==
      ["UDPInterface", "RNodeSerialInterface"] and ns["CONFIG"]["interfaces"][1]["port"] == "COM5", ns["CONFIG"])
check('pc block: hotspot, parent, own clock', ns["PC_HOTSPOT_NAME"] == "Apt 3B" and ns["PC_CHAIN_PARENT_IP"] == "192.168.4.1"
      and ns["CONFIG"]["time_sync"] == {"enabled": False} and ns["PC_HTTP_PORT"] == 80)
ns = {"CONFIG": {"interfaces": [{"type": "WiFiSerialInterface", "target_host": "192.168.137.2"}]}}
exec(P._pc_config_block({"pc_heltec": "wifi"}), ns)
check('pc block: a Wi-Fi Heltec is kept', ns["CONFIG"]["interfaces"][0]["target_host"] == "192.168.137.2")
# remove_plugin refuses core
check('remove refuses urns', P.remove_plugin('/dev/fake', 'urns') is False)
print('FAILURES', FAIL)

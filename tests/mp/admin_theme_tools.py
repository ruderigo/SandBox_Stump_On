# /admin: the theme for everyone (saved on the board, wins over config.py,
# applied at once), and deleting tools from the card by file or section.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import theme
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:400]))
    if not c:
        FAIL.append(n)


theme.SITE_THEME_FILE = ROOT + '/site_theme.json'
theme.set_site_theme(None)
setup = theme.configured_theme()
def page_theme():
    b = req('/about')[2]
    i = b.find("data-theme='")
    return b[i + 12:b.find("'", i + 12)]

s, ct, b = req('/admin', b'admin_pass=pw')
check("admin: theme for everyone", "action='/admin/theme'" in b and "name='theme' value='oled'" in b, b[:200])
check("admin: as set up is ticked", "name='theme' value='' checked" in b)
check("admin: browser-only section says so", b.find("action='/admin/theme'") < b.find("stumpSetTheme('amber')"))

s, ct, b = req('/admin/theme', b'admin_pass=wrong&theme=oled')
check("wrong password refused", s.startswith('403') and theme.site_theme() == setup, s)
other = 'oled' if setup != 'oled' else 'phosphor'
s, ct, b = req('/admin/theme', ('admin_pass=pw&theme=' + other).encode())
check("saved for everyone", s.startswith('200') and theme.site_theme() == other and theme.admin_choice() == other, s)
check("this response shows it, and clears this browser's own", "localStorage.removeItem('stump_theme')" in b
      and "data-theme='" + other + "'" in b)
check("every page has it", page_theme() == other, page_theme())
check("saved on the board", open(theme.SITE_THEME_FILE).read().find(other) > 0)
check("ticked on the form now", ("name='theme' value='" + other + "' checked") in req('/admin', b'admin_pass=pw')[2])
theme._ADMIN_CHOICE = theme._load_admin_choice()
check("survives a restart", theme.site_theme() == other)
s, ct, b = req('/admin/theme', b'admin_pass=pw&theme=nonsense')
check("unknown theme not saved", theme.site_theme() == other)
s, ct, b = req('/admin/theme', b'admin_pass=pw&theme=')
check("back to as set up", theme.site_theme() == setup and theme.admin_choice() is None and page_theme() == setup)
try:
    os.stat(theme.SITE_THEME_FILE); gone = False
except OSError:
    gone = True
check("its file removed", gone)

# Tools
T = fserv.TOOLS_DIR
for d in ('rnfs', 'flasher'):
    os.mkdir(T + '/' + d)
for rel in ('rnfs/a.whl', 'rnfs/README.md', 'flasher/esptool-bundle.js', 'flasher/esptool-js-LICENSE.txt', 'loose.txt'):
    open(T + '/' + rel, 'w').write('x')
open(ROOT + '/secret.txt', 'w').write('keep')
s, ct, b = req('/admin', b'admin_pass=pw')
check("admin: tools listed", "action='/admin/tools'" in b and "name='d' value='rnfs'" in b
      and "name='f' value='flasher/esptool-bundle.js'" in b and "name='f' value='loose.txt'" in b, b[b.find('/admin/tools'):][:600])
s, ct, b = req('/admin/tools', b'admin_pass=wrong&d=rnfs')
check("tools: wrong password refused", s.startswith('403') and os.listdir(T + '/rnfs'))
s, ct, b = req('/admin/tools', b'admin_pass=pw&d=rnfs&f=rnfs%2Fa.whl&f=flasher%2Fesptool-bundle.js&f=..%2Fsecret.txt&f=flasher&d=..&d=%2E')
left = sorted(os.listdir(T))
check("tools: section and file deleted", left == ['flasher', 'loose.txt'] and os.listdir(T + '/flasher') == ['esptool-js-LICENSE.txt'], left)
check("tools: nothing outside tools/", open(ROOT + '/secret.txt').read() == 'keep')
check("tools: counted", "3 " in b or "3 file" in b or "3 fichier" in b, b[:100])
print("FAILURES", FAIL)

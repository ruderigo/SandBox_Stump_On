# This Stump's language (1.0.0-beta.67): config.py's DEFAULT_LANG, changed
# in /admin -> Stump settings and by Arborist; for visitors who haven't
# picked one and for what's posted for everyone (the fserv bot), at once.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import config
config.AUTH_ADMIN_PASSWORD = 'pw'
import i18n, settings
settings.CONFIG_FILE = "config.py"        # (the test's own folder)
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:300]))
    if not c:
        FAIL.append(n)


check("French by default (no DEFAULT_LANG in config.py)", i18n.DEFAULT_LANG == "fr" and settings.current()["DEFAULT_LANG"] == "fr")
base = {"node_name": "Kit", "bot_name": "BarKeep", "greeting": "", "economy": "free", "auth_mode": "open", "f_chat": "1"}
ch, bad = settings.parse_form(dict(base, default_lang="en"))
check("/admin's form: English", bad is None and ch["DEFAULT_LANG"] == "en", (ch, bad))
ch2, bad2 = settings.parse_form(dict(base, default_lang="de"))
check("... a language it doesn't speak: refused", ch2 is None and bad2 == "default_lang", bad2)
ch3, bad3 = settings.parse_form(dict(base))
check("... a form without it (an older page): left as it is", bad3 is None and "DEFAULT_LANG" not in ch3, ch3)
saved, later = settings.apply(ch)
cfg = open("config.py").read()
check("saved in config.py, applied at once (no restart)", saved and "DEFAULT_LANG = 'en'" in cfg and i18n.DEFAULT_LANG == "en"
      and "DEFAULT_LANG" not in later, (saved, later))
check("a visitor who hasn't picked one gets it", i18n.get_lang("someone-new") == "en")
i18n.set_lang("picky", "es")
check("... one who picked their own keeps theirs", i18n.get_lang("picky") == "es")
import fservbot.core as fc
check("the fserv bot posts in it", fc._ctx()["lang"] == "en")
import admin_web
html = admin_web._render_admin_setup_section("en", "pw")
check("/admin shows it, English checked", "name='default_lang' value='en' checked" in html and "This Stump's language" in html, html[:200])
# After a restart, config.py's is the one.
import sys as _s
for m in ("i18n",):
    _s.modules.pop(m, None)
config.DEFAULT_LANG = "es"
import i18n as i18n2
check("after a restart: config.py's DEFAULT_LANG", i18n2.DEFAULT_LANG == "es")
config.DEFAULT_LANG = "xx"
_s.modules.pop("i18n", None)
import i18n as i18n3
check("... one it doesn't speak: French", i18n3.DEFAULT_LANG == "fr")
print("FAILURES", FAIL)

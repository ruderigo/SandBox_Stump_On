# The Simple pack (1.0.0-beta.53): sentences, on request, for people on
# LXMF apps that don't know Stumps. Through the core's mesh_out hook
# (plugin API 2) and the chat's gates, as rrc_mesh calls them.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import config
config.AUTH_ADMIN_PASSWORD = 'pw'
import plugins, rrc, rrc_mesh, i18n
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:400]))
    if not c:
        FAIL.append(n)


plugins.load_all()
check("the pack starts (plugin API 2)", plugins._plugins.get('simple', {}).get('state') == 'on', plugins._plugins.get('simple'))
H = 'cd' * 16           # someone on Sideband
F = 'ef' * 16           # someone on FireFly
for h in (H, F):
    i18n.set_lang(h, 'en')

LINES = "→ #lora-mesh\n<rod> anyone near the market?\n✓ ~maria\n[DM] <maria>: I am, 5 min away"
t, title = plugins.mesh_out(F, LINES, "#lora-mesh")
check("first message to anyone: unchanged, plus a one-time tip", t.startswith(LINES) and "simple" in t.split("\n")[-1], t)
t, title = plugins.mesh_out(F, LINES, "#lora-mesh")
check("... only once", t == LINES, t)

rrc.touch_user(H, nick='sid', room='lora-mesh')
rrc_mesh._peers[H] = {"nick": "sid", "room": "lora-mesh", "stump": False}
replies, _ = rrc.handle_input(H, 'lora-mesh', 'simple')
check("\"simple\" from an LXMF app: switched on, said so", replies and "plain sentences" in replies[0], replies)
check("... not posted to the room", not any(m.get('body') == 'simple' for m in rrc.since('lora-mesh', 0)))
t, title = plugins.mesh_out(H, LINES + "\n✎ rod → bob\n✎ #main soup tonight\n⊖ ghost\n* rod waves\n⧗ — Too fast, wait a moment.\n[DM] <bob>: ♪ 5.0 s", "#lora-mesh")
want = ["You're now in #lora-mesh.", "rod: anyone near the market?", "maria joined.",
        "Private message from maria: I am, 5 min away", "rod is now called bob.",
        "The topic of #main is now: soup tonight", "No one here is called ghost.", "* rod waves",
        "Too fast, wait a moment.", "Private message from bob: (a 5.0 s voice note, to hear on a Stump app or the Wi-Fi)"]
check("then sentences", t.split("\n") == want, t.split("\n"))
check("... the title kept", title == "#lora-mesh")
t, _ = plugins.mesh_out(H, "AUTH-CHALLENGE " + "00" * 16, "")
check("what an app reads is never touched", t == "AUTH-CHALLENGE " + "00" * 16, t)
i18n.set_lang(H, 'fr')
t, _ = plugins.mesh_out(H, "✓ ~maria", "")
check("in the person's language", t == "maria est arrivé·e.", t)
i18n.set_lang(H, 'en')
replies, _ = rrc.handle_input(H, 'lora-mesh', 'simple off')
t, _ = plugins.mesh_out(H, "✓ ~maria", "")
check("\"simple off\": back to the short lines", "short lines" in replies[0] and t == "✓ ~maria", (replies, t))
replies, _ = rrc.handle_input('v' + 'w' * 20, 'main', 'simple')
check("on the web, \"simple\" is just a word in the room",
      replies == [] and any(m.get('body') == 'simple' for m in rrc.since('main', 0)), replies)

# The core never hands another Stump's messages to the hook.
seen = []
plugins._mesh_out.insert(0, [0, 0, 'simple', lambda h, t, ti: seen.append(h)])
S = 'ab' * 16
rrc_mesh._peers[S] = {"nick": "Bûche2", "stump": True}


class R:
    def send_message(self, *a, **k):
        pass


rrc_mesh._send_item((R(), bytes.fromhex(S), "x"))
rrc_mesh._send_item((R(), bytes.fromhex(H), "x"))
check("to another Stump: not reworded; to a person: through the hook", seen == [H], seen)
plugins._mesh_out.pop(0)

plugins.set_enabled('simple', False)
replies, _ = rrc.handle_input(H, 'lora-mesh', 'simple')
t, _ = plugins.mesh_out(H, "✓ ~maria", "")
check("switched off in /admin: nothing reworded", t == "✓ ~maria", t)
print('FAILURES:', FAIL)

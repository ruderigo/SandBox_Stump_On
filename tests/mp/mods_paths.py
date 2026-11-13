# Room moderation on every way in (mods.py; the review of 12 Nov 2026):
# an op on Sideband/MeshChat (over the mesh), a mesh user banned from a
# room, /names over the mesh; the web page's refresh (banned or kicked:
# back to #main; a total ban: nothing to read); someone on another Stump
# muted then unmuted; voice notes under a total ban; and with the access
# modes (stumpid) on.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import time, json
import rrc, rrc_mesh, mods, guard, i18n
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:400]))
    if not c:
        FAIL.append(n)


mods.reset("mods_paths.json")
ADA, CAT, DEE = "a1" * 16, "c3" * 16, "d4" * 16           # people on apps (LXMF), over the mesh
B1 = 'v' + '1' * 20                                         # a browser (the Stump's cookie)
rrc.create_room("bavard")
for cid, nick in ((ADA, "Ada"), (CAT, "Cat"), (DEE, "Dee")):
    rrc.touch_user(cid, nick=nick, room="bavard")
    i18n.set_lang(cid, "en")
i18n.set_lang(B1, "en")


def peer(cid, nick, room="bavard"):
    p = rrc_mesh._peers.get(cid)
    if p is None:
        p = rrc_mesh._peers[cid] = {"nick": nick, "room": room, "home_room": "lora-mesh", "last_sent_id": 0,
                                    "last_dm_id": 0, "last_seen": time.time()}
    return p


def mesh(cid, nick, text):
    """A line from someone on Sideband/MeshChat, as the mesh hands it in."""
    guard._buckets.clear()
    p = peer(cid, nick)
    lines, new_room = rrc_mesh._handle(cid, p, text)
    if new_room:
        p["room"] = new_room
    return " ".join(lines), p


def web(path, who=B1, body=b'', method=None):
    s, ct, b = req(path, body=body, headers=('Cookie: stump_v=' + who,), method=method)
    try:
        return s, json.loads(b)
    except ValueError:
        return s, b


# -- 17. over the mesh -----------------------------------------------------------
say_admin = rrc.handle_input(DEE, "bavard", "/op pw #bavard Ada")
check("(Ada, on Sideband, made op of #bavard)", mods.rank(ADA, "bavard") == "op", say_admin)
r, _ = mesh(ADA, "Ada", "/mute #bavard Cat")
check("an op on Sideband: /mute over the mesh works", mods.muted(CAT, "bavard"), r)
r, _ = mesh(CAT, "Cat", "still talking?")
check("... the muted mesh user's line isn't posted", r.startswith("✗") and not any(m["body"] == "still talking?" for m in rrc.since("bavard", 0)), r)
mesh(ADA, "Ada", "/unmute #bavard Cat")
r, pc = mesh(ADA, "Ada", "/kick #bavard Cat too loud")
check("an op on Sideband: /kick over the mesh: Cat out of #bavard (their mesh room too)",
      rrc._users[CAT]["room"] == "main" and pc is not None and rrc_mesh._peers[CAT]["room"] == "main", (r, rrc_mesh._peers[CAT]["room"]))
for k in list(mods._kicked):
    mods._kicked[k] = time.time() - 1
r, _ = mesh(ADA, "Ada", "/ban #bavard Cat")
check("an op on Sideband: /ban over the mesh", mods.banned(CAT, "bavard"), r)
r, pc = mesh(CAT, "Cat", "/join bavard")
check("a mesh user banned from #bavard: /join refused over the mesh", r.startswith("✗") and pc["room"] != "bavard", r)
mesh(ADA, "Ada", "/unban #bavard Cat")
mesh(CAT, "Cat", "/join bavard")
mesh(ADA, "Ada", "/mod #bavard Dee")
r, _ = mesh(CAT, "Cat", "/names")
check("/names over the mesh: @ for an op, % for a mod", "@Ada" in r and "%Dee" in r, r)

# -- 18. the web page's refresh ------------------------------------------------------
rrc.touch_user(B1, nick="Bea", room="bavard")
s, p = web('/rrc/poll?room=bavard&since=0')
check("(a browser in #bavard)", isinstance(p, dict) and p.get("room") == "bavard", p if not isinstance(p, dict) else p.get("room"))
mods._kicked[(mods._key(B1), "bavard")] = time.time() + 60
s, p = web('/rrc/poll?room=bavard&since=0')
check("the web page, kicked from #bavard: its next refresh is in #main", isinstance(p, dict) and p.get("room") == "main",
      p.get("room") if isinstance(p, dict) else p)
mods._kicked.clear()
rrc.touch_user(B1, room="bavard")
mods._load()["bans"]["bavard"] = {mods._key(B1): {"label": "Bea", "by": "t", "at": 0}}
s, p = web('/rrc/poll?room=bavard&since=0')
check("... banned from #bavard: back in #main", isinstance(p, dict) and p.get("room") == "main", p.get("room") if isinstance(p, dict) else p)
mods._load()["bans"].clear()
rrc.post("main", "Ada", "a line everyone sees")
mods._load()["bans"]["*"] = {mods._key(B1): {"label": "Bea", "by": "t", "at": 0}}
s, p = web('/rrc/poll?room=main&since=0')
check("... a total ban: its page gets nothing (no lines, rooms, people), and says why",
      isinstance(p, dict) and p.get("banned") is True and p.get("messages") == [] and p.get("users") == [] and p.get("rooms") == []
      and p.get("topic"), p if not isinstance(p, dict) else {k: p.get(k) for k in ("banned", "messages", "topic")})
s, p = web('/rrc/send', body=b'let me in', method='POST')
check("... and what it sends isn't posted", not any(m["body"] == "let me in" for m in rrc.since("main", 0)), p)
mods._load()["bans"].clear()

# -- 20. someone on another Stump: muted, then unmuted ------------------------------
H = "e5" * 16
mods._load()["mutes"]["bavard"] = {"r:@%s:zoe" % H: {"label": "zoe@aleph", "by": "Ada", "at": 0}}
m1 = rrc.post("bavard", "zoe@aleph", "muted words", via=H)
check("someone on another Stump muted here: their lines don't show here", m1 is None)
mods._load()["mutes"].clear()
m2 = rrc.post("bavard", "zoe@aleph", "free again", via=H)
check("... unmuted: they show again", m2 is not None)

# -- 21. a voice note under a total ban -----------------------------------------------
mods._load()["bans"]["*"] = {mods._key(DEE): {"label": "Dee", "by": "t", "at": 0}}
r = rrc.send_voice(DEE, "Ada", 3, bytes(200))
check("a total ban: no voice note either", r and r[0].startswith("✗") and not any("♪" in d.get("body", "") for d in rrc.dms_since(ADA, 0)), r)
mods._load()["bans"].clear()

# -- with the access modes on (stumpid) ------------------------------------------------
try:
    import stumpid.core as sc
    before = sc.AUTH_MODE
    sc.set_mode("hybrid")
    mods._load()["bans"]["bavard"] = {mods._key(CAT): {"label": "Cat", "by": "t", "at": 0}}
    lines, _ = rrc.handle_input(CAT, "bavard", "banned but verified?")
    check("hybrid mode: a ban still holds", lines and lines[0].startswith("✗") and not any(m["body"] == "banned but verified?" for m in rrc.since("bavard", 0)), lines)
    r, _ = mesh(ADA, "Ada", "/unban #bavard Cat")
    check("hybrid mode: an op's commands still work", not mods.banned(CAT, "bavard"), r)
    sc.set_mode("mandatory")
    r, _ = mesh(ADA, "Ada", "/mode #bavard +t")
    check("mandatory mode: an op's commands still work", mods.topic_locked("bavard"), r)
    sc.set_mode(before)
except ImportError:
    check("stumpid present for the access-mode checks", False)

print("FAILURES", FAIL)

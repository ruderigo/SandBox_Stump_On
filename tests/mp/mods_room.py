# Room moderation (mods.py, 1.0.0-beta.64): ops named by the admin, mods
# named by an op, /kick /mute /ban /mode +t, who may do what to whom, held
# by an identity (never a nick), kept across a restart -- and the admin
# password never shown. Modelled on rrcd's rules (see mods.py).
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import time
import rrc, mods, guard
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:400]))
    if not c:
        FAIL.append(n)


mods.reset("mods_test.json")
try:
    import os
    os.remove("mods_test.json")
except OSError:
    pass

ADA = "a1" * 16                      # an app identity (LXMF address): Sideband, NomadNet...
CAT = "c3" * 16
DEE = "d4" * 16
BEN = "p:ben"                        # a registered profile, logged in on the web
GUEST = "web-guest-1"                # a guest: a browser, no identity
for cid, nick in ((ADA, "Ada"), (CAT, "Cat"), (DEE, "Dee"), (BEN, "Ben"), (GUEST, "Gus")):
    rrc.touch_user(cid, nick=nick, room="main")
rrc.create_room("bavard")
for cid in (ADA, CAT, BEN, GUEST):
    rrc.touch_user(cid, room="bavard")


def say(cid, text, room="bavard"):
    guard._buckets.clear() if hasattr(guard, "_buckets") else None
    lines, _ = rrc.handle_input(cid, room, text)
    return " ".join(lines)


def bodies(room="bavard"):
    return " ".join(m["body"] for m in rrc.since(room, 0))


# -- the admin names ops ---------------------------------------------------------
r = say(ADA, "/op nope #bavard Ada")
check("/op with a wrong admin password: refused, no one named", "✗" in r and mods.rank(ADA, "bavard") is None, r)
r = say(CAT, "/kick Ada")
check("/kick with no room: its usage, not taken as a wrong password", "✗" not in r and "kick" in r, r)
r = say(CAT, "/op pw #bavard Ada")
check("the admin (the password first): Ada is op in #bavard", mods.rank(ADA, "bavard") == "op" and mods.rank(ADA, "main") is None, r)
check("... said in the room, the password nowhere in it", "@ Ada" in bodies() and " pw " not in " " + bodies() + " ", bodies()[-200:])
r = say(CAT, "/op pw #bavard Gus")
check("a guest can't be op (no identity, no profile)", mods.rank(GUEST, "bavard") is None and "Gus" in r, r)
r = say(ADA, "/op #bavard Cat")
check("an op can't name ops (only the admin)", "✗" in r and mods.rank(CAT, "bavard") is None, r)

# -- an op names mods, in their scope only ---------------------------------------
r = say(ADA, "/mod #bavard Ben")
check("Ada (op of #bavard) makes Ben, a profile, mod in #bavard", mods.rank(BEN, "bavard") == "mod", r)
r = say(ADA, "/mod -stump Dee")
check("... not in every room: her role is one room's", "✗" in r and mods.rank(DEE, "main") is None, r)
r = say(BEN, "/mod #bavard Cat")
check("a mod names no one", "✗" in r and mods.rank(CAT, "bavard") is None, r)
names = say(CAT, "/names")
check("/names: an op as @Ada, a mod as %Ben", "@Ada" in names and "%Ben" in names and "@Cat" not in names, names)
roles = say(CAT, "/roles")
check("/roles (anyone): who's op and mod, with the start of their hash", "@Ada (a1a1a1a1)" in roles and "%Ben (profile ben)" in roles, roles)

# -- a mod: kick and mute, not ban; not on an op ---------------------------------
r = say(BEN, "/ban #bavard Cat")
check("a mod can't ban", "✗" in r, r)
r = say(BEN, "/kick #bavard Ada")
check("a mod can't kick an op", "✗" in r and rrc._users[ADA]["room"] == "bavard", r)
r = say(BEN, "/mute #bavard Cat")
check("Ben (mod) mutes Cat in #bavard", mods.muted(CAT, "bavard") and not mods.muted(CAT, "main"), r)
r = say(CAT, "hello?")
check("... Cat can't write in #bavard", r.startswith("✗") and "hello?" not in bodies(), r)
r = say(CAT, "/me waves")
check("... nor /me", r.startswith("✗"), r)
r = say(CAT, "still here", room="main")
check("... but can in #main", "still here" in bodies("main"), r)
r = say(BEN, "/unmute #bavard Cat")
r2 = say(CAT, "back")
check("/unmute: Cat writes again", not mods.muted(CAT, "bavard") and "back" in bodies(), (r, r2))
r = say(BEN, "/mute #bavard Cat 5")
e = mods._load()["mutes"]["bavard"]["h:" + CAT]
check("/mute for 5 minutes: until then", mods.muted(CAT, "bavard") and 290 < e["until"] - time.time() <= 300, e)
e["until"] = int(time.time()) - 1
check("... and over after", not mods.muted(CAT, "bavard"))
r = say(BEN, "/kick #bavard Cat being rude")
check("Ben kicks Cat: back in #main, said with why", rrc._users[CAT]["room"] == "main" and "⊖ Cat" in bodies() and "being rude" in bodies(), r)
r = say(CAT, "/join bavard", room="main")
check("... not back in for a minute", r.startswith("✗") and rrc._users[CAT]["room"] == "main", r)
for k in list(mods._kicked):
    mods._kicked[k] = time.time() - 1
r = say(CAT, "/join bavard", room="main")
check("... then back in", "✗" not in r, r)
rrc.touch_user(CAT, room="bavard")
rrc.touch_user(DEE, room="main")
r = say(ADA, "/kick pw #main Dee")
check("#main can't be kicked from, even by the admin (everyone's way back in): /mute instead",
      "✗" not in r and "/mute" in r and rrc._users[DEE]["room"] == "main", r)
r = say(BEN, "/kick #main Cat")
check("... and a mod of #bavard has no say in #main", "✗" in r, r)

# -- an op: ban; on a mod too; not on another op ---------------------------------
r = say(ADA, "/ban #bavard Cat")
check("Ada bans Cat from #bavard: out, can't write there", mods.banned(CAT, "bavard") and rrc._users[CAT]["room"] == "main", r)
r = say(CAT, "/join bavard", room="main")
check("... can't join", r.startswith("✗"), r)
r = say(CAT, "sneaky", room="bavard")
check("... nor write there (a client that says it's there)", r.startswith("✗") and "sneaky" not in bodies(), r)
b = say(ADA, "/bans")
check("/bans: Cat, by Ada", "Cat" in b and "Ada" in b, b)
b = say(GUEST, "/bans")
check("/bans for someone with no role: nothing shown", "Cat" not in b, b)
r = say(ADA, "/unban #bavard Cat")
check("/unban", not mods.banned(CAT, "bavard"), r)
r = say(ADA, "/mute #bavard Ben")
check("an op mutes a mod", mods.muted(BEN, "bavard"), r)
say(ADA, "/unmute #bavard Ben")
say(CAT, "/op pw #bavard Dee")
rrc.touch_user(DEE, room="bavard")
r = say(ADA, "/kick #bavard Dee")
check("an op can't kick another op", "✗" in r and rrc._users[DEE]["room"] == "bavard", r)
r = say(CAT, "/kick pw #bavard Dee")
check("the admin can (the password first)", rrc._users[DEE]["room"] == "main", r)

# -- a guest: kicked, muted, banned by their visit ---------------------------------
r = say(ADA, "/ban #bavard Gus")
r2 = say(GUEST, "hi")
check("a guest banned: by their visit, said so", mods.banned(GUEST, "bavard") and r2.startswith("✗") and "Gus" in r, (r, r2))
say(ADA, "/unban #bavard Gus")

# -- +t: the topic by ops and mods ---------------------------------------------------
r = say(BEN, "/mode #bavard +t")
check("a mod can't set +t", "✗" in r and not mods.topic_locked("bavard"), r)
r = say(ADA, "/mode #bavard +t")
check("an op sets +t", mods.topic_locked("bavard"), r)
r = say(CAT, "/topic cats only")
check("+t: no topic from someone with no role", r.startswith("✗") and rrc.topic("bavard") != "cats only", r)
r = say(BEN, "/topic tea and talk")
check("+t: a mod sets it", rrc.topic("bavard") == "tea and talk", r)
r = say(CAT, "/topic", room="bavard")
check("+t: anyone still reads it", "tea and talk" in r, r)

# -- -stump: every room ------------------------------------------------------------
r = say(CAT, "/op pw -stump Dee")
check("the admin: Dee op in every room of this Stump", mods.rank(DEE, "main") == "op" and mods.rank(DEE, "bavard") == "op", r)
r = say(DEE, "/mute -stump Cat", room="main")
check("Dee mutes Cat everywhere", mods.muted(CAT, "main") and mods.muted(CAT, "bavard"), r)
r = say(ADA, "/unmute -stump Cat")
check("Ada (one room's op) can't undo an everywhere mute", "✗" in r and mods.muted(CAT, "main"), r)
say(DEE, "/unmute -stump Cat", room="main")
r = say(DEE, "/ban -stump Ada", room="main")
check("Dee can't ban Ada everywhere: Ada is an op somewhere", "✗" in r and not mods.banned(ADA, "main"), r)

# -- the same person on LoRa and on the web (a FireFly's /auth) ----------------------
rrc.link_same("web-ada", ADA)
rrc.touch_user("web-ada", nick="Ada", room="bavard")
check("Ada on the web after /auth: the same op", mods.rank("web-ada", "bavard") == "op")

# -- someone on another Stump: hidden here -------------------------------------------
H = "e5" * 16
mods._load()["bans"].setdefault("bavard", {})["r:@%s:zoe" % H] = {"label": "zoe@aleph", "by": "Ada", "at": 0}
m = rrc.post("bavard", "zoe@aleph", "from afar", via=H)
m2 = rrc.post("bavard", "yan@aleph", "also afar", via=H)
check("banned here, on another Stump: their lines don't show here; others' do", m is None and m2 is not None)
r = say(ADA, "/kick #bavard zoe@aleph")
check("/kick someone on another Stump: says /mute or /ban instead", "✗" not in r, r)

# -- kept across a restart --------------------------------------------------------------
mods.reset("mods_test.json")
check("after a restart: the roles, bans and +t are still there",
      mods.rank(ADA, "bavard") == "op" and mods.rank(BEN, "bavard") == "mod" and mods.topic_locked("bavard"))

# -- the admin can't be locked out by a ban ------------------------------------------------
say(DEE, "/ban -stump Cat", room="main")
r = say(CAT, "/unban pw -stump Cat", room="main")
check("banned, the admin (the password) still unbans -- even themselves", not mods.banned(CAT, "main"), r)

# -- a nick taken over: the role stays with its identity ----------------------------------
rrc._users.pop(ADA, None)
rrc._users.pop("web-ada", None)
rrc.touch_user("web-imp", nick="Ada", room="bavard")
r = say("web-imp", "/ban #bavard Ben")
check("Ada gone, a guest takes the nick \"Ada\": none of her powers", "✗" in r and not mods.banned(BEN, "bavard")
      and mods.rank("web-imp", "bavard") is None, r)
check("... and /names doesn't mark the impostor", "@Ada" not in say(CAT, "/names"))

# -- a total ban: in #main or "-stump", out of the chat altogether ---------------------------
rrc.touch_user(GUEST, nick="Gus", room="main")
rrc.touch_user(CAT, nick="Cat", room="bavard")
r = say(CAT, "/ban pw #main Gus", room="bavard")
check("banned in #main: a total ban, off the lists at once", mods.total(GUEST) and "Gus" not in rrc.users_in_room("main"), r)
check("... can't write in #main", say(GUEST, "anyone?", room="main").startswith("✗") and "anyone?" not in bodies("main"))
check("... nor any other command: /names, /rooms, /nick, /join, /msg",
      all(say(GUEST, c, room="main").startswith("✗") for c in ("/names", "/rooms", "/nick Gusto", "/join bavard", "/msg Cat hi")))
check("... /help still answers", not say(GUEST, "/help", room="main").startswith("✗"))
rrc.touch_user(GUEST, room="main")
check("... and isn't listed even if it polls again", "Gus" not in rrc.users_in_room("main") and "Gus" not in say(CAT, "/names", room="main"))
say(CAT, "/unban pw #main Gus", room="main")
check("/unban: back in", not mods.total(GUEST) and not say(GUEST, "back", room="main").startswith("✗"))

# ... on the mesh: answered once, then quiet (LoRa airtime), nothing sent to them
import rrc_mesh
say(CAT, "/ban pw -stump Dee", room="main")
peer = {"room": "main", "home_room": "main", "nick": "Dee", "last_sent_id": 0, "last_dm_id": 0}
r1, _ = rrc_mesh._handle(DEE, peer, "hello")
r2, _ = rrc_mesh._handle(DEE, peer, "hello again")
check("on the mesh, banned -stump: told once, then nothing (each answer is airtime)", r1 and r1[0].startswith("✗") and r2 == [], (r1, r2))
rrc.post("main", "Cat", "a line Dee mustn't get")
before = len(rrc_mesh._send_queue)
rrc_mesh._flush_to_peer(None, DEE, peer)
check("... nothing of the rooms sent to them, and their marks move on", len(rrc_mesh._send_queue) == before
      and peer["last_sent_id"] == rrc.since("main", 0)[-1]["id"])
say(CAT, "/unban pw -stump Dee", room="main")

print("FAILURES", FAIL)

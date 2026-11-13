# Room moderation, the rest of it (mods.py; the review of 12 Nov 2026):
# /deop and /demod, /mode shown and -t, /help mods, acting on oneself, a
# mod's /bans, two roles at once, a role through a nick change, two people
# with one nick, people no longer here, a kick from elsewhere, bad mute
# minutes, the entry limit, a damaged mods.json -- and the admin password:
# the lockout, a forgotten room not counted, plugins never seeing it, and
# nowhere in any room or private message afterwards.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import time
import config
SECRET = "Zebra-77-secret"
config.AUTH_ADMIN_PASSWORD = SECRET
import rrc, mods, guard, plugins, barkeep
barkeep._check_admin_pw_now = lambda pw: pw == SECRET       # (the harness's stub takes "pw": a password easy to spot instead)
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:400]))
    if not c:
        FAIL.append(n)


FILE = "mods_more.json"
try:
    import os
    os.remove(FILE)
except OSError:
    pass
mods.reset(FILE)

ADA, CAT, DEE = "a1" * 16, "c3" * 16, "d4" * 16
MAX1, MAX2 = "e1" * 16, "e2" * 16
BEN, GUEST = "p:ben", "web-guest-9"
rrc.create_room("bavard")
for cid, nick, room in ((ADA, "Ada", "bavard"), (CAT, "Cat", "bavard"), (DEE, "Dee", "bavard"), (BEN, "Ben", "bavard"),
                        (GUEST, "Gus", "bavard"), (MAX1, "Max", "bavard"), (MAX2, "Max", "bavard")):
    rrc.touch_user(cid, nick=nick, room=room)
for cid, nick in ((MAX1, "Max"), (MAX2, "Max")):          # two people, one nick (on two apps)
    rrc._users[cid]["nick"] = nick


def say(cid, text, room="bavard"):
    guard._buckets.clear()
    lines, _ = rrc.handle_input(cid, room, text)
    return " ".join(lines)


def fails(cid):
    f = guard._fails.get(guard._k(cid))
    return f[0] if f else 0


def admin(text, room="bavard"):
    """The admin's command, with the password first, from someone neutral."""
    parts = text.split(" ", 1)
    return say(GUEST, parts[0] + " " + SECRET + " " + parts[1], room)


# -- 1. /deop and /demod -------------------------------------------------------
admin("/op #bavard Ada")
check("(an op to start with)", mods.rank(ADA, "bavard") == "op")
say(ADA, "/mod #bavard Ben")
r = say(BEN, "/demod #bavard Ben")
check("a mod can't /demod (even themselves)", "✗" in r and mods.rank(BEN, "bavard") == "mod", r)
r = say(ADA, "/demod #bavard Ben")
check("an op /demods a mod of their room", mods.rank(BEN, "bavard") is None, r)
r = say(ADA, "/demod #bavard Ben")
check("... /demod someone who isn't: said so, nothing broken", "✗" not in r and mods.rank(BEN, "bavard") is None, r)
r = say(ADA, "/deop #bavard Ada")
check("an op can't /deop (only the admin): asked without the password, refused", mods.rank(ADA, "bavard") == "op", r)
r = admin("/deop #bavard Ada")
check("the admin /deops", mods.rank(ADA, "bavard") is None, r)
admin("/op #bavard Ada")
rrc._users.pop(ADA)
r = admin("/deop #bavard Ada")
check("/deop someone who's gone: by the nick they had", mods.rank(ADA, "bavard") is None and ADA not in str(mods._load()["roles"]), r)
admin("/op #bavard a1a1a1a1a1a1")       # (gone: nothing to resolve -- and nothing stored)
rrc.touch_user(ADA, nick="Ada", room="bavard")
admin("/op #bavard Ada")
rrc._users.pop(ADA)
r = admin("/deop #bavard a1a1a1")
check("... or by the start of their hash", mods.rank(ADA, "bavard") is None, r)
rrc.touch_user(ADA, nick="Ada", room="bavard")
admin("/op #bavard Ada")

# -- 2. /mode shown, -t, and not -stump ------------------------------------------
r = say(CAT, "/mode #bavard")
check("/mode #room with nothing after: shows it (anyone)", "#bavard" in r and "+t" not in r, r)
say(ADA, "/mode #bavard +t")
check("(+t on)", mods.topic_locked("bavard") and "+t" in say(CAT, "/mode #bavard"))
r = say(ADA, "/mode #bavard -t")
check("/mode -t: anyone sets the topic again", not mods.topic_locked("bavard") and "✗" not in say(CAT, "/topic open again"), r)
r = say(ADA, "/mode -stump +t")
check("/mode -stump: refused (+t is a room's)", "mode" in r and not any(mods.topic_locked(x) for x in ("main", "bavard")), r)

# -- 3. /help mods ------------------------------------------------------------------
lines, _ = rrc.handle_input(CAT, "bavard", "/help mods")
check("/help mods: one line per command", len(lines) == len(mods.COMMANDS) and all(c in " ".join(lines) for c in ("/op", "/kick", "/mode")), lines)

# -- 4. on oneself -------------------------------------------------------------------
r = say(ADA, "/mute #bavard Ada")
check("an op muting themselves: refused", "✗" not in r and not mods.muted(ADA, "bavard") and r, r)
r = say(ADA, "/ban #bavard Ada")
check("... banning themselves: refused", not mods.banned(ADA, "bavard"), r)

# -- 5. a mod's /bans ------------------------------------------------------------------
say(ADA, "/mod #bavard Ben")
say(ADA, "/ban #bavard Cat")
b = say(BEN, "/bans")
check("a mod lists the bans of their room", "Cat" in b, b)
say(ADA, "/unban #bavard Cat")
rrc.touch_user(CAT, room="bavard")

# -- 6. op in one room, mod everywhere ------------------------------------------------
admin("/op #bavard Dee")
admin("/op -stump Ada")
say(ADA, "/mod -stump Dee", room="main")
check("op in #bavard and mod everywhere: op there, mod elsewhere", mods.rank(DEE, "bavard") == "op" and mods.rank(DEE, "main") == "mod")
rrc.touch_user(CAT, room="main")
r = say(DEE, "/ban #main Cat", room="main")
check("... in #main: no ban (a mod there)", "✗" in r and not mods.banned(CAT, "main"), r)
r = say(DEE, "/mute #main Cat", room="main")
check("... but a mute (a mod's)", mods.muted(CAT, "main"), r)
say(DEE, "/unmute #main Cat", room="main")
rrc.touch_user(CAT, room="bavard")
r = say(DEE, "/ban #bavard Cat")
check("... in #bavard: a ban (an op's)", mods.banned(CAT, "bavard"), r)
say(DEE, "/unban #bavard Cat")
rrc.touch_user(CAT, room="bavard")
admin("/deop -stump Ada")
say(ADA, "/demod -stump Dee")

# -- 7. through a nick change -----------------------------------------------------------
r = say(ADA, "/nick Ada2")
check("an op who changes nick: still op (the role is the identity's)", mods.rank(ADA, "bavard") == "op" and "@Ada2" in say(CAT, "/names"), r)
say(ADA, "/nick Ada")

# -- 8. two people, one nick ---------------------------------------------------------------
r = say(ADA, "/mute #bavard Max")
check("two people called Max: \"more than one\", with their hashes, no one muted",
      "e1e1e1e1" in r and "e2e2e2e2" in r and not mods.muted(MAX1, "bavard") and not mods.muted(MAX2, "bavard"), r)
r = say(ADA, "/mute #bavard e1e1e1")
check("... the start of a hash picks one", mods.muted(MAX1, "bavard") and not mods.muted(MAX2, "bavard"), r)
say(ADA, "/unmute #bavard e1e1e1")

# -- 9. people no longer here --------------------------------------------------------------
say(ADA, "/ban #bavard Cat")
rrc._users.pop(CAT, None)
r = say(ADA, "/unban #bavard Cat")
check("/unban someone who's gone: by the nick they had", not mods.banned(CAT, "bavard"), r)
rrc.touch_user(CAT, nick="Cat", room="bavard")
say(ADA, "/mute #bavard Cat")
rrc._users.pop(CAT, None)
r = say(ADA, "/unmute #bavard c3c3c3")
check("/unmute someone who's gone: by the start of their hash", not mods.muted(CAT, "bavard"), r)
rrc.touch_user(CAT, nick="Cat", room="main")

# -- 10. a kick from a room they're not in ------------------------------------------------------
r = say(ADA, "/kick #bavard Cat")
check("/kick #bavard someone in #main: stays in #main, and can't come into #bavard for a minute",
      rrc._users[CAT]["room"] == "main" and say(CAT, "/join bavard", room="main").startswith("✗"), r)
for k in list(mods._kicked):
    mods._kicked[k] = time.time() - 1
rrc.touch_user(CAT, room="bavard")

# -- 11. bad mute minutes -------------------------------------------------------------------------
for m in ("0", "99999", "abc", "-5"):
    r = say(ADA, "/mute #bavard Cat " + m)
    check("/mute ... %s minutes: its usage, not muted" % m, not mods.muted(CAT, "bavard") and "mute" in r, r)

# -- 12. the entry limit -----------------------------------------------------------------------------
keep = mods.MAX_ENTRIES
mods.MAX_ENTRIES = mods._count() + 1
say(ADA, "/mute #bavard Cat")
r = say(ADA, "/mute #bavard Gus")
check("the entry limit: the one past it refused, said so", mods.muted(CAT, "bavard") and not mods.muted(GUEST, "bavard") and r, r)
mods.MAX_ENTRIES = keep
say(ADA, "/unmute #bavard Cat")

# -- 13. a damaged mods.json -----------------------------------------------------------------------------
for bad in ("{not json", "[1, 2, 3]", '{"roles": "x", "bans": 5, "t": "y"}', ""):
    with open(FILE, "w") as f:
        f.write(bad)
    mods.reset(FILE)
    try:
        ok = mods.rank(ADA, "bavard") is None and not mods.banned(CAT, "bavard") and not mods.topic_locked("bavard")
        say(CAT, "/roles")
    except Exception as e:
        ok = repr(e)
    check("a damaged mods.json (%r): starts with nothing, no crash" % bad[:12], ok is True, ok)
mods.reset(FILE)
admin("/op #bavard Ada")
check("... and works again after (saved, read back)", mods.rank(ADA, "bavard") == "op" and (mods.reset(FILE) or True)
      and mods.rank(ADA, "bavard") == "op")

# -- 14. the lockout -------------------------------------------------------------------------------------------
guard._fails.clear()
for i in range(guard.LOCK_AFTER):
    say(CAT, "/op wrong%d #bavard Cat" % i)
check("wrong admin passwords count", guard.locked(CAT) > 0, guard._fails)
r = say(CAT, "/op " + SECRET + " #bavard Cat")
check("... locked: even the right password is refused", mods.rank(CAT, "bavard") is None, r)
guard._fails.clear()

# -- 15. a forgotten room isn't a wrong password -------------------------------------------------------------
before = fails(CAT)
for t in ("/kick Gus", "/ban Gus", "/mute Gus 5", "/unban Gus", "/mod Gus", "/mode +t"):
    say(CAT, t)
check("a forgotten room (/kick Gus...) isn't counted as a wrong password", fails(CAT) == before and guard.locked(CAT) == 0,
      (before, fails(CAT)))

# -- 16. the password: plugins never see it, and it's nowhere afterwards ------------------------------------------
seen = []
real_before = plugins.before


def spy(client_id, room, nick, text, lang):
    seen.append(text)
    return real_before(client_id, room, nick, text, lang)


plugins.before = spy
try:
    admin("/op #bavard Dee")
    admin("/kick #bavard Gus being loud")
    admin("/mute -stump Gus 5")
    admin("/ban #bavard Gus")
    admin("/unban #bavard Gus")
    admin("/unmute -stump Gus")
    admin("/mode #bavard +t")
    admin("/mod -stump Ben")
    say(GUEST, "/bans " + SECRET)
    say(GUEST, "/op " + SECRET + "x #bavard Gus")         # a wrong one too
finally:
    plugins.before = real_before
check("plugins never see a command with the admin password in it", not any(SECRET in t for t in seen), seen)
everything = []
for room in list(rrc._rooms):
    everything += [m.get("body", "") + " " + str(m.get("nick", "")) for m in rrc.since(room, 0)]
for cid in (ADA, CAT, DEE, BEN, GUEST, MAX1, MAX2):
    everything += [d.get("body", "") for d in rrc.dms_since(cid, 0)]
everything += [str(rrc.topic(room, "en")) for room in list(rrc._rooms)]
check("the admin password: in no room, no private message, no topic", not any(SECRET in t for t in everything),
      [t for t in everything if SECRET in t][:3])
saved = open(FILE).read()
check("... nor in mods.json", SECRET not in saved)

print("FAILURES", FAIL)

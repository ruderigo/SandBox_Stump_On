# The five storage caps, flooded (pentest checklist I.2, ROADMAP's TODO):
# rooms and DMs 60 each, voice notes 10 per inbox and ~2 MB in all,
# billboard 150 notices. Each is pushed well past its cap; what's held
# must stay at the cap, the oldest going first, the newest kept, and
# nobody else's messages touched.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import rrc, billboard, gc
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:300]))
    if not c:
        FAIL.append(n)


# ── 1. A room: 500 lines ────────────────────────────────────────────
for i in range(500):
    rrc.post('main', 'flood', 'line %d' % i)
msgs = rrc.since('main', 0)
check("room: held at %d after 500 lines" % rrc.MAX_MESSAGES_PER_ROOM, len(msgs) == rrc.MAX_MESSAGES_PER_ROOM, len(msgs))
check("... the newest kept, the oldest gone",
      msgs[-1]['body'] == 'line 499' and msgs[0]['body'] == 'line %d' % (500 - rrc.MAX_MESSAGES_PER_ROOM))
check("... still takes new lines", rrc.post('main', 'after', 'still here') is not None
      and rrc.since('main', 0)[-1]['body'] == 'still here')

# ── 2. One inbox: 500 DMs ───────────────────────────────────────────
A, B = 'v' + 'a' * 20, 'v' + 'b' * 20
rrc.touch_user(A, 'alice')
rrc.touch_user(B, 'bob')
rrc.send_dm('carol', 'bob', 'for bob')
for i in range(500):
    ok, _ = rrc.send_dm('flood', 'alice', 'dm %d' % i)
box = rrc.dms_since(A, 0)
check("DMs: held at %d after 500" % rrc.MAX_DMS_PER_USER, len(box) == rrc.MAX_DMS_PER_USER, len(box))
check("... the newest kept, the oldest gone", box[-1]['body'] == 'dm 499' and box[0]['body'] == 'dm %d' % (500 - rrc.MAX_DMS_PER_USER))
check("... another inbox untouched", [m['body'] for m in rrc.dms_since(B, 0)] == ['for bob'])

# ── 3. Voice notes in one inbox: 30, with text between ──────────────
rrc._dms.clear()
for i in range(30):
    rrc.send_dm('flood', 'alice', 'note %d' % i, audio=(rrc.OPUS_OGG, bytes(1000)))
    rrc.send_dm('flood', 'alice', 'text %d' % i)
box = rrc.dms_since(A, 0)
voices = [m for m in box if 'audio' in m]
check("voice: %d per inbox after 30" % rrc.VOICE_PER_RECIPIENT, len(voices) == rrc.VOICE_PER_RECIPIENT, len(voices))
check("... the newest notes kept", [m['body'] for m in voices] == ['note %d' % i for i in range(30 - rrc.VOICE_PER_RECIPIENT, 30)])
check("... text DMs not dropped for voice", len([m for m in box if 'audio' not in m]) == 30)

# ── 4. Voice in all: 15 inboxes x 10 notes of 20 KB (3 MB) ──────────
rrc._dms.clear()
NOTE = 20000
users = []
for u in range(15):
    cid = 'v%020d' % u
    rrc.touch_user(cid, 'u%d' % u)
    users.append(cid)
for n in range(10):
    for u in range(15):
        rrc.send_dm('flood', 'u%d' % u, 'u%d n%d' % (u, n), audio=(rrc.OPUS_OGG, bytes(NOTE)))
    gc.collect()
total = sum(len(m['audio'][1]) for b in rrc._dms.values() for m in b if 'audio' in m)
check("voice in all: at most %d bytes after 3 MB" % rrc.VOICE_TOTAL_BYTES, total <= rrc.VOICE_TOTAL_BYTES, total)
check("... close to the cap, not emptied", total > rrc.VOICE_TOTAL_BYTES - NOTE, total)
held = sorted(m['id'] for b in rrc._dms.values() for m in b if 'audio' in m)
check("... the oldest went first: what's held is the newest", held == sorted(held)[-len(held):]
      and max(held) == rrc._next_id[0] - 1 and len(held) == rrc.VOICE_TOTAL_BYTES // NOTE)
check("... the last round reached every inbox",
      all(any(m['body'] == 'u%d n9' % u for m in rrc._dms.get(users[u], [])) for u in range(15)))
rrc._dms.clear()
gc.collect()

# ── 5. The billboard: 200 notices ───────────────────────────────────
for i in range(200):
    billboard._append_entry("Notice %d" % i, "", "x")
ents = billboard._read_entries()
check("billboard: held at %d after 200" % billboard.MAX_ENTRIES_STORED, len(ents) == billboard.MAX_ENTRIES_STORED, len(ents))
titles = [e[1] for e in ents]
check("... the newest kept, the oldest gone", "Notice 199" in titles and "Notice 0" not in titles
      and "Notice %d" % (200 - billboard.MAX_ENTRIES_STORED) in titles, titles[:3])

print('FAILURES:', FAIL)

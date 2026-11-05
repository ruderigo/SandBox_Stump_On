# Simple -- plain sentences for people on LXMF apps that don't know
# Stumps (Sideband, Columba, MeshChat...). The Stump talks to every app
# in compact lines a Stump app parses (`<rod> hi`, `✓ ~rod`,
# `[DM] <bob>: hi`): readable in FireFly, cryptic elsewhere. A person who
# writes "simple" gets sentences instead, from then on ("simple off" to
# go back). Opt-in per person: over LoRa the Stump can't tell FireFly
# from Sideband, and FireFly needs the compact lines. Uses plugin API 2:
# stump.mesh_out() rewords what the Stump sends.

try:
    import ujson as json
except ImportError:
    import json

VERSION = "1.0"
STUMP_API = 2

MAX_PEOPLE = 500       # people remembered (opted in, or told once)

_api = []
_on = {}        # LXMF address (hex) -> 1: wants sentences
_told = {}      # LXMF address (hex) -> 1: has been told about "simple"
_file = [None]
_dirty = [False]

WORDS_ON = ("simple", "simple on", "/simple", "/simple on", "!simple")
WORDS_OFF = ("simple off", "/simple off", "!simple off")


def setup(stump):
    _api.append(stump)
    _file[0] = stump.storage_file("simple.json")
    _load()
    stump.gate(_gate, priority=45)
    stump.mesh_out(_out, priority=50)
    stump.every(30, _save)


def _load():
    try:
        with open(_file[0]) as f:
            d = json.load(f)
        _on.update(d.get("on", {}))
        _told.update(d.get("told", {}))
    except Exception:
        pass


def _save():
    if not _dirty[0] or not _file[0]:
        return
    _dirty[0] = False
    try:
        with open(_file[0], "w") as f:
            json.dump({"on": _on, "told": _told}, f)
    except Exception as e:
        _api[0].log("could not save:", e)


def _mark(d, key):
    if key not in d:
        while len(d) >= MAX_PEOPLE:
            d.pop(next(iter(d)))
        d[key] = 1
        _dirty[0] = True


def _lang(h):
    try:
        import i18n
        return i18n.get_lang(h)
    except Exception:
        return "en"


def _t(key, h, **kw):
    return _api[0].t(key, _lang(h), **kw)


def _gate(ctx):
    """"simple" / "simple off" from someone on an LXMF app."""
    if not ctx.is_mesh:
        return None
    w = (ctx.text or "").strip().lower()
    h = ctx.client_id
    if w in WORDS_ON:
        _mark(_on, h)
        _mark(_told, h)
        return [_t("on", h)]
    if w in WORDS_OFF:
        if _on.pop(h, None) is not None:
            _dirty[0] = True
        return [_t("off", h)]
    return None


def _machine(text, title):
    """Something an app reads, not a person: left exactly as it is."""
    if title == "#profiles" or text[:1] == "{":
        return True
    return any(l.startswith(("AUTH-", "{")) for l in text.split("\n"))


def _out(dest_hex, text, title):
    if not text or _machine(text, title):
        return None
    if dest_hex in _on:
        return _reword(dest_hex, text), title
    if dest_hex not in _told and not _stump_app(dest_hex):
        # Once per person on a plain app: how to get sentences instead.
        # A Stump app (FireFly) reads the lines as they are: never told.
        _mark(_told, dest_hex)
        return text + "\n" + _t("tip", dest_hex), title
    return None


def _stump_app(h):
    try:
        import rrc
        return rrc.is_app(h)
    except Exception:
        return False


def _nick(s):
    return s.lstrip("~")


def _reword(h, text):
    out = []
    for line in text.split("\n"):
        out.append(_line(h, line))
    return "\n".join(l for l in out if l is not None)


def _line(h, line):
    t = lambda key, **kw: _t(key, h, **kw)
    if not line:
        return line
    c = line[0]
    if line.startswith("[DM] <") and ">: " in line:
        who, _, body = line[6:].partition(">: ")
        if body.startswith("♪ "):
            body = t("voice", secs=body[2:])
        return t("dm", who=who, text=body)
    if c == "<" and "> " in line:
        who, _, body = line[1:].partition("> ")
        return who + ": " + body
    if c == "✓" and line[1:2] == " ":
        return t("joined", who=_nick(line[2:]))
    if c == "✗" and line[1:2] == " ":
        return t("left", who=_nick(line[2:]))
    if c == "✎" and line[1:2] == " ":
        rest = line[2:]
        if rest.startswith("#") and " " in rest:
            room, _, topic = rest.partition(" ")
            return t("topic", room=room, topic=topic)
        if " → " in rest:
            a, _, b = rest.partition(" → ")
            return t("renamed", old=_nick(a), new=_nick(b))
    if c == "→" and line[1:3] == " #":
        return t("moved", room=line[2:])
    if c == "⊖" and line[1:2] == " ":
        return t("nobody", who=_nick(line[2:]))
    if c in "=?⊘⧗" and " — " in line:
        return line.split(" — ", 1)[1]          # the sentence, without the token
    return line

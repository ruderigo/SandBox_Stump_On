# Browsing NomadNet from the Stump: the Nomad Network nodes it hears, and
# their pages, fetched over Reticulum (a link to the node, a request for
# /page/<name>.mu) and shown as web pages to anyone on the Stump. Links,
# forms (fields, checkboxes, radio buttons) and link variables work the
# way NomadNet's browser sends them ("field_<name>", "var_<name>").
#
# Pages are micron, NomadNet's markup; render() turns it into HTML,
# following NomadNet's own parser (nomadnet/ui/textui/MicronParser.py):
# headings (>), dividers (-), comments (#), literal blocks (`=), tables
# (`t), formatting (`! `* `_ `F `B `f `b ``), alignment (`c `l `r `a),
# links `[label`url`fields] and fields `<flags|name`value>.
#
# Fetching takes seconds over LoRa, so a page first answers "fetching",
# refreshing itself until the node's answer is in.

import time

NODES_MAX = 60
CACHE_S = 60
FAIL_S = 15
_nodes = {}       # node hex -> {"name", "seen"}
_cache = {}       # token -> {"node", "path", "data", "t", "page" (bytes) or None, "state"}
_remotes = {}     # node hex -> Remote
_api = []


def setup(stump):
    _api.append(stump)
    stump.on_announce("nomadnetwork", ("node",), _heard)
    stump.page("nodes", _nodes_page, nav=lambda lang: stump.t("browse_card", lang),
               sub=lambda lang: stump.t("browse_card_sub", lang))
    stump.page("view", _view_page)


def _heard(dest_hex, app_data):
    try:
        name = app_data.decode("utf-8") if isinstance(app_data, (bytes, bytearray)) else ""
    except Exception:
        name = ""
    me = _own()
    if dest_hex == me:
        return
    if dest_hex not in _nodes and len(_nodes) >= NODES_MAX:
        old = min(_nodes, key=lambda k: _nodes[k]["seen"])
        del _nodes[old]
    _nodes[dest_hex] = {"name": name[:64] or dest_hex[:8], "seen": time.time()}


def _own():
    from . import install as nn
    return nn._door[0].hexhash if nn._door[0] is not None else None


# ── fetching ─────────────────────────────────────────────────────────

def _token(node, path, data):
    from urns.crypto.hashes import sha256
    key = node + "|" + path + "|" + repr(sorted((data or {}).items()))
    return sha256(key.encode())[:8].hex()


def fetch(node, path, data):
    """Starts (or reuses) a fetch; returns its token."""
    tok = _token(node, path, data)
    c = _cache.get(tok)
    now = time.time()
    if c and (c["state"] == "wait" or (c["state"] == "ok" and now - c["t"] < CACHE_S)
              or (c["state"] == "fail" and now - c["t"] < FAIL_S)):
        return tok
    if len(_cache) > 40:
        for k in sorted(_cache, key=lambda k: _cache[k]["t"])[:10]:
            del _cache[k]
    c = _cache[tok] = {"node": node, "path": path, "data": data, "t": now, "page": None, "state": "wait"}
    r = _remotes.get(node)
    if r is None or r.failed:
        r = _remotes[node] = _api[0].connect(node, "nomadnetwork", ("node",), identify=True)

    def done(resp):
        c["t"] = time.time()
        if isinstance(resp, (bytes, bytearray)):
            c["page"], c["state"] = bytes(resp), "ok"
        elif isinstance(resp, str):
            c["page"], c["state"] = resp.encode("utf-8"), "ok"
        else:
            c["state"] = "fail"

    r.request(path, data or None, done)
    return tok


# ── the Stump's pages ────────────────────────────────────────────────

def _esc(s):
    return _api[0].esc(s)


def _t(req, key, **kw):
    return _api[0].t(key, req.lang, **kw)


def _ago(req, ts):
    s = max(0, int(time.time() - ts))
    if s < 90:
        return _t(req, "browse_now")
    if s < 5400:
        return _t(req, "browse_min", n=s // 60)
    return _t(req, "browse_h", n=s // 3600)


def _nodes_page(req):
    out = ["<h1>" + _esc(_t(req, "browse_title")) + "</h1><p class='sub'>" + _esc(_t(req, "browse_intro")) + "</p>"]
    if not _nodes:
        out.append("<div class='panel'><p>" + _esc(_t(req, "browse_none")) + "</p></div>")
    else:
        out.append("<div class='panel'><ul class='files'>")
        for h, n in sorted(_nodes.items(), key=lambda kv: -kv[1]["seen"]):
            out.append("<li><a href='/p/nomadnet/view?n=" + h + "&amp;p=/page/index.mu'><b>" + _esc(n["name"])
                       + "</b></a> <small>&lt;" + h[:8] + "&gt; · " + _esc(_ago(req, n["seen"])) + "</small></li>")
        out.append("</ul></div>")
    try:
        import rrc
        people = rrc.reachable_nicks()
    except Exception:
        people = []
    out.append("<h2>" + _esc(_t(req, "people_title")) + "</h2>")
    if people:
        out.append("<p class='sub'>" + _esc(_t(req, "people_intro")) + "</p><div class='panel'><ul class='files'>"
                   + "".join("<li><b>" + _esc(n) + "</b> <small><code>/msg " + _esc(n) + " …</code></small></li>"
                             for n in people[:40]) + "</ul></div>")
    else:
        out.append("<p class='sub'>" + _esc(_t(req, "people_none")) + "</p>")
    out.append("<form method='GET' action='/p/nomadnet/view' class='post-form'><label>"
               + _esc(_t(req, "browse_by_address")) + "<br><input name='n' maxlength='32' size='34' "
               "pattern='[0-9a-fA-F]{32}' required></label><input type='hidden' name='p' value='/page/index.mu'> "
               "<button type='submit'>" + _esc(_t(req, "browse_open")) + "</button></form>")
    return "".join(out)


def _hexok(s):
    return isinstance(s, str) and len(s) == 32 and all(c in "0123456789abcdef" for c in s)


def _view_page(req):
    q = req.query
    tok = q.get("t")
    if tok:
        c = _cache.get(tok)
    else:
        node = (q.get("n") or "").strip().lower()
        path = q.get("p") or "/page/index.mu"
        if not _hexok(node) or not path.startswith("/"):
            return "<p>" + _esc(_t(req, "browse_bad")) + "</p>"
        data = {}
        for kv in (q.get("v") or "").split("|"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                data["var_" + k] = v
        if req.method == "POST":
            form = req.form() if callable(req.form) else req.form
            want = (q.get("f") or "").split("|")
            for k, v in form.items():
                if k.startswith("mu_") and ("*" in want or k[3:] in want):
                    data["field_" + k[3:]] = v
        tok = fetch(node, path, data)
        c = _cache.get(tok)
    if c is None:
        return "<p>" + _esc(_t(req, "browse_gone")) + " <a href='/p/nomadnet/nodes'>" + _esc(_t(req, "browse_title")) + "</a></p>"
    name = (_nodes.get(c["node"]) or {}).get("name") or c["node"][:8]
    head = ("<p class='sub'><a href='/p/nomadnet/nodes'>" + _esc(_t(req, "browse_title")) + "</a> › <b>"
            + _esc(name) + "</b> <small>" + _esc(c["path"]) + "</small></p>")
    if c["state"] == "wait":
        return (head + "<meta http-equiv='refresh' content='2;url=/p/nomadnet/view?t=" + tok + "'>"
                "<div class='panel'><p>" + _esc(_t(req, "browse_fetching", name=name)) + "</p></div>")
    if c["state"] == "fail":
        return (head + "<div class='panel'><p>" + _esc(_t(req, "browse_failed")) + "</p><p><a href='/p/nomadnet/view?n="
                + c["node"] + "&amp;p=" + _esc(c["path"]) + "'>" + _esc(_t(req, "browse_retry")) + "</a></p></div>")
    try:
        text = c["page"].decode("utf-8")
    except Exception:
        text = c["page"].decode("utf-8", "replace")
    return head + "<div class='panel mu-page'>" + render(text, c["node"], c["path"]) + "</div>" + _STYLE


_STYLE = ("<style>.mu-page{font-family:monospace;white-space:pre-wrap;overflow-x:auto}"
          ".mu-page .mu{min-height:1.2em}.mu-page .h1{font-size:1.25em;font-weight:bold}"
          ".mu-page .h2{font-size:1.1em;font-weight:bold}.mu-page .h3{font-weight:bold}"
          ".mu-page input,.mu-page textarea{font:inherit}.mu-page table{border-collapse:collapse}"
          ".mu-page td{padding:0 .6em}.mu-page hr{border:0;border-top:1px solid var(--border)}</style>")


# ── micron -> HTML ───────────────────────────────────────────────────

def _h(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("'", "&#39;").replace('"', "&quot;"))


def _color(c):
    if len(c) == 3 and all(x in "0123456789abcdefABCDEF" for x in c):
        return "#" + c
    if len(c) == 6 and all(x in "0123456789abcdefABCDEF" for x in c):
        return "#" + c
    return None


def _url(url, node, fields):
    """(href or None, is a form submit, field list) for a micron link."""
    vars_, fl = [], []
    for f in (fields or "").split("|"):
        if not f:
            continue
        if "=" in f:
            vars_.append(f)
        else:
            fl.append(f)
    target = None
    if url.startswith("#"):
        return url, False, []
    if url.startswith("rrc://"):
        return "/p/nomadnet/hubs?add=" + _h(url[6:]), False, []
    if url.startswith(":"):
        target = (node, url[1:])
    elif ":" in url:
        h, _, p = url.partition(":")
        if "@" in h:
            h = h.split("@", 1)[1]
        if _hexok(h.lower()):
            target = (h.lower(), p or "/page/index.mu")
    elif _hexok(url.lower()):
        target = (url.lower(), "/page/index.mu")
    if target is None or not target[1].startswith("/page/"):
        return None, False, []
    href = "/p/nomadnet/view?n=" + target[0] + "&amp;p=" + _h(target[1])
    if vars_:
        href += "&amp;v=" + _h("|".join(vars_))
    if fl:
        href += "&amp;f=" + _h("|".join(fl))
    return href, bool(fl), fl


class _State:
    def __init__(self):
        self.bold = self.italic = self.underline = False
        self.fg = self.bg = None
        self.align = None
        self.depth = 0
        self.literal = False

    def style(self):
        s = []
        if self.bold:
            s.append("font-weight:bold")
        if self.italic:
            s.append("font-style:italic")
        if self.underline:
            s.append("text-decoration:underline")
        if self.fg:
            s.append("color:" + self.fg)
        if self.bg:
            s.append("background:" + self.bg)
        return ";".join(s)


def _inline(line, st, node, out, pre_escape=False):
    """One line of micron text (no line-level command) as HTML into out."""
    buf = []
    open_style = [None]

    def flush():
        if buf:
            text = _h("".join(buf))
            stl = st.style()
            out.append("<span style='" + stl + "'>" + text + "</span>" if stl else text)
            del buf[:]

    i, n = 0, len(line)
    escape = pre_escape
    while i < n:
        c = line[i]
        if escape:
            buf.append(c)
            escape = False
            i += 1
            continue
        if c == "\\":
            escape = True
            i += 1
            continue
        if c != "`" or i + 1 >= n:
            buf.append(c)
            i += 1
            continue
        flush()
        k = line[i + 1]
        i += 2
        if k == "!":
            st.bold = not st.bold
        elif k == "*":
            st.italic = not st.italic
        elif k == "_":
            st.underline = not st.underline
        elif k in "FB":
            if line[i:i + 1] == "T" and i + 7 <= n:
                col, i = _color(line[i + 1:i + 7]), i + 7
            else:
                col, i = _color(line[i:i + 3]), i + 3
            if k == "F":
                st.fg = col
            else:
                st.bg = col
        elif k == "f":
            st.fg = None
        elif k == "b":
            st.bg = None
        elif k == "`":
            st.bold = st.italic = st.underline = False
            st.fg = st.bg = None
            st.align = None
        elif k in "clr":
            st.align = {"c": "center", "l": "left", "r": "right"}[k]
        elif k == "a":
            st.align = None
        elif k == ":":
            j = i
            while j < n and (line[j].isalnum() or line[j] in "_-"):
                j += 1
            if j > i:
                out.append("<a id='" + _h(line[i:j]) + "'></a>")
            i = j
        elif k == "<":
            bt = line.find("`", i)
            end = line.find(">", bt + 1) if bt >= 0 else -1
            if bt < 0 or end < 0:
                continue
            content, data = line[i:bt], line[bt + 1:end]
            i = end + 1
            ftype, width, rows, masked, value, checked = "field", 24, 1, False, "", False
            name = content
            if "|" in content:
                comps = content.split("|")
                flags, name = comps[0], comps[1]
                if "^" in flags:
                    ftype, flags = "radio", flags.replace("^", "")
                elif "?" in flags:
                    ftype, flags = "checkbox", flags.replace("?", "")
                elif "!" in flags:
                    masked, flags = True, flags.replace("!", "")
                if flags:
                    w, _, r = flags.partition("x")
                    try:
                        width = min(int(w), 256)
                    except ValueError:
                        pass
                    try:
                        rows = max(1, min(int(r), 32)) if r else 1
                    except ValueError:
                        pass
                value = comps[2] if len(comps) > 2 else ""
                checked = len(comps) > 3 and comps[3] == "*"
            fname = "mu_" + _h(name)
            if ftype in ("checkbox", "radio"):
                out.append("<label><input type='" + ftype + "' name='" + fname + "' value='" + _h(value or data) + "'"
                           + (" checked" if checked else "") + "> " + _h(data) + "</label>")
            elif rows > 1:
                out.append("<textarea name='" + fname + "' cols='" + str(width) + "' rows='" + str(rows) + "'>"
                           + _h(data) + "</textarea>")
            else:
                out.append("<input type='" + ("password" if masked else "text") + "' name='" + fname + "' size='"
                           + str(min(width, 60)) + "' value='" + _h(data) + "'>")
        elif k == "[":
            end = line.find("]", i)
            if end < 0:
                continue
            comps = line[i:end].split("`")
            i = end + 1
            if len(comps) == 1:
                label, url, fields = "", comps[0], ""
            elif len(comps) == 2:
                label, url, fields = comps[0], comps[1], ""
            elif len(comps) == 3:
                label, url, fields = comps
            else:
                continue
            if not url:
                continue
            label = label or url
            href, submit, _ = _url(url, node, fields)
            stl = st.style()
            sty = " style='" + stl + "'" if stl else ""
            if href is None:
                out.append("<span" + sty + ">" + _h(label) + "</span>")
            elif submit:
                out.append("<button type='submit' class='plain' formaction='" + href + "'" + sty + ">"
                           + _h(label) + "</button>")
            else:
                out.append("<a href='" + href + "'" + sty + ">" + _h(label) + "</a>")
        # anything else after ` (partials, images...) is skipped
    flush()


def render(text, node, path=""):
    st = _State()
    out = ["<form method='POST' action='/p/nomadnet/view?n=" + node + "&amp;p=" + _h(path) + "'>"]
    table = None
    for raw in text.replace("\r", "").split("\n"):
        line = raw
        if line == "`=":
            st.literal = not st.literal
            continue
        if st.literal:
            out.append("<div class='mu'>" + _h(line) + "</div>")
            continue
        if line.startswith("`t"):
            if table is None:
                table = []
            else:
                out.append("<table>")
                for row in table:
                    out.append("<tr>")
                    for cell in row.split("|"):
                        cell_out = []
                        _inline(cell, st, node, cell_out)
                        out.append("<td>" + "".join(cell_out) + "</td>")
                    out.append("</tr>")
                out.append("</table>")
                table = None
            continue
        if table is not None:
            table.append(line)
            continue
        if (line.startswith("`+") or line.startswith("`-")) and line[2:3] == ">":
            line = line[2:]
        pre = False
        if line.startswith(">") and "`<" in line:
            line = line.lstrip(">")
        if line.startswith("\\"):
            line, pre = line[1:], True
        elif line.startswith("#"):
            continue
        elif line.startswith("`{") or line.startswith("`("):
            continue
        elif line.startswith("<"):
            st.depth = 0
            line = line[1:]
        if not pre and line.startswith(">"):
            d = len(line) - len(line.lstrip(">"))
            st.depth = d
            body = line[d:]
            if body:
                cell = []
                _inline(body, st, node, cell)
                out.append("<div class='mu h" + str(min(d, 3)) + "'>" + "".join(cell) + "</div>")
            continue
        if not pre and line.startswith("-") and len(line) <= 2:
            out.append("<hr>")
            continue
        cell = []
        _inline(line, st, node, cell, pre)
        indent = " style='" + ("text-align:" + st.align + ";" if st.align else "") \
                 + ("padding-left:" + str(st.depth) + "em" if st.depth else "") + "'"
        out.append("<div class='mu'" + (indent if (st.align or st.depth) else "") + ">" + "".join(cell) + "</div>")
    out.append("</form>")
    return "".join(out)

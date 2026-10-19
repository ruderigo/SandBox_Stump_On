# The web server's connection hygiene: nobody can hold the Stump by
# keeping connections open.
#
# One loop serves everyone (uasyncio), so a connection that waits doesn't
# cost CPU -- but each one holds a socket, and the CAM has only about ten.
# A few phones opening connections and sending a byte a minute (the
# "slowloris" attack) used to lock every visitor out, and nothing ever
# timed them out. So:
#
#   admission   at most MAX connections at once (the CAM's sockets), and
#               PER_CLIENT from one address; beyond that a quick "503,
#               retry in 2 s" instead of a socket held.
#   headers     the request line and headers must arrive within HEAD_S
#               (HEAD_BUSY_S once the Stump is three quarters full), each
#               line at most LINE_MAX bytes -- a line that never ends
#               can't fill the CAM's memory either.
#   body        a read where nothing arrives for IDLE_S ends the body
#               (the callers already treat that as "the client went away":
#               a half upload is discarded), and past RATE_GRACE_S a body
#               must average MIN_BPS.
#   response    a write the client doesn't take within IDLE_S drops the
#               connection (a download nobody reads).
#
# Each can be changed in config.py (CONN_MAX, CONN_PER_CLIENT, CONN_HEAD_S,
# CONN_HEAD_BUSY_S, CONN_IDLE_S, CONN_MIN_BPS, CONN_RATE_GRACE_S).
# Counts of what was dropped: stats().

import time

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

LINE_MAX = 4096           # a request or header line, bytes
HEAD_MAX = 16384          # the request line and all headers together

_DEFAULTS = {"CONN_HEAD_S": 10, "CONN_HEAD_BUSY_S": 3, "CONN_IDLE_S": 15,
             "CONN_MIN_BPS": 512, "CONN_RATE_GRACE_S": 30}
_CAM = {"CONN_MAX": 10, "CONN_PER_CLIENT": 6}
_COMPUTER = {"CONN_MAX": 128, "CONN_PER_CLIENT": 16}

_open = {}                # address -> connections open now
_total = [0]
_stats = {"served": 0, "refused_busy": 0, "refused_client": 0, "dropped_head": 0,
          "dropped_long": 0, "dropped_idle": 0, "dropped_slow": 0, "dropped_write": 0}
_said = [0]               # when the log last summed up drops (ms)


class Dropped(Exception):
    """This connection is being let go (why: head, long, write)."""


def _computer():
    try:
        import stump_host  # noqa: F401
        return True
    except ImportError:
        return False


def setting(key):
    try:
        import config
        v = getattr(config, key, None)
    except ImportError:
        v = None
    if v is None:
        v = _DEFAULTS.get(key)
        if v is None:
            v = (_COMPUTER if _computer() else _CAM)[key]
    return v


def _now():
    try:
        return time.ticks_ms()
    except AttributeError:
        return int(time.time() * 1000)


def _since(t0):
    try:
        return time.ticks_diff(time.ticks_ms(), t0)
    except AttributeError:
        return _now() - t0


def _local(ip):
    return ip in ("127.0.0.1", "::1", "localhost")


def admit(ip):
    """A new connection from ip: None (taken in, counted), or why not:
    "busy" (the Stump is full) or "client" (that address has enough)."""
    if _total[0] >= setting("CONN_MAX"):
        _stats["refused_busy"] += 1
        _say()
        return "busy"
    if not _local(ip) and _open.get(ip, 0) >= setting("CONN_PER_CLIENT"):
        _stats["refused_client"] += 1
        _say()
        return "client"
    _open[ip] = _open.get(ip, 0) + 1
    _total[0] += 1
    _stats["served"] += 1
    return None


def leave(ip):
    n = _open.get(ip, 0) - 1
    if n > 0:
        _open[ip] = n
    else:
        _open.pop(ip, None)
    if _total[0] > 0:
        _total[0] -= 1


def head_timeout():
    """Seconds the request line and headers may take: shorter once the
    Stump is three quarters full, so held connections go first."""
    if _total[0] * 4 >= setting("CONN_MAX") * 3:
        return setting("CONN_HEAD_BUSY_S")
    return setting("CONN_HEAD_S")


def open_now():
    return _total[0]


def stats():
    out = dict(_stats)
    out["open"] = _total[0]
    return out


def note(why):
    """A connection let go: counted (and summed up in the log now and
    then, never once per connection -- an attack would flood it)."""
    key = "dropped_" + str(why)
    _stats[key] = _stats.get(key, 0) + 1
    _say()


def _say():
    if _said[0] and _since(_said[0]) < 60000:
        return
    _said[0] = _now() or 1
    dropped = sum(v for k, v in _stats.items() if k.startswith("dropped_"))
    refused = _stats["refused_busy"] + _stats["refused_client"]
    if dropped or refused:
        print("[web] connections: %d open, %d refused (full or too many from one address), "
              "%d dropped (too slow or silent) so far" % (_total[0], refused, dropped))


async def refuse(writer, why):
    """The quick answer to a connection not taken in."""
    try:
        await asyncio.wait_for(writer.awrite(
            "HTTP/1.1 503 Service Unavailable\r\nRetry-After: 2\r\nContent-Type: text/plain\r\n"
            "Content-Length: 5\r\nConnection: close\r\n\r\nbusy\n"), 2)
    except Exception:
        pass
    try:
        await asyncio.wait_for(writer.aclose(), 2)
    except Exception:
        pass


class Reader:
    """The connection's reader, with the deadlines above: readline() for
    the request line and headers, read() for the body. A body read that
    times out answers b"" (end of data), as a client gone away would."""

    def __init__(self, raw, head_s=None):
        self._raw = raw
        self._buf = b""
        self._head = True
        self._head_bytes = 0
        self._deadline = _now()
        self._head_ms = int((head_s if head_s is not None else head_timeout()) * 1000)
        self._body_t0 = None
        self._body_n = 0
        self.why = None

    def start_body(self):
        """The headers are in: from here, read() and the body's limits."""
        self._head = False
        self._body_t0 = _now()

    async def _get(self, n, timeout_s):
        if timeout_s <= 0:
            return None
        try:
            data = await asyncio.wait_for(self._raw.read(n), timeout_s)
        except asyncio.TimeoutError:
            return None
        return data or b""

    async def readline(self):
        while b"\n" not in self._buf:
            if len(self._buf) >= LINE_MAX or self._head_bytes + len(self._buf) >= HEAD_MAX:
                raise Dropped("long")
            left = (self._head_ms - _since(self._deadline)) / 1000
            data = await self._get(512, left)
            if data is None:
                raise Dropped("head")
            if not data:
                line, self._buf = self._buf, b""
                return line
            self._buf += data
        i = self._buf.index(b"\n") + 1
        line, self._buf = self._buf[:i], self._buf[i:]
        self._head_bytes += len(line)
        return line

    async def read(self, n=-1):
        if self._buf:
            if n is None or n < 0 or n >= len(self._buf):
                out, self._buf = self._buf, b""
            else:
                out, self._buf = self._buf[:n], self._buf[n:]
            self._body_n += len(out)
            return out
        if self.why:
            return b""
        if self._body_t0 is None:
            self.start_body()
        data = await self._get(n if n and n > 0 else 2048, setting("CONN_IDLE_S"))
        if data is None:
            self.why = "idle"
            note("idle")
            return b""
        self._body_n += len(data)
        t = _since(self._body_t0)
        if t > setting("CONN_RATE_GRACE_S") * 1000 and self._body_n * 1000 < setting("CONN_MIN_BPS") * t:
            self.why = "slow"
            note("slow")
            return b""
        return data


class Writer:
    """The connection's writer: a write the client doesn't take within
    CONN_IDLE_S lets the connection go (Dropped("write")). Attributes set
    on it (the page's cookie, no-store) stay on it."""

    def __init__(self, raw):
        self._raw = raw

    async def awrite(self, data, *a):
        try:
            await asyncio.wait_for(self._raw.awrite(data, *a), setting("CONN_IDLE_S"))
        except asyncio.TimeoutError:
            raise Dropped("write")

    async def aclose(self):
        try:
            await asyncio.wait_for(self._raw.aclose(), 2)
        except Exception:
            pass

    def get_extra_info(self, name):
        return self._raw.get_extra_info(name)

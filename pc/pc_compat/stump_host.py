# Stump on a computer (docs/PC.md): what makes the board's firmware run on
# Windows, macOS or Linux, unchanged.
#
#   - The Stump folder plays the board's flash: the firmware, the plugins,
#     config.py and everything the node saves live there, and a path the
#     firmware opens as "/radio.json" or "/sd/shared/x" is that folder's
#     radio.json or sd/shared/x. Only calls made BY the firmware are
#     redirected (Python's own libraries keep the real filesystem).
#   - Files are UTF-8 with no line-ending translation, as on the board
#     (Windows would otherwise write cp1252 and \r\n).
#   - os.statvfs (missing on Windows) reports a storage quota, so the
#     "card" never fills the computer's own disk: PC_STORAGE_MB.
#   - Small MicroPython extras: time.ticks_*, gc.mem_free, socket.readinto.
#
# Settings, in config.py (all optional):
#   PC_HOTSPOT_IP = "auto"   # the address visitors reach this computer on
#   PC_HTTP_PORT  = 80       # 8080 if 80 is taken
#   PC_STORAGE_MB = 2048     # room for shared files and tools
#   PC_HOTSPOT_NAME = ""     # the Wi-Fi name visitors join, for the About page

import builtins
import os
import sys
import time

ROOT = None
IS_PC = True


def setting(name, default):
    try:
        import config
        return getattr(config, name, default)
    except Exception:
        return default


# ── the hotspot address ─────────────────────────────────────────────

# Addresses the operating systems give their own hotspot.
WELL_KNOWN = ("192.168.137.1",   # Windows Mobile Hotspot
              "192.168.2.1",     # macOS Internet Sharing
              "10.42.0.1")       # Linux NetworkManager hotspot


def local_ips():
    import socket
    ips = []
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    try:
        # The address of the default route (sends nothing).
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        if ip not in ips:
            ips.append(ip)
    except Exception:
        pass
    return [ip for ip in ips if not ip.startswith("127.")]


def hotspot_ip():
    """The address visitors reach this computer on: PC_HOTSPOT_IP, else the
    hotspot's well-known address if this computer has it, else its own
    address on its network."""
    want = setting("PC_HOTSPOT_IP", "auto")
    if want and want != "auto":
        return want
    ips = local_ips()
    for ip in WELL_KNOWN:
        if ip in ips:
            return ip
    for ip in ips:
        if ip.startswith(("192.168.", "10.", "172.")):
            return ip
    return ips[0] if ips else "127.0.0.1"


# ── the Stump folder as the board's filesystem ──────────────────────

def _from_firmware():
    """True when the call comes from code in the Stump folder."""
    f = sys._getframe(2)
    name = f.f_code.co_filename
    return name.startswith(ROOT)


def _map(path):
    if isinstance(path, str) and path.startswith("/") and not path.startswith(ROOT):
        return ROOT + path
    return path


def _wrap1(fn):
    def w(path, *a, **k):
        if _from_firmware():
            path = _map(path)
        return fn(path, *a, **k)
    return w


def _wrap2(fn):
    def w(a, b, *rest, **k):
        if _from_firmware():
            a, b = _map(a), _map(b)
        return fn(a, b, *rest, **k)
    return w


def _dir_size(path):
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for n in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, n))
            except OSError:
                pass
    return total


def _statvfs(path):
    """The board's statvfs() tuple: a quota (PC_STORAGE_MB) for the
    folder, never more than the disk really has free."""
    import shutil
    real = _map(path) if isinstance(path, str) else path
    quota = int(setting("PC_STORAGE_MB", 2048)) * 1024 * 1024
    used = _dir_size(real)
    try:
        disk_free = shutil.disk_usage(real).free
    except OSError:
        disk_free = quota
    free = max(0, min(quota - used, disk_free))
    total = used + free
    return (1, 1, total, free, free, 0, 0, 0, 0, 255)


def install(root):
    """Sets everything up for the firmware in `root` (the Stump folder)."""
    global ROOT
    ROOT = os.path.abspath(root).replace("\\", "/")
    if os.sep == "\\":
        # Frames report native paths on Windows.
        global _from_firmware

        def _from_firmware():
            f = sys._getframe(2)
            return f.f_code.co_filename.replace("\\", "/").startswith(ROOT)

    real_open = builtins.open

    def stump_open(file, mode="r", *a, **k):
        if _from_firmware():
            file = _map(file)
            if "b" not in mode and not a:
                k.setdefault("encoding", "utf-8")
                k.setdefault("newline", "")
        return real_open(file, mode, *a, **k)
    builtins.open = stump_open

    os.stat = _wrap1(os.stat)
    os.listdir = _wrap1_listdir(os.listdir)
    os.mkdir = _wrap1(os.mkdir)
    os.remove = _wrap1(os.remove)
    os.rmdir = _wrap1(os.rmdir)
    os.rename = _wrap2(os.replace)          # the board's rename replaces, Windows' doesn't
    os.statvfs = _statvfs
    os.mount = lambda *a, **k: None         # the "card" is the sd/ folder
    os.umount = lambda *a, **k: None
    os.sync = getattr(os, "sync", lambda: None)

    for name, fn in (("ticks_ms", lambda: int(time.monotonic() * 1000)),
                     ("ticks_us", lambda: int(time.monotonic() * 1000000)),
                     ("ticks_diff", lambda a, b: a - b),
                     ("ticks_add", lambda a, b: a + b),
                     ("sleep_ms", lambda ms: time.sleep(ms / 1000)),
                     ("sleep_us", lambda us: time.sleep(us / 1000000))):
        if not hasattr(time, name):
            setattr(time, name, fn)

    import gc
    if not hasattr(gc, "mem_free"):
        gc.mem_free = lambda: 1 << 30       # "plenty": the big tables (urns/const.py)
        gc.mem_alloc = lambda: 0

    import socket
    if not hasattr(socket.socket, "readinto"):
        def readinto(self, buf, n=None):
            try:
                return self.recv_into(buf, n or len(buf))
            except BlockingIOError:
                raise OSError(11, "EAGAIN")      # the board's errno, whatever the OS
        socket.socket.readinto = readinto

    for d in ("sd",):
        try:
            os.makedirs(os.path.join(ROOT, d), exist_ok=True)
        except OSError:
            pass


def _wrap1_listdir(fn):
    def w(path=".", *a, **k):
        if _from_firmware():
            path = _map(path)
        return fn(path, *a, **k)
    return w

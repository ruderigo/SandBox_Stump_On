# /names in #lora-mesh, the same on every Stump (1.0.0-beta.64): a chain
# of two (the first with a Heltec, the second with none) and a Stump on
# its own with a Heltec, the two Heltecs over a simulated air -- the kit
# test bench (Bob's Glitch: the S3-CAM with its radio and a WROVER with
# none; eKoms' and BGARE's Stumps on their own, each with a Heltec: three
# radios on one air). Each has someone in #lora-mesh; /names on each lists
# everyone, wherever they are. Then one restarts: within a couple of
# minutes it lists everyone again, and everyone lists it (it waited up to
# 10 minutes for the next names list before).
# Linux only. Run: python3 tests/pc/pc_lora_names_test.py
import json, os, pty, subprocess, sys, tempfile, threading, time, tty, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import builtins
builtins.input = lambda *a: ""
import provisioner as P

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD
A, B, K, G = (("127.0.11.1", 8110, "Parentn"), ("127.0.11.2", 8111, "Childn"), ("127.0.11.3", 8112, "Kitn"),
              ("127.0.11.4", 8113, "Gearn"))
SECRET = "lora-names-secret"
FAIL = []


def annotate(text):
    if os.environ.get("GITHUB_ACTIONS"):
        print("::error::" + text.replace("%", "%25").replace("\r", "").replace("\n", "%0A"))


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + repr(info)[:600]))
    if not cond:
        FAIL.append(name)
        annotate(name + ": " + repr(info)[:1500])


if not sys.platform.startswith("linux"):
    print("SKIP (needs two loopback addresses: Linux)")
    sys.exit(0)


def kiss(cmd, payload):
    body = bytearray()
    for b in payload:
        body += bytes([FESC, TFEND]) if b == FEND else bytes([FESC, TFESC]) if b == FESC else bytes([b])
    return bytes([FEND, cmd]) + bytes(body) + bytes([FEND])


class Heltec:
    """A simulated RNode on a pseudo-terminal: answers the handshake, and
    hands every data frame it's given to the other one (the air)."""

    def __init__(self):
        self.master, slave = pty.openpty()
        tty.setraw(slave)
        self.port = os.ttyname(slave)
        self.slave = slave
        self.others = []
        self.buf, self.cur, self.esc, self.inside = bytearray(), None, False, False
        self.sent = 0

    def feed(self, data):
        for b in data:
            if b == FEND:
                if self.inside and self.cur:
                    self.frame(self.cur[0], bytes(self.cur[1:]))
                self.cur, self.inside = bytearray(), True
            elif self.inside:
                if b == FESC:
                    self.esc = True
                else:
                    if self.esc:
                        b = FEND if b == TFEND else FESC if b == TFESC else b
                        self.esc = False
                    self.cur.append(b)

    def frame(self, cmd, payload):
        if cmd == 0x08 and payload[:1] == b"\x73":
            os.write(self.master, kiss(0x08, b"\x46") + kiss(0x50, b"\x01\x4e") + kiss(0x48, b"\x80"))
        elif cmd == 0x00 and payload and self.others:
            self.sent += 1
            for o in self.others:                                   # over the air, to every other radio
                os.write(o.master, kiss(0x00, payload))


air = [Heltec(), Heltec(), Heltec()]
for h in air:
    h.others = [o for o in air if o is not h]
stop = threading.Event()


def run_air():
    for h in air:
        os.set_blocking(h.master, False)
    while not stop.is_set():
        for h in air:
            try:
                h.feed(os.read(h.master, 4096))
            except (BlockingIOError, OSError):
                pass
        time.sleep(0.01)

threading.Thread(target=run_air, daemon=True).start()

work = tempfile.mkdtemp(prefix="stump-names-")
nodes = {}


def start(who, heltec, parent=None, chain=True):
    ip, port, name = who
    folder = os.path.join(work, name)
    if os.path.isdir(folder):                    # a restart: the same Stump, same identity
        nodes[name] = subprocess.Popen([sys.executable, "-u", "stump_pc.py"], cwd=folder,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return
    os.makedirs(folder)
    P._pc_copy_firmware(P.STUMP_APP_DIR, folder)
    cfg = open(os.path.join(ROOT, "tests", "config.py"), encoding="utf-8").read()
    prof = {"pc_hotspot_name": name, "pc_heltec": "usb" if heltec else "none"}
    if heltec:
        prof["pc_heltec_port"] = heltec.port
    if chain:
        prof["chain"] = {"enabled": True, "parent_ip": parent} if parent else {"enabled": True}
    cfg += P._pc_config_block(prof)
    cfg += "\nNODE_NAME = %r\nPC_HTTP_PORT = %d\nPC_HOTSPOT_IP = %r\n" % (name, port, ip)
    if chain:
        cfg += "CHAIN_ENABLED = True\nCHAIN_UPLINK_SSID = %r\nCHAIN_SECRET = %r\n" % ("(home)" if parent else "", SECRET)
    else:
        cfg += "CHAIN_ENABLED = False\n"
    open(os.path.join(folder, "config.py"), "w", encoding="utf-8").write(cfg)
    nodes[name] = subprocess.Popen([sys.executable, "-u", "stump_pc.py"], cwd=folder,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def get(who, path, data=None):
    ip, port, _ = who
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request("http://%s:%d%s" % (ip, port, path), data=data), timeout=10) as r:
        return r.read().decode("utf-8", "replace")


def lora(who):
    return json.loads(get(who, "/rrc/poll?room=lora-mesh&since=0"))["messages"]


def wait(cond, secs):
    t0 = time.time()
    while time.time() - t0 < secs:
        try:
            if cond():
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def up(who):
    try:
        get(who, "/node.json")
        return True
    except Exception:
        return False

radio_on = lambda who: json.loads(get(who, "/hw.json"))["state"] == "online"
start(A, air[0])
check("the chain's first Stump starts, its radio online", wait(lambda: up(A) and radio_on(A), 60))
start(B, None, parent=A[0])
check("the chain's second Stump starts (no radio)", wait(lambda: up(B), 60))
start(K, air[1], chain=False)
check("a Stump on its own starts, its radio online", wait(lambda: up(K) and radio_on(K), 60))
start(G, air[2], chain=False)
check("another Stump on its own starts, its radio online", wait(lambda: up(G) and radio_on(G), 60))
ALL = (A, B, K, G)
logs = {}
if all(up(x) for x in ALL):
    names = lambda who: " ".join(json.loads(get(who, "/rrc/send", b"/names"))["replies"])
    for who in ALL:
        get(who, "/rrc/send", b"/join lora-mesh")
    for who in ALL:
        get(who, "/rrc/send", ("hello from " + who[2]).encode())
    for who in ALL:
        for other in ALL:
            if other is not who:
                got = wait(lambda: any(m["body"] == "hello from " + other[2] for m in lora(who)), 150)
                check("#lora-mesh on %s: %s's line" % (who[2], other[2]), got, [m["nick"] + ": " + m["body"] for m in lora(who)][-6:])
    def everyone(who, secs):
        others = [o[2] for o in ALL if o is not who]
        ok = wait(lambda: all("@" + o in names(who) for o in others), secs)
        check("/names in #lora-mesh on %s: the people on %s too" % (who[2], ", ".join(others)), ok, names(who))
    for who in ALL:
        everyone(who, 180)

    # The chain's members (the no-radio one is a computer here: the macOS
    # Stump on Bob's Glitch): the LoRa Stumps' people in #lora-mesh, never in
    # #wifi-mesh -- the one without a radio reaches them only through the
    # first, over the chain link (1.0.0-beta.68).
    def names_in(who, room):
        get(who, "/rrc/send", ("/join " + room).encode())
        out = names(who)
        get(who, "/rrc/send", b"/join lora-mesh")
        return out
    def right_rooms(when):
        for who in (A, B):
            w = names_in(who, "wifi-mesh")
            check("#wifi-mesh on %s (%s): only the chain's, not the LoRa Stumps' people" % (who[2], when),
                  "@" + K[2] not in w and "@" + G[2] not in w, w)
    right_rooms("before a restart")
    # One of them restarts (an update, a power cut): listed again everywhere, and lists everyone, soon.
    nodes[K[2]].terminate()
    logs[K[2]] = nodes[K[2]].communicate(timeout=20)[0]
    start(K, air[1], chain=False)
    check("%s restarts" % K[2], wait(lambda: up(K) and radio_on(K), 60))
    get(K, "/rrc/send", b"/join lora-mesh")
    get(K, "/rrc/send", b"back from a restart")
    print("(after the restart: within 150 s, not the next names list 10 minutes later)")
    for who in ALL:
        everyone(who, 150)
    right_rooms("after the restart")
for name, proc in nodes.items():
    proc.terminate()
    try:
        log = proc.communicate(timeout=20)[0]
    except subprocess.TimeoutExpired:
        proc.kill()
        log = proc.communicate()[0]
    log = logs.get(name, "") + log
    check("no tracebacks in %s's log" % name, "Traceback" not in log, log[log.find("Traceback"):][:1500])
    if FAIL:
        print("---- %s log (tail) ----\n%s" % (name, log[-3000:]))
stop.set()
print("FAILURES", FAIL)
sys.exit(1 if FAIL else 0)

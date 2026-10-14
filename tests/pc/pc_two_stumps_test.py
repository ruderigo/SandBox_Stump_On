# Two Stumps of a chain talking in #chained, end to end: two computer
# Stumps (the real firmware, stump_pc.py), the first one and a second one
# joining it on the same network, on loopback. Each takes the other in
# from its beacon -- nobody messages anybody first -- and a line said in
# #chained on one shows on the other as "<nick@stump>", once, while
# #lora stays empty. Linux only: it needs two loopback addresses.
# Run: python3 tests/pc/pc_two_stumps_test.py
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import builtins
builtins.input = lambda *a: ""
import provisioner as P

SECRET = "two-stumps-secret"
FIRST, SECOND = ("127.0.8.1", 8096, "Firstpc"), ("127.0.8.2", 8097, "Secondpc")
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

work = tempfile.mkdtemp(prefix="stump-two-")
fw = P.STUMP_APP_DIR
nodes = {}


def start(who, parent=None):
    ip, port, name = who
    folder = os.path.join(work, name)
    os.makedirs(folder)
    P._pc_copy_firmware(fw, folder)
    cfg = open(os.path.join(ROOT, "tests", "config.py"), encoding="utf-8").read()
    cfg += P._pc_config_block({"pc_hotspot_name": name, "pc_heltec": "none",
                               "chain": {"enabled": True, "parent_ip": parent} if parent else {"enabled": True}})
    cfg += ("\nNODE_NAME = %r\nPC_HTTP_PORT = %d\nPC_HOTSPOT_IP = %r\nCHAIN_ENABLED = True\n"
            "CHAIN_UPLINK_SSID = %r\nCHAIN_SECRET = %r\n" % (name, port, ip, "(home)" if parent else "", SECRET))
    open(os.path.join(folder, "config.py"), "w", encoding="utf-8").write(cfg)
    nodes[name] = subprocess.Popen([sys.executable, "-u", "stump_pc.py"], cwd=folder,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def get(who, path, data=None):
    ip, port, _ = who
    req = urllib.request.Request("http://%s:%d%s" % (ip, port, path), data=data)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", "replace")


def room(who, name):
    return json.loads(get(who, "/rrc/poll?room=%s&since=0" % name))["messages"]


def wait(cond, secs):
    t0 = time.time()
    while time.time() - t0 < secs:
        try:
            if cond():
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


start(FIRST)
start(SECOND, parent=FIRST[0])
up = wait(lambda: get(FIRST, "/node.json") and get(SECOND, "/node.json"), 90)
check("both Stumps start", up)
if up:
    for who in (FIRST, SECOND):
        get(who, "/rrc/send", b"/join chained")
    met = wait(lambda: any("~Secondpc" in m["body"] for m in room(FIRST, "chained"))
               and any("~Firstpc" in m["body"] for m in room(SECOND, "chained")), 150)
    check("each takes the other into #chained from its beacon", met,
          (room(FIRST, "chained"), room(SECOND, "chained")))
    get(SECOND, "/rrc/send", b"hello from the second")
    got = wait(lambda: any(m["body"] == "hello from the second" and m["nick"].endswith("@Secondpc")
                           for m in room(FIRST, "chained")), 60)
    check("a line in #chained reaches the other Stump, as nick@stump", got, room(FIRST, "chained"))
    get(FIRST, "/rrc/send", b"hello back")
    got = wait(lambda: any(m["body"] == "hello back" and m["nick"].endswith("@Firstpc")
                           for m in room(SECOND, "chained")), 60)
    check("... and back", got, room(SECOND, "chained"))
    time.sleep(12)
    second = room(SECOND, "chained")
    check("said once, never echoed back", sum(m["body"] == "hello from the second" for m in second) == 1
          and sum(m["body"] == "hello back" for m in second) == 1, second)
    check("no notices crossed", not any("@" in m["nick"] and m["kind"] == "system" for m in second)
          and not any(m["body"].startswith(("✓", "✗", "✎")) and "@" in m["nick"] for m in second), second)
    lora = []
    for who in (FIRST, SECOND):
        get(who, "/rrc/send", b"/join lora")      # the poll answers the room you're in
        lora += [m for m in room(who, "lora")]
    check("#lora stays quiet", not any("hello" in m["body"] for m in lora), lora)
for name, proc in nodes.items():
    proc.terminate()
    try:
        log = proc.communicate(timeout=20)[0]
    except subprocess.TimeoutExpired:
        proc.kill()
        log = proc.communicate()[0]
    check("no tracebacks in %s's log" % name, "Traceback" not in log, log[log.find("Traceback"):][:1500])
    if FAIL:
        annotate("%s log: %s" % (name, log[-2500:]))
shutil.rmtree(work, ignore_errors=True)
print("FAILURES", FAIL)
sys.exit(1 if FAIL else 0)

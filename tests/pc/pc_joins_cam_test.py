# A Stump on a computer JOINING a CAM's chain (docs/PC.md, "The computer
# joining a CAM"), and the Provisioner's chain checks (--check-chain):
#   1. each check that can fail says what's wrong (no network needed);
#   2. a CAM -- the real MicroPython chain and LXMF code -- is the first
#      Stump; the Provisioner's hello is let in with the right secret and
#      not with a wrong one;
#   3. the computer Stump starts as a member; the live check sees the CAM
#      answer it; chat lines cross both ways.
# Needs: the cryptography package, and MICROPYTHON (a MicroPython unix
# port); without MicroPython only part 1 runs.
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import builtins
builtins.input = lambda *a: ""
import provisioner as P

MP = os.environ.get("MICROPYTHON") or "micropython"
HAVE_MP = shutil.which(MP) is not None or os.path.isfile(MP)
CAM, PC, PORT, SECRET = "127.0.4.1", "127.0.5.2", 8095, "pc-chain-secret"
FAIL = []


def annotate(text):
    if os.environ.get("GITHUB_ACTIONS"):
        print("::error::" + text.replace("%", "%25").replace("\r", "").replace("\n", "%0A"))


def _crash(kind, value, tb):
    import traceback
    text = "".join(traceback.format_exception(kind, value, tb))
    print(text)
    annotate("crashed: " + text[-2500:])
    sys.exit(1)

sys.excepthook = _crash


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + repr(info)[:400]))
    if not cond:
        FAIL.append(name)
        annotate(name + ": " + repr(info)[:1500])


def fake_get(table):
    def get(url, timeout=4):
        for k, v in table.items():
            if url.endswith(k):
                if isinstance(v, Exception):
                    raise v
                return v
        raise OSError("connection refused")
    return get


def last(checks):
    return checks[-1]


# 1. what each failure says
ME = "127.0.4.9"                   # the computer, on the CAM's network
on = lambda ip: ME
r = P.chain_preflight(CAM, SECRET, "LaBuche-Stump.web.app", route=lambda ip: "192.168.0.161")
check("not on the CAM's network: says to join its Wi-Fi", not last(r)[0] and "Join 'LaBuche-Stump.web.app'" in last(r)[2], r)
r = P.chain_preflight(CAM, SECRET, route=on, get=fake_get({}))
check("nothing answers: says to check the Stump and its address", not last(r)[0] and "Nothing answers" in last(r)[2], r)
import urllib.error
refused = urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))
r = P.chain_preflight(CAM, SECRET, route=on, get=fake_get({"/chain.json": refused, "/node.json": refused}), wait=0)
check("refused: its Wi-Fi is up, its program stopped, power-cycle", not last(r)[0] and "web server refused" in last(r)[2]
      and ME in last(r)[2] and "power-cycle" in last(r)[2], r)
tries = []
def starting(url, timeout=4):
    tries.append(url)
    if len(tries) < 3:
        raise refused
    return {"enabled": True, "role": "root", "secret": True} if url.endswith("/chain.json") else {"name": "LaBuche", "version": "Beta A"}
real_sleep = P.time.sleep
P.time.sleep = lambda s: None
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()) as said:
    r = P.chain_preflight(CAM, SECRET, route=on, get=starting, hello=lambda *a: True, wait=30)
P.time.sleep = real_sleep
check("refused while starting: waits, then goes on", all(ok for ok, _, _ in r) and "trying again" in said.getvalue()
      and "LaBuche" in r[1][1], (r, said.getvalue()))
import urllib.request
check("no proxy between this computer and a Stump", "ProxyHandler({})" in open(P.__file__).read())
r = P.chain_preflight(CAM, SECRET, route=on, get=fake_get({"/node.json": {"name": "Old", "version": "0.9"}}))
check("old firmware: says to update it", not last(r)[0] and "--upload-app" in last(r)[2], r)
r = P.chain_preflight(CAM, SECRET, route=on, get=fake_get({"/chain.json": {"enabled": False}}))
check("chain off on the CAM: says how to turn it on", not last(r)[0] and "CHAIN_ENABLED = True" in last(r)[2], r)
r = P.chain_preflight(CAM, "", route=on, get=fake_get({"/chain.json": {"enabled": True, "role": "root", "secret": True}}))
check("secret on the CAM only: says to enter it", not last(r)[0] and "has a chain secret and this one has none" in last(r)[2], r)
r = P.chain_preflight(CAM, SECRET, route=on, get=fake_get({"/chain.json": {"enabled": True, "role": "root", "secret": False}}))
check("secret here only: says to give both the same", not last(r)[0] and "no chain secret and this one does" in last(r)[2], r)
r = P.chain_preflight(CAM, SECRET, route=on, hello=lambda *a: False,
                      get=fake_get({"/chain.json": {"enabled": True, "role": "root", "secret": True}}))
check("hello refused: says the secrets differ, or the firewall", not last(r)[0] and "wrong chain secret" in last(r)[2]
      and "firewall" in last(r)[2], r)
r = P.check_remote_chain("192.168.5.1", get=fake_get({"/chain.json": {"enabled": True, "role": "member",
                         "uplink": {"ssid": "Stump 4", "ip": None}}}))
check("a CAM member that hasn't joined: says what to check", not last(r)[0] and "CHAIN_UPLINK_SSID" in last(r)[2], r)
r = P.check_remote_chain("192.168.5.1", get=fake_get({"/chain.json": {"enabled": True, "role": "member",
                         "uplink": {"ssid": "Stump 4", "ip": "192.168.4.20", "parent": "192.168.4.1", "parent_heard_s": None}}}))
check("a CAM member not answered: says secrets / chain on", not last(r)[0] and "CHAIN_SECRET" in last(r)[2], r)
r = P.check_remote_chain("192.168.5.1", get=fake_get({"/chain.json": {"enabled": True, "role": "member",
                         "uplink": {"ssid": "Stump 4", "ip": "192.168.4.20", "parent": "192.168.4.1", "parent_heard_s": 5}}}))
check("a linked CAM member: all good", all(ok for ok, _, _ in r), r)

if not HAVE_MP:
    print("SKIP the CAM half (no MicroPython here)")
    print("FAILURES", FAIL)
    sys.exit(1 if FAIL else 0)

# 2. a real CAM as the first Stump; the Provisioner's hello
work = tempfile.mkdtemp(prefix="stump-join-")
fw = P.STUMP_APP_DIR
lxmf_file = os.path.join(work, "pc_lxmf")
os.makedirs(os.path.join(work, "cam", "cam"))
cam = subprocess.Popen([MP, os.path.join(ROOT, "tests", "mp", "pc_chain_cam_root.py"), "x", os.path.join(work, "cam"), lxmf_file],
                       cwd=fw, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(6)
check("a wrong secret isn't let in", P.chain_hello(CAM, "not-the-secret", ME) is False)
cam_chain = {"/chain.json": {"enabled": True, "role": "root", "secret": True}}
r = P.chain_preflight(CAM, SECRET, "CAM", route=on, get=fake_get(cam_chain))
check("the right secret is let in: every check passes", all(ok for ok, _, _ in r), r)

# 3. the computer Stump joins it
folder = os.path.join(work, "Stump")
os.makedirs(folder)
P._pc_copy_firmware(fw, folder)
cfg = open(os.path.join(ROOT, "tests", "config.py"), encoding="utf-8").read()
cfg += P._pc_config_block({"pc_hotspot_name": "CAM", "pc_heltec": "none",
                           "chain": {"enabled": True, "uplink_ssid": "CAM", "parent_ip": CAM}})
cfg += "\nPC_HTTP_PORT = %d\nPC_HOTSPOT_IP = %r\nCHAIN_ENABLED = True\nCHAIN_UPLINK_SSID = 'CAM'\nCHAIN_SECRET = %r\n" % (
    PORT, PC, SECRET)
open(os.path.join(folder, "config.py"), "w", encoding="utf-8").write(cfg)
node = subprocess.Popen([sys.executable, "-u", "stump_pc.py"], cwd=folder,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def get(path, data=None):
    with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path), data=data), timeout=10) as r:
        return r.read().decode("utf-8", "replace")


real_and_cam = lambda url, timeout=4: P._get_json(url, timeout) if "127.0.0.1" in url else {"below": [PC]}
r = P.chain_live(folder, CAM, wait=90, get=real_and_cam)
check("live check: running, a member, answered by the CAM, listed below", all(ok for ok, _, _ in r) and len(r) == 3, r)
lxmf = json.loads(get("/node.json"))["lxmf"]
open(lxmf_file, "w").write(lxmf)
get("/rrc/send", b"/join lxmf")
arrived = False
t0 = time.time()
while time.time() - t0 < 90 and not arrived:
    time.sleep(3)
    arrived = any("hello from the root CAM" in m["body"] for m in json.loads(get("/rrc/poll?room=lxmf&since=0"))["messages"])
check("the CAM's chat line reaches the computer's #lxmf", arrived)
import re
names = " ".join(m["body"] for m in json.loads(get("/rrc/poll?room=lxmf&since=0"))["messages"])
nick = (re.findall(r"~[\w-]+", names) or ["~camroot"])[-1]
reply = get("/rrc/send", ("/msg %s hello from the laptop" % nick).encode())
time.sleep(20)
cam.kill()
out = cam.communicate()[0]
check("the computer's /msg reaches the CAM", "hello from the laptop" in out, (reply, out[-800:]))
node.terminate()
try:
    log = node.communicate(timeout=20)[0]
except subprocess.TimeoutExpired:
    node.kill()
    log = node.communicate()[0]
check("no tracebacks in the computer Stump's log", "Traceback" not in log, log[log.find("Traceback"):][:1500])
shutil.rmtree(work, ignore_errors=True)
print("FAILURES", FAIL)
sys.exit(1 if FAIL else 0)

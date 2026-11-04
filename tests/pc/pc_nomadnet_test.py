# The NomadNet pack end to end: a computer Stump with the pack, and the
# official Reticulum library (what NomadNet and MeshChat run) on the
# other side of a TCP link, browsing it as NomadNet does: a path request
# to the Stump's nomadnetwork.node, a link, Identify, page requests, and
# a line said in a room through a form. Needs rns (pip install rns):
# run by the "reference" job. Run: python3 tests/pc/pc_nomadnet_test.py
import os, shutil, subprocess, sys, tempfile, time, json, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import builtins
builtins.input = lambda *a: ""
import provisioner as P
import RNS

PORT, IP, RNS_PORT = 8097, "127.0.0.1", 4297
FAIL = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + repr(info)[:600]))
    if not cond:
        FAIL.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print("::error::" + (name + ": " + repr(info)[:1500]).replace("%", "%25").replace("\n", "%0A"))


def get(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://%s:%d%s" % (IP, PORT, path), timeout=10) as r:
        return r.status, r.read().decode("utf-8", "replace")


# The reference side: a Reticulum instance with a TCP server the Stump
# connects to (as a NomadNet laptop on the same network would be).
work = tempfile.mkdtemp(prefix="stump-nn-")
rcfg = os.path.join(work, "rns")
os.makedirs(rcfg)
open(os.path.join(rcfg, "config"), "w").write("""[reticulum]
  enable_transport = False
  share_instance = No
  panic_on_interface_error = No
[logging]
  loglevel = 2
[interfaces]
  [[Stump link]]
    type = TCPServerInterface
    enabled = yes
    listen_ip = 127.0.0.1
    listen_port = %d
""" % RNS_PORT)
RNS.Reticulum(configdir=rcfg)
me = RNS.Identity()

# The Stump: a computer Stump folder, the pack's plugin in it, a TCP
# client to the reference instance.
folder = os.path.join(work, "Stump")
os.makedirs(folder)
P._pc_copy_firmware(P.STUMP_APP_DIR, folder)
shutil.copytree(os.path.join(ROOT, "packs", "nomadnet-pack", "nomadnet"), os.path.join(folder, "nomadnet"),
                ignore=shutil.ignore_patterns("__pycache__"))
cfg = open(os.path.join(ROOT, "tests", "config.py"), encoding="utf-8").read()
cfg += P._pc_config_block({"pc_hotspot_name": "x", "pc_heltec": "none"})
cfg += ("\nPC_HTTP_PORT = %d\nPC_HOTSPOT_IP = %r\nAUTH_ADMIN_PASSWORD = 'pw'\nNODE_NAME = 'Souche'\n"
        "CONFIG['interfaces'].append({'type': 'TCPClientInterface', 'name': 'ref', 'enabled': True,"
        " 'target_host': '127.0.0.1', 'target_port': %d})\n") % (PORT, IP, RNS_PORT)
open(os.path.join(folder, "config.py"), "w", encoding="utf-8").write(cfg)
log = open(os.path.join(work, "stump.out"), "w")
stump = subprocess.Popen([sys.executable, "-u", "stump_pc.py"], cwd=folder, stdout=log, stderr=subprocess.STDOUT)

try:
    up, t0 = False, time.time()
    while time.time() - t0 < 60 and not up:
        try:
            up = get("/node.json")[0] == 200
        except Exception:
            time.sleep(1)
    check("the computer Stump runs, with the pack", up)
    s, hello = get("/hello")
    pub = bytes.fromhex(json.loads(hello)["pub"])
    stump_id = RNS.Identity(create_keys=False)
    stump_id.load_public_key(pub)
    node = RNS.Destination.hash(stump_id, "nomadnetwork", "node")

    # Like NomadNet: ask for a path, then open a link.
    t0 = time.time()
    RNS.Transport.request_path(node)
    while not RNS.Transport.has_path(node) and time.time() - t0 < 60:
        time.sleep(0.5)
        if int(time.time() - t0) % 10 == 0:
            RNS.Transport.request_path(node)
    check("its NomadNet node answers a path request", RNS.Transport.has_path(node))
    ident = RNS.Identity.recall(node)
    dest = RNS.Destination(ident, RNS.Destination.OUT, RNS.Destination.SINGLE, "nomadnetwork", "node")
    link = RNS.Link(dest)
    t0 = time.time()
    while link.status != RNS.Link.ACTIVE and time.time() - t0 < 30:
        time.sleep(0.2)
    check("a link to it, as NomadNet's browser opens", link.status == RNS.Link.ACTIVE, link.status)

    def page(path, data=None):
        box = {}
        link.request(path, data=data, response_callback=lambda r: box.update(ok=r.response),
                     failed_callback=lambda r: box.update(failed=True), timeout=30)
        t0 = time.time()
        while not box and time.time() - t0 < 35:
            time.sleep(0.2)
        r = box.get("ok")
        return r.decode("utf-8", "replace") if isinstance(r, bytes) else r

    b = page("/page/index.mu")
    check("its home page, in micron, with the Stump's name", b is not None and "Souche" in b
          and ":/page/rooms.mu]" in b, b)
    b = page("/page/rooms.mu")
    check("the rooms", b is not None and "room=main]" in b, b)
    link.identify(me)
    time.sleep(1)
    b = page("/page/room.mu", {"var_room": "main"})
    check("identified: the room has a field to say something", b is not None and "<48|msg`>" in b, b)
    b = page("/page/say.mu", {"var_room": "main", "field_msg": "hello from the reference library"})
    check("said through the form: back on the room's page", b is not None and "hello from the reference library" in b, b)
    s, poll = get("/rrc/poll?room=main&since=0")
    check("... and in the Stump's chat, for everyone", "hello from the reference library" in poll, poll[-600:])
    b = page("/page/board.mu")
    check("the billboard", b is not None and "<40|title`>" in b, b)
    link.teardown()
finally:
    stump.terminate()
    try:
        stump.wait(10)
    except Exception:
        stump.kill()
    log.close()
    if FAIL:
        print(open(os.path.join(work, "stump.out")).read()[-3000:])
print("FAILURES", FAIL)
sys.exit(1 if FAIL else 0)

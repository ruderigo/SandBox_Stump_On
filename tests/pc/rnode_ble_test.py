# RNodeBLEInterface (a Heltec over Bluetooth, for Stump on a computer)
# against a simulated RNode behind a stand-in for bleak: found by name,
# the handshake and radio set-up over the Bluetooth serial service, writes
# cut to the link's size, a packet in, the link dropping (red at once,
# back by itself), no Heltec around (says what to check), and the radio
# off on close. Run: python3 tests/pc/rnode_ble_test.py
import os, sys, time, types, asyncio as aio
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, "pc", "pc_compat"), os.path.join(ROOT, "final_firmware")]
import stump_host
stump_host.install(os.path.join(ROOT, "final_firmware"))
from urns.log import set_loglevel, LOG_NONE
set_loglevel(LOG_NONE)

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD
FAIL = []


def annotate(text):
    if os.environ.get("GITHUB_ACTIONS"):
        print("::error::" + text.replace("%", "%25").replace("\r", "").replace("\n", "%0A"))


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + repr(info)[:400]))
    if not cond:
        FAIL.append(name)
        annotate(name + ": " + repr(info)[:1500])


def frames(raw):
    out, cur, esc, inside = [], None, False, False
    for b in raw:
        if b == FEND:
            if inside and cur:
                out.append((cur[0], bytes(cur[1:])))
            cur, inside = bytearray(), True
        elif inside:
            if b == FESC:
                esc = True
            else:
                if esc:
                    b = FEND if b == TFEND else FESC if b == TFESC else b
                    esc = False
                cur.append(b)
    return out


def kiss(cmd, payload):
    body = bytearray()
    for b in payload:
        body += bytes([FESC, TFEND]) if b == FEND else bytes([FESC, TFESC]) if b == FESC else bytes([b])
    return bytes([FEND, cmd]) + bytes(body) + bytes([FEND])


# ---- a stand-in for bleak, with an RNode behind it -------------------------
UART = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
radio = {"around": True, "answering": True, "written": bytearray(), "writes": [], "client": None, "seen": b""}
DETECT = bytes([FEND, 0x08, 0x73, FEND])


class Dev:
    name, address = "RNode 3B87", "AA:BB:CC:DD:EE:01"


class Adv:
    local_name = "RNode 3B87"
    service_uuids = [UART]


class Scanner:
    @staticmethod
    async def find_device_by_filter(f, timeout=5.0):
        await aio.sleep(0.05)
        return Dev() if radio["around"] and f(Dev(), Adv()) else None


class Char:
    max_write_without_response_size = 20


class Service:
    def get_characteristic(self, u):
        return Char()


class Services:
    def get_service(self, u):
        return Service()


class Client:
    def __init__(self, dev, disconnected_callback=None, timeout=10):
        self.cb = disconnected_callback
        self.services = Services()
        self.notify = None
        self.up = False

    async def __aenter__(self):
        self.up = True
        radio["client"] = self
        return self

    async def __aexit__(self, *a):
        self.up = False

    async def start_notify(self, uuid, cb):
        self.notify = cb

    async def write_gatt_char(self, char, data, response=False):
        radio["writes"].append(len(data))
        radio["written"].extend(data)
        # Answers each "are you an RNode?" once, however it was cut up.
        seen = radio["seen"] + bytes(data)
        if radio["answering"] and DETECT in seen:
            self.notify(None, bytearray(kiss(0x08, b"\x46") + kiss(0x50, b"\x01\x4e") + kiss(0x48, b"\x80")))
            seen = seen[seen.rindex(DETECT) + len(DETECT):]
        radio["seen"] = seen[-8:]

    def drop(self):
        self.up = False
        self.cb(self)


bleak = types.ModuleType("bleak")
bleak.BleakScanner, bleak.BleakClient = Scanner, Client
sys.modules["bleak"] = bleak

import urns.interfaces.rnode_ble as rb
rb.RETRY_S = 0.3
import uasyncio as asyncio

iface = rb.RNodeBLEInterface({"target": "RNode 3B87", "frequency": 917112000, "bandwidth": 125000,
                              "txpower": 14, "spreadingfactor": 8, "codingrate": 5})
received = []
iface.process_incoming = lambda data: received.append(bytes(data))


async def run(seconds):
    t = asyncio.create_task(iface.poll_loop())
    await asyncio.sleep(seconds)
    t.cancel()

asyncio.run(run(rb.RNodeBLEInterface.LOOK_EVERY + 1.5))
st = iface.status()
check("found by name over Bluetooth, handshake answered: online", iface.online and st["state"] == "online"
      and st["kind"] == "ble" and st["fw"] == "1.78" and "RNode 3B87" in st["where"], st)
f = [x for x in frames(radio["written"]) if x[0] not in (0x08, 0x50, 0x48)]
check("radio set up over Bluetooth, the mesh's frequency", [c for c, p in f][:6] == [1, 2, 3, 4, 5, 6]
      and f[0][1] == (917112000).to_bytes(4, "big") and f[2][1] == b"\x0e", f[:6])

radio["written"].clear()
radio["writes"].clear()
pkt = bytes(range(100)) + bytes([FEND])
iface.process_outgoing(pkt)
asyncio.run(run(0.5))
check("a packet goes out whole, cut to the link's size", frames(radio["written"]) == [(0, pkt)]
      and max(radio["writes"]) <= 20 and len(radio["writes"]) > 1, (frames(radio["written"]), radio["writes"]))
incoming = bytes(range(50)) + b"in"
radio["client"].notify(None, bytearray(kiss(0x00, incoming)))
asyncio.run(run(0.4))
check("a packet comes in", received == [incoming], received)

# The link drops (out of range, Heltec off): red at once, and it comes
# back by itself.
radio["around"] = False
radio["client"].drop()
asyncio.run(run(1.6))
st = iface.status()
check("link dropped: offline, red, says so", not iface.online and st["state"] == "error" and st["error"], st)
asyncio.run(run(1.5))
st = iface.status()
check("no Heltec around: says to check it's on, Bluetooth on, paired", not iface.online
      and "paired" in (st["error"] or ""), st)
radio["around"] = True
radio["written"].clear()
asyncio.run(run(2.5))
check("back in range: reconnects by itself, handshake and set-up again", iface.online
      and [c for c, p in frames(radio["written"])][:3] == [0x08, 0x50, 0x48], (iface.status(), frames(radio["written"])[:4]))

# /admin's retry works the same way.
iface.retry_now()
asyncio.run(run(1.5))
check("retry: online again", iface.online)

# Stopping the Stump: radio off, then leave.
radio["written"].clear()
iface.close()
time.sleep(0.5)
check("on close: radio off, then leave", frames(radio["written"]) == [(0x06, b"\x00"), (0x0A, b"\xff")],
      frames(radio["written"]))

# No bleak in that Python: says how to get it.
del sys.modules["bleak"]
import builtins
real_import = builtins.__import__
builtins.__import__ = lambda n, *a, **k: (_ for _ in ()).throw(ImportError(n)) if n == "bleak" else real_import(n, *a, **k)
p = rb._BLEPort("auto")
time.sleep(0.3)
builtins.__import__ = real_import
check("without bleak: says the Provisioner installs it", "bleak" in (p.error or "") and not p.connected, p.error)
print("FAILURES", FAIL)
sys.exit(1 if FAIL else 0)

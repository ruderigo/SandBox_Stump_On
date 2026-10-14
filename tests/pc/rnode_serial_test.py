# RNodeSerialInterface (a Heltec on USB, for Stump on a computer) against a
# simulated RNode on a pseudo-terminal: the radio set-up it sends on
# connect, a packet out, a packet in, and an unplug and replug.
# Linux/macOS (pty). Run: python3 tests/pc/rnode_serial_test.py
import os, sys, pty, time, threading
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, "pc", "pc_compat"), os.path.join(ROOT, "final_firmware")]
import stump_host
stump_host.install(os.path.join(ROOT, "final_firmware"))
import tty
import urns.interfaces.rnode_serial as rs
rs.BOOT_WAIT_S = 0.2
from urns.log import set_loglevel, LOG_NONE
set_loglevel(LOG_NONE)

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD
FAIL = []


def annotate(text):
    """On GitHub Actions, a failure shows as an annotation (readable without the log)."""
    if os.environ.get("GITHUB_ACTIONS"):
        print("::error::" + text.replace("%", "%25").replace("\r", "").replace("\n", "%0A"))


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + repr(info)[:300]))
    if not cond:
        FAIL.append(name)
        annotate(name + ": " + repr(info)[:1500])


def frames(raw):
    """KISS frames in raw bytes -> [(command, payload)]."""
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
        if b == FEND:
            body += bytes([FESC, TFEND])
        elif b == FESC:
            body += bytes([FESC, TFESC])
        else:
            body.append(b)
    return bytes([FEND, cmd]) + bytes(body) + bytes([FEND])


master, slave = pty.openpty()
tty.setraw(slave)
port = os.ttyname(slave)
got = bytearray()
stop = threading.Event()


def reader():
    os.set_blocking(master, False)
    while not stop.is_set():
        try:
            got.extend(os.read(master, 4096))
        except (BlockingIOError, OSError):
            time.sleep(0.02)

threading.Thread(target=reader, daemon=True).start()
iface = rs.RNodeSerialInterface({"port": port, "frequency": 915000000, "bandwidth": 125000,
                                 "txpower": 7, "spreadingfactor": 8, "codingrate": 5})
time.sleep(0.5)
f = frames(got)
cmds = [c for c, p in f]
# RNode commands: FREQUENCY 0x01, BANDWIDTH 0x02, TXPOWER 0x03, SF 0x04, CR 0x05, RADIO_STATE 0x06
check("online after connect", iface.online)
check("radio set up on connect, in order", cmds[:6] == [0x01, 0x02, 0x03, 0x04, 0x05, 0x06], cmds)
check("frequency 915 MHz", f[0][1] == (915000000).to_bytes(4, "big"), f[0])
check("bandwidth 125 kHz", f[1][1] == (125000).to_bytes(4, "big"))
check("power 7, SF8, CR5, radio on", [p for c, p in f[2:6]] == [b"\x07", b"\x08", b"\x05", b"\x01"], f[2:6])

got.clear()
pkt = bytes(range(40)) + bytes([FEND, FESC]) + b"tail"
iface.process_outgoing(pkt)
time.sleep(0.3)
check("a packet goes out as one data frame, escaped", frames(got) == [(0x00, pkt)], frames(got))
check("no keepalive frames on USB", iface.KEEPALIVE_INTERVAL > 10 ** 6)

received = []
iface.process_incoming = lambda data: received.append(bytes(data))
import uasyncio as asyncio


async def run(seconds):
    t = asyncio.create_task(iface.poll_loop())
    await asyncio.sleep(seconds)
    t.cancel()

incoming = bytes(range(60)) + bytes([FEND]) + b"in"
os.write(master, b"boot noise" + kiss(0x00, incoming) + kiss(0x25, b"\x01\x02"))
asyncio.run(run(0.5))
check("a packet comes in (boot noise and other commands ignored)", received == [incoming], received)

# Unplug: the port goes away; the interface goes offline and retries.
stop.set()
os.close(master)
asyncio.run(run(0.5))
check("unplugged: offline", not iface.online)
print("FAILURES", FAIL)
sys.exit(1 if FAIL else 0)

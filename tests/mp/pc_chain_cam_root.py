# A CAM Stump as the FIRST Stump of a chain, with a Stump on a computer
# joining it (docs/PC.md, "The computer joining a CAM"): the real
# MicroPython chain and LXMF code, on loopback. The CAM's hub is on
# 127.0.4.1; the computer joins from 127.0.5.2. Once the test writes the
# computer's LXMF address to the file named on the command line, the CAM
# sends it a chat line, and prints any message the computer sends back.
# tests/pc/pc_joins_cam_test.py runs it.
import sys, time
sys.path.insert(0, '.')
work, lxmf_file = sys.argv[2], sys.argv[3]
from urns.log import LOG_NONE, set_loglevel
set_loglevel(LOG_NONE)
from urns import Reticulum
from urns.transport import Transport
from urns.identity import Identity
import uasyncio as asyncio
from node_common import setup_node

rns = Reticulum(config_path=work + "/cam/config.json", loglevel=LOG_NONE)
rns.config = {"enable_transport": True, "interfaces": [
    {"type": "ChainHubInterface", "listen_ip": "127.0.4.1", "listen_port": 4242,
     "secret": "pc-chain-secret"}]}
dest, router = setup_node(rns, "camroot")


def got(msg):
    try:
        print("CAM got:", msg.content_as_string())
    except Exception as e:
        print("CAM got a message", e)

try:
    router.register_delivery_callback(got)
except Exception as e:
    print("CAM no callback", e)
rns.setup_interfaces()
print("CAM lxmf", bytes(dest.hash).hex())


async def main():
    hub = rns.interfaces[0]
    t0 = time.time()
    while not hub.peers and time.time() - t0 < 60:
        await asyncio.sleep(0.5)
    print("CAM", "computer joined below" if hub.peers else "FAIL nobody joined")
    target = None
    while target is None:
        try:
            target = bytes.fromhex(open(lxmf_file).read().strip())
        except (OSError, ValueError):
            await asyncio.sleep(1)
    router.announce()
    t0 = time.time()
    while Identity.recall(target) is None and time.time() - t0 < 60:
        Transport.request_path(target)
        await asyncio.sleep(3)
    if Identity.recall(target) is None:
        print("CAM FAIL computer's LXMF address never known")
        return
    router.send_message(target, "hello from the root CAM")
    print("CAM sent")
    while True:
        router.announce()
        await asyncio.sleep(10)


async def both():
    asyncio.create_task(main())
    await rns.run()

try:
    asyncio.run(asyncio.wait_for(both(), 240))
except Exception as e:
    print("CAM end:", type(e).__name__)

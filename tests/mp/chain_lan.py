# A board Stump that joins its chain over the home Wi-Fi (1.0.0-beta.56),
# like a computer Stump: it stays on WIFI_SSID (its home address, the
# clock, internet), links to the first Stump at CHAIN_PARENT_IP there, and
# finds it again on that network when the router moved it -- never leaving
# the network to scan for hotspots.
import sys
exec(open(sys.argv[1] + '/harness.py').read())
import config, chain
import uasyncio as asyncio
FAIL = []


def check(n, c, i=''):
    print(('PASS ' if c else 'FAIL ') + n + ('' if c else '  ' + repr(i)[:400]))
    if not c:
        FAIL.append(n)


config.CHAIN_ENABLED = True
config.CHAIN_UPLINK_SSID = ""
config.CHAIN_PARENT_IP = "192.168.0.173"
config.WIFI_SSID = "Bob's Glitch"
config.CHAIN_SUBNET = 6
config.CHAIN_SECRET = "s3cret"
s = chain.settings()
check("a member over the home Wi-Fi: not the first Stump, its uplink the home Wi-Fi",
      not chain.is_root(s) and chain.over_lan(s) and s["uplink_ssid"] == "Bob's Glitch", s)
check("... its own hotspot as usual (192.168.6.1)", chain.ap_ip(s) == "192.168.6.1")
check("... the uplink goes to the first Stump's home address, not the router",
      chain.parent_address(s, "192.168.0.1") == "192.168.0.173")
ifs = chain.interfaces(s, "192.168.0.120", chain.parent_address(s, "192.168.0.1"), "192.168.6.1", lan_ip="192.168.0.120")
up = [i for i in ifs if i["type"] == "ChainUplinkInterface"]
down = [i for i in ifs if i["type"] == "ChainHubInterface"]
check("... interfaces: up to 192.168.0.173 from its home address, down on its own hotspot, no LAN hub",
      len(up) == 1 and up[0]["forward_ip"] == "192.168.0.173" and up[0]["listen_ip"] == "192.168.0.120"
      and len(down) == 1 and down[0]["listen_ip"] == "192.168.6.1", ifs)
check("... the boot's note of it", chain.note_lan_uplink(s, "192.168.0.120") == ("192.168.0.120", "192.168.0.173"))
chain._state["uplink"] = None
st = chain.status()
check("... /chain.json says so", st["role"] == "member" and st["uplink"]["over_lan"] is True, st["uplink"])

# A hotspot member is unchanged
config.CHAIN_PARENT_IP = ""
config.CHAIN_UPLINK_SSID = "LaBuche-Stump.web.app"
s2 = chain.settings()
check("a member through a hotspot: unchanged (the gateway is the Stump above)",
      not chain.over_lan(s2) and chain.parent_address(s2, "192.168.4.1") == "192.168.4.1")
config.CHAIN_UPLINK_SSID = ""
config.CHAIN_PARENT_IP = "192.168.0.173"

# The router gave the first Stump another address: found again on the
# network by discovery's question, and only the right one is taken.
OURS = chain.chain_id(s)
config.CHAIN_SECRET = "other"
THEIRS = chain.chain_id()
config.CHAIN_SECRET = "s3cret"
CARD = b'{"stump": 1, "name": "x"}'


class Sock:
    def __init__(self, replies):
        self.sent = []
        self.q = list(replies)

    def sendto(self, data, addr):
        self.sent.append(data)

    def recvfrom(self, n):
        if self.q:
            return self.q.pop(0)
        raise OSError(11)


NET = {
    "192.168.0.50": {"enabled": True, "role": "member", "chain": OURS, "lan_ip": None},       # a member
    "192.168.0.60": {"enabled": True, "role": "root", "chain": THEIRS, "lan_ip": "192.168.0.60"},  # another chain
    "192.168.0.70": {"enabled": True, "role": "root", "chain": OURS, "lan_ip": None},          # not taking links here
    "192.168.0.181": {"enabled": True, "role": "root", "chain": OURS, "lan_ip": "192.168.0.181"},  # it
}
asked = []


def get(ip, path, timeout=2):
    asked.append((ip, path))
    return NET.get(ip)


chain._state["sta_ip"] = "192.168.0.120"
sock = Sock([(CARD, ("192.168.0.%d" % n, 4244)) for n in (50, 60, 70, 181)] + [(CARD, ("192.168.0.120", 4244))])
found = asyncio.run(chain.find_parent_on_lan(s, sock=sock, get=get, wait_s=0.5))
check("moved: found again on the network (the first Stump of this chain, taking links there)",
      found == "192.168.0.181", (found, asked))
check("... asked by discovery's question, broadcast", sock.sent and sock.sent[0] == b"STUMP?", sock.sent)
check("... its own answer not asked", ("192.168.0.120", "/chain.json") not in asked, asked)
sock = Sock([(CARD, ("192.168.0.60", 4244))])
check("nobody of this chain answers: None (it tries again later)",
      asyncio.run(chain.find_parent_on_lan(s, sock=sock, get=get, wait_s=0.3)) is None)
chain._state["lan_parent"] = "192.168.0.181"
check("... and the uplink then goes to where it was found", chain.parent_address(s, "192.168.0.1") == "192.168.0.181")
chain._state["lan_parent"] = None

# Off the router (at boot it wasn't there, or it dropped): the router is
# joined again, and never a Stump hotspot (beta.56: a WROVER set up for
# the router joined LaBuche's hotspot)
class STA:
    def __init__(self):
        self.joined = []
        self.scanned = 0
    def active(self, on=None):
        return True
    def isconnected(self):
        return False
    def connect(self, ssid, psk=""):
        self.joined.append(ssid)
    def scan(self):
        self.scanned += 1
        return [(b"LaBuche-Stump.web.app", b"", 11, -40, 0, 0)]


config.CHAIN_PARENT_IP = "192.168.0.173"
config.CHAIN_UPLINK_SSID = ""
config.WIFI_SSID = "Bob's Glitch"
config.WIFI_PASS = "pw"
s = chain.settings()
sta = STA()
chain._state["rejoin_at"] = 0
check("off the router: joins it again", chain.rejoin_router(s, sta, 100) and sta.joined == ["Bob's Glitch"], sta.joined)
check("... not again within REJOIN_S", not chain.rejoin_router(s, sta, 100 + chain.REJOIN_S - 1) and len(sta.joined) == 1)
check("... and again after it", chain.rejoin_router(s, sta, 100 + chain.REJOIN_S + 1) and len(sta.joined) == 2)
check("... never a scan for Stump hotspots", sta.scanned == 0)
config.CHAIN_ENABLED = False
config.CHAIN_PARENT_IP = ""
print('FAILURES:', FAIL)

# Project Stump -- chain.py
#
# Stumps linked to each other over Wi-Fi, so big transfers between them
# never touch LoRa (docs/CHAIN.md). Each Stump in a chain:
#
#   - serves its own Wi-Fi on its own subnet, 192.168.<CHAIN_SUBNET>.1
#     (every Stump in a chain needs a different number);
#   - except the first one (the root), joins the Wi-Fi of the Stump before
#     it as a station (CHAIN_UPLINK_SSID) -- the "uplink";
#   - speaks Reticulum to its neighbours in UDP on both: up through the
#     uplink, down to whoever joined its own Wi-Fi (other Stumps, and PCs
#     running Reticulum), with transport on so it relays for them.
#
# The ESP32 can't route ordinary IP between its two Wi-Fi sides, but it
# can relay Reticulum -- which is all the chain needs.
#
# config.py:
#   CHAIN_ENABLED     = True
#   CHAIN_UPLINK_SSID = ""      # the neighbour Stump's Wi-Fi; "" = this is the root
#   CHAIN_UPLINK_PASS = ""
#   CHAIN_SUBNET      = 4       # this Stump's Wi-Fi is 192.168.<n>.1 (4..254, unique per Stump)
#   CHAIN_CHANNEL     = 11      # root only: the Wi-Fi channel the whole chain uses
#   CHAIN_SECRET      = ""      # the same on every Stump of the chain (strongly advised)
#   CHAIN_PORT        = 4242
#   CHAIN_LAN         = True    # root only, with a secret: also take chain links on
#                               # the Wi-Fi it joined (WIFI_SSID), so a computer on
#                               # the same home network joins without switching Wi-Fi

import time

DEFAULT_SUBNET = 4
DEFAULT_PORT = 4242

_state = {"sta_ip": None, "parent_ip": None, "ap_ip": None, "uplink": None, "hub": None,
          "hubs": [], "lan_ip": None}


def settings():
    """The chain settings, or None when this Stump isn't in a chain."""
    try:
        import config as c
    except ImportError:
        return None
    if not getattr(c, "CHAIN_ENABLED", False):
        return None
    try:
        subnet = int(getattr(c, "CHAIN_SUBNET", DEFAULT_SUBNET))
    except (TypeError, ValueError):
        subnet = DEFAULT_SUBNET
    if not 1 <= subnet <= 254:
        subnet = DEFAULT_SUBNET
    try:
        channel = int(getattr(c, "CHAIN_CHANNEL", 0) or 0)
    except (TypeError, ValueError):
        channel = 0
    return {
        "uplink_ssid": (getattr(c, "CHAIN_UPLINK_SSID", "") or "").strip(),
        "uplink_pass": getattr(c, "CHAIN_UPLINK_PASS", "") or "",
        "subnet": subnet,
        "channel": channel if 1 <= channel <= 13 else 0,
        "secret": getattr(c, "CHAIN_SECRET", "") or "",
        "port": int(getattr(c, "CHAIN_PORT", DEFAULT_PORT) or DEFAULT_PORT),
        "lan": bool(getattr(c, "CHAIN_LAN", True)),
    }


def ap_ip(s=None):
    """This Stump's own Wi-Fi address: 192.168.<subnet>.1 -- or, for a
    Stump on a computer (docs/PC.md), its hotspot's real address."""
    try:
        import stump_host
        return stump_host.hotspot_ip()
    except ImportError:
        pass
    s = s or settings()
    return "192.168.%d.1" % (s["subnet"] if s else DEFAULT_SUBNET)


def ap_prefix():
    """'192.168.<subnet>.' -- who's on this Stump's own Wi-Fi."""
    return ap_ip()[:-1]


def is_root(s=None):
    s = s or settings()
    return bool(s) and not s["uplink_ssid"]


def connect_uplink(s, timeout=20):
    """Joins the parent Stump's Wi-Fi as a station. Returns (sta_ip,
    parent_ip) or (None, None). Reconnects by itself afterwards."""
    import network
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        sta.config(reconnects=-1)          # keep trying if the parent reboots
    except Exception:
        pass
    if not sta.isconnected():
        print("[chain] joining %r ..." % s["uplink_ssid"])
        sta.connect(s["uplink_ssid"], s["uplink_pass"])
        t0 = time.time()
        while not sta.isconnected():
            if time.time() - t0 > timeout:
                print("[chain] couldn't join %r yet; will keep trying" % s["uplink_ssid"])
                return None, None
            time.sleep(0.5)
    try:
        sta.config(pm=0)                   # no power save: it costs throughput
    except Exception:
        pass
    ip, mask, gw, dns = sta.ifconfig()
    _state["sta_ip"], _state["parent_ip"] = ip, gw
    try:
        rssi = sta.status("rssi")
    except Exception:
        rssi = "?"
    print("[chain] uplink: %s via %s (signal %s dBm)" % (ip, gw, rssi))
    return ip, gw


def interfaces(s, sta_ip, parent_ip, own_ap_ip, lan_ip=None):
    """The Reticulum interface configs for this Stump's place in the chain.
    lan_ip: the first Stump's address on the Wi-Fi it joined (WIFI_SSID),
    where it also takes chain links when it has a chain secret -- a
    computer on that same network (home, office) then joins the chain
    without leaving it. Never without a secret: anyone on that network
    could sit on the chain."""
    out = []
    # A Stump on a computer with one Wi-Fi radio joins its parent and serves
    # visitors on that same network: no separate side below it.
    if own_ap_ip != sta_ip:
        out.append({"type": "ChainHubInterface", "name": "Chain down", "enabled": True,
                    "listen_ip": own_ap_ip, "listen_port": s["port"], "secret": s["secret"],
                    "gravity": 10})
    if s["uplink_ssid"] and sta_ip and parent_ip:
        out.append({"type": "ChainUplinkInterface", "name": "Chain up", "enabled": True,
                    "listen_ip": sta_ip, "listen_port": s["port"],
                    "forward_ip": parent_ip, "forward_port": s["port"],
                    "secret": s["secret"], "gravity": 10})
    _state["lan_ip"] = None
    if is_root(s) and lan_ip and lan_ip != own_ap_ip and s.get("lan", True):
        if s["secret"]:
            out.append({"type": "ChainHubInterface", "name": "Chain LAN", "enabled": True,
                        "listen_ip": lan_ip, "listen_port": s["port"], "secret": s["secret"],
                        "gravity": 10})
            _state["lan_ip"] = lan_ip
        else:
            print("[chain] not taking chain links on %s: that needs a CHAIN_SECRET" % lan_ip)
    _state["ap_ip"] = own_ap_ip
    return out


def attach(rns):
    """Called after Reticulum set up its interfaces: remembers the chain's."""
    _state["hubs"] = []
    for i in rns.interfaces:
        n = i.__class__.__name__
        if n == "ChainHubInterface":
            _state["hubs"].append(i)
            if _state["hub"] is None or getattr(i, "listen_ip", None) == _state["ap_ip"]:
                _state["hub"] = i
        elif n == "ChainUplinkInterface":
            _state["uplink"] = i


def _start_uplink(rns, s, ip, gw):
    """Creates the uplink interface once the parent's Wi-Fi is joined (at
    boot, or later if the parent came up after this Stump)."""
    import uasyncio as asyncio
    from urns.interfaces.chain import ChainUplinkInterface
    from urns.transport import Transport
    cfg = interfaces(s, ip, gw, _state["ap_ip"] or ap_ip(s))[-1]
    iface = ChainUplinkInterface(cfg)
    iface.setup_ifac(cfg)
    iface.gravity = cfg["gravity"]
    rns.interfaces.append(iface)
    Transport.register_interface(iface)
    _state["uplink"] = iface
    asyncio.create_task(iface.poll_loop())
    print("[chain] uplink to %s is up" % gw)


async def watch_loop(rns):
    """Brings the uplink up when the parent's Wi-Fi is joined, and moves it
    if its address changes (the parent rebooted and handed out a new one)."""
    import uasyncio as asyncio
    import network
    s = settings()
    if not s or not s["uplink_ssid"]:
        return
    while True:
        await asyncio.sleep(15)
        up = _state["uplink"]
        try:
            sta = network.WLAN(network.STA_IF)
            if not sta.isconnected():
                continue
            ip, mask, gw, dns = sta.ifconfig()
            _state["sta_ip"], _state["parent_ip"] = ip, gw
            if up is None:
                _start_uplink(rns, s, ip, gw)
                continue
            if ip != up.listen_ip or gw != up.forward_ip:
                print("[chain] uplink address changed: %s via %s" % (ip, gw))
                up.listen_ip = ip
                up.forward_ip = gw
                from urns.interfaces.udp import _resolve_addr
                up._forward_addr = _resolve_addr(gw, up.forward_port)
                up._recreate_socket()
        except Exception as e:
            print("[chain] watch:", e)


def status():
    """For /admin and /chain.json."""
    s = settings()
    if not s:
        return {"enabled": False}
    now = time.time()
    up, hub = _state["uplink"], _state["hub"]
    return {
        "enabled": True,
        "role": "root" if is_root(s) else "member",
        "ap_ip": ap_ip(s),
        "channel": s["channel"] or None,
        "secret": bool(s["secret"]),
        "uplink": None if is_root(s) else {
            "ssid": s["uplink_ssid"],
            "ip": up.listen_ip if up else None,
            "parent": up.forward_ip if up else None,
            "parent_heard_s": int(now - up.parent_seen) if up and up.parent_seen else None,
        },
        "lan_ip": _state["lan_ip"],
        "below": sorted(set(ip for h in (_state["hubs"] or ([hub] if hub else [])) for ip in h.peers)),
    }

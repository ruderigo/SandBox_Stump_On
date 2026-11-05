# µReticulum AutoInterface -- Reticulum's own local-network discovery, so
# NomadNet, Sideband, MeshChat (anything running the reference Reticulum
# with its default config) on the same Wi-Fi or LAN finds this Stump with
# no setup, and the other way round. Computers only: the ESP32's
# MicroPython sockets are IPv4-only (no IPv6 receive, no multicast join).
#
# Wire-compatible with reference RNS (RNS/Interfaces/AutoInterface.py):
# - every 1.6 s, on each network interface with an IPv6 link-local
#   address, a discovery token SHA-256(group_id + own link-local address)
#   is sent to the group's multicast address ff12:0:<from the group hash>,
#   port 29716; tokens heard there are checked the same way against the
#   sender's address, and the sender becomes a peer;
# - peers also get the token unicast on port 29717 now and then (so a
#   network that drops multicast still keeps the peering);
# - Reticulum packets themselves go unicast, UDP, to each peer's
#   link-local address, port 42671; a peer silent for 22 s is dropped.
# One interface here for all peers (the reference spawns one per peer):
# what goes out goes to every peer, like the Stump's UDP broadcast.

import socket
import struct
import sys
import time

from . import Interface
from ..log import log, LOG_VERBOSE, LOG_DEBUG, LOG_WARNING, LOG_ERROR, LOG_NOTICE

DEFAULT_DISCOVERY_PORT = 29716
DEFAULT_DATA_PORT = 42671
DEFAULT_GROUP_ID = b"reticulum"
ANNOUNCE_INTERVAL = 1.6
PEERING_TIMEOUT = 22.0
REVERSE_PEERING_INTERVAL = ANNOUNCE_INTERVAL * 3.25
DEDUP_TTL = 0.75
IGNORE_IFS = ("lo", "lo0", "awdl0", "llw0")


def _sha256(b):
    import hashlib
    return hashlib.sha256(b).digest()


def _descope(addr):
    """fe80::1%en0 -> fe80::1; fe80:4::1 (BSD's embedded scope) -> fe80::1."""
    addr = addr.split("%")[0]
    if addr.startswith("fe80:") and not addr.startswith("fe80::"):
        rest = addr.split("::", 1)
        if len(rest) == 2:
            addr = "fe80::" + rest[1]
    return addr


def mcast_address(group_id):
    """The group's discovery address, as the reference computes it
    (temporary multicast, link scope)."""
    g = _sha256(group_id)
    gt = "0"
    for i in range(2, 14, 2):
        gt += ":" + "{:02x}".format(g[i + 1] + (g[i] << 8))
    return "ff12:" + gt


def token(group_id, addr):
    return _sha256(group_id + _descope(addr).encode("utf-8"))


def link_local_addresses():
    """[(ifname, ifindex, link-local address)] on this computer."""
    out = []
    try:
        with open("/proc/net/if_inet6") as f:              # Linux
            for line in f:
                p = line.split()
                if len(p) < 6 or not p[0].startswith("fe80"):
                    continue
                h = p[0]
                addr = ":".join(h[i:i + 4] for i in range(0, 32, 4))
                addr = socket.inet_ntop(socket.AF_INET6, socket.inet_pton(socket.AF_INET6, addr))
                out.append((p[5], int(p[1], 16), addr))
        return [x for x in out if x[0] not in IGNORE_IFS]
    except OSError:
        pass
    try:
        import subprocess                                    # macOS, BSD
        txt = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5).stdout
        ifname = None
        for line in txt.splitlines():
            if line and not line[0].isspace():
                ifname = line.split(":")[0]
            elif ifname and "inet6 fe80:" in line:
                addr = _descope(line.split()[1])
                try:
                    out.append((ifname, socket.if_nametoindex(ifname), addr))
                except OSError:
                    pass
        if out:
            return [x for x in out if x[0] not in IGNORE_IFS]
    except Exception:
        pass
    try:                                                     # Windows (and a fallback)
        for ai in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6):
            a, scope = ai[4][0], ai[4][3]
            if a.startswith("fe80") and scope:
                out.append((str(scope), scope, _descope(a)))
    except Exception:
        pass
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


class AutoInterface(Interface):
    RX_BATCH = 32
    # Every device on the link hears every other one directly (multicast
    # discovery, then unicast to each): an announce heard here is never
    # echoed back here (Transport's split horizon). Relaying it onto LoRa
    # stays under that interface's airtime cap.
    POINT_TO_POINT = True

    def __init__(self, config):
        super().__init__(config.get("name", "Local network"))
        self.HW_MTU = 1196
        self.bitrate = 10 * 1000 * 1000
        gid = config.get("group_id", None)
        self.group_id = gid.encode("utf-8") if isinstance(gid, str) else (gid or DEFAULT_GROUP_ID)
        self.discovery_port = int(config.get("discovery_port", DEFAULT_DISCOVERY_PORT))
        self.unicast_port = self.discovery_port + 1
        self.data_port = int(config.get("data_port", DEFAULT_DATA_PORT))
        self.mcast = mcast_address(self.group_id)
        self.peers = {}            # address -> [ifindex, last heard, last reverse peering]
        self.own = {}              # ifname -> (ifindex, link-local address)
        self._disc = []            # (socket, ifname)
        self._data = []
        self._send = None
        self._recent = {}          # packet hash -> time (the same packet on two interfaces)
        self._last_announce = 0
        if sys.platform == "esp32":
            log("AutoInterface: not on this board (no IPv6 sockets); computers only", LOG_WARNING)
            return
        try:
            self._open()
        except Exception as e:
            log("AutoInterface could not start: " + str(e), LOG_ERROR)
            self.online = False

    def _open(self):
        allowed = None
        for ifname, idx, addr in link_local_addresses():
            if allowed is not None and ifname not in allowed:
                continue
            try:
                ifs = struct.pack("I", idx)
                d = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                d.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if hasattr(socket, "SO_REUSEPORT"):
                    d.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                d.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, ifs)
                d.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP,
                             socket.inet_pton(socket.AF_INET6, self.mcast) + ifs)
                if sys.platform.startswith("win"):
                    d.bind(("", self.discovery_port))
                else:
                    d.bind((self.mcast, self.discovery_port, 0, idx))
                d.setblocking(False)
                u = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if hasattr(socket, "SO_REUSEPORT"):
                    u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                u.bind(("" if sys.platform.startswith("win") else addr, self.unicast_port, 0, idx))
                u.setblocking(False)
                s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((addr, self.data_port, 0, idx))
                s.setblocking(False)
            except OSError as e:
                log("AutoInterface: skipping " + ifname + ": " + str(e), LOG_VERBOSE)
                continue
            self.own[ifname] = (idx, addr)
            self._disc += [(d, ifname), (u, ifname)]
            self._data.append((s, ifname))
            log("AutoInterface on " + ifname + " (" + addr + ")", LOG_NOTICE)
        self._send = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        self.online = bool(self.own)
        if not self.own:
            log("AutoInterface: no network interface with an IPv6 link-local address", LOG_WARNING)

    def _own_addresses(self):
        return set(a for _, a in self.own.values())

    def _announce(self, now):
        for ifname, (idx, addr) in self.own.items():
            try:
                self._send.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, struct.pack("I", idx))
                self._send.sendto(token(self.group_id, addr), (self.mcast, self.discovery_port, 0, idx))
            except OSError as e:
                log("AutoInterface: discovery on " + ifname + ": " + str(e), LOG_DEBUG)
        for paddr, p in list(self.peers.items()):
            if now - p[1] > PEERING_TIMEOUT:
                del self.peers[paddr]
                log("AutoInterface: peer " + paddr + " gone", LOG_VERBOSE)
            elif now - p[2] > REVERSE_PEERING_INTERVAL:
                ifname = p[3]
                if ifname in self.own:
                    try:
                        self._send.sendto(token(self.group_id, self.own[ifname][1]),
                                          (paddr, self.unicast_port, 0, p[0]))
                    except OSError:
                        pass
                p[2] = now

    def _discovery(self, sock, ifname, now):
        for _ in range(self.RX_BATCH):
            try:
                data, src = sock.recvfrom(1024)
            except (BlockingIOError, OSError):
                return
            addr = _descope(src[0])
            if addr in self._own_addresses():
                continue                                      # our own echo
            if data[:32] != token(self.group_id, addr):
                continue
            p = self.peers.get(addr)
            if p is None:
                self.peers[addr] = [self.own[ifname][0], now, now, ifname]
                log("AutoInterface: peer " + addr + " on " + ifname, LOG_NOTICE)
            else:
                p[1] = now

    def _receive(self, sock, now):
        got = 0
        while got < self.RX_BATCH:
            try:
                data, src = sock.recvfrom(self.HW_MTU + 64)
            except (BlockingIOError, OSError):
                break
            got += 1
            addr = _descope(src[0])
            p = self.peers.get(addr)
            if p is None:
                continue                                      # only from peers we've found
            p[1] = now
            h = _sha256(data)
            if now - self._recent.get(h, 0) < DEDUP_TTL:
                continue
            self._recent[h] = now
            if len(self._recent) > 64:
                for k in [k for k, t in self._recent.items() if now - t > DEDUP_TTL]:
                    del self._recent[k]
            self.process_incoming(data)
        return got

    def process_outgoing(self, data):
        if not self.online:
            return False
        if not self.peers:
            return True                 # nobody on the network yet: nothing to send, not a failure
        data = self.ifac_sign(data)
        sent = False
        for paddr, p in list(self.peers.items()):
            try:
                self._send.sendto(data, (paddr, self.data_port, 0, p[0]))
                sent = True
            except OSError as e:
                log("AutoInterface: send to " + paddr + ": " + str(e), LOG_DEBUG)
        if sent:
            self.txb += len(data)
            self.tx += 1
            self._last_activity = time.time()
        return sent

    async def poll_loop(self):
        try:
            import uasyncio as asyncio
        except ImportError:
            import asyncio
        while self.online:
            now = time.time()
            try:
                if now - self._last_announce >= ANNOUNCE_INTERVAL:
                    self._last_announce = now
                    self._announce(now)
                for sock, ifname in self._disc:
                    self._discovery(sock, ifname, now)
                got = 0
                for sock, ifname in self._data:
                    got += self._receive(sock, now)
            except Exception as e:
                log("AutoInterface poll error: " + str(e), LOG_ERROR)
                got = 0
            await asyncio.sleep(0 if got else 0.02)

    def close(self):
        super().close()
        for s, _ in self._disc + self._data:
            try:
                s.close()
            except Exception:
                pass
        self.online = False
